"""Cliente HTTP da API REST do GitHub: cache em disco, rate limit e backoff (#2, #10).

Contrato 5.1 das DIRETRIZES: `get` devolve um `Response` (`.json`, `.headers`) e
`get_paginated` segue o cabeçalho `Link rel="next"`.

- Cache: um JSON comprimido (gzip) por requisição em `cache_dir/<aa>/<sha256>.json.gz`. Rodar de novo
  retoma de onde parou, sem repetir chamadas. Erros definitivos (404, 403 que não
  é limite de cota, 409, 410, 422, 451) também são guardados; 5xx e limite de
  cota nunca são.
- Rate limit: lê `X-RateLimit-Remaining/Reset` (por recurso: core, search…) e
  espera a renovação quando a cota acaba, antes de a API recusar.
- Backoff exponencial (1 s, 2 s, 4 s, 8 s…) para 5xx e falhas de rede.
- `graphql(query, variables)` (extensão do contrato): POST /graphql com o mesmo cache,
  backoff e cota própria (recurso 'graphql'); usado onde a REST custaria uma chamada
  por item (datas das tags).
- O token só vai no cabeçalho `Authorization` de requisições a `api.github.com`;
  nunca é registrado em log nem gravado no cache.
- Seguro para threads (paralelismo leve do pipeline, #10): uma trava por arquivo de cache
  (a mesma requisição em duas threads vai à rede uma vez e ninguém lê um arquivo sendo
  trocado); a cota é compartilhada e *reservada* antes de cada chamada (com 1 restante, só
  uma thread passa; esgotada, todas esperam a renovação); respostas fora de ordem não
  aumentam a cota (vale o menor `Remaining` da mesma janela); um 403/429 de limite pausa o
  recurso para todas as threads; um ritmo global (`intervalo_minimo`, 0,1 s ≈ 600 req/min,
  abaixo dos 900 pontos/min do limite secundário) espaça as partidas; `max_simultaneas`
  limita as requisições em voo (o pipeline usa `coleta.workers`); cada thread usa a
  própria `requests.Session`. `cancelar()` (Ctrl+C) acorda quem espera e barra novas chamadas.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

import requests

log = logging.getLogger(__name__)

HOST_API = "api.github.com"
URL_BASE = f"https://{HOST_API}"
VERSAO_API = "2022-11-28"
CAMINHO_GRAPHQL = "/graphql"

MAX_TENTATIVAS = 5          # tentativas por requisição em 5xx/falha de rede
ESPERA_BASE_S = 1.0         # 1 s, 2 s, 4 s, 8 s…
MAX_ESPERAS_COTA = 5        # esperas por limite de cota numa mesma requisição
ESPERA_LIMITE_SECUNDARIO_S = 60.0  # quando a API não diz quanto esperar (dobra a cada repetição)
ESPERA_SECUNDARIA = float("nan")   # sentinela: limite sem prazo informado pela API
# Mensagens de 403 que indicam limite (secundário) e não erro definitivo.
TERMOS_LIMITE_SECUNDARIO = ("rate limit", "abuse detection")
FOLGA_RENOVACAO_S = 1.0     # segundos extras depois do `X-RateLimit-Reset`
TIMEOUT_S = 30.0
INTERVALO_PROGRESSO = 100   # loga a cada N requisições feitas à rede
FATIA_ESPERA_S = 0.5        # esperas longas em fatias, para o Ctrl+C chegar no Windows
# Espaço mínimo entre partidas de requisições à rede, somando todas as threads: 0,1 s
# limita a ~600 req/min, abaixo dos 900 pontos/min do limite secundário da REST.
INTERVALO_MINIMO_S = 0.1

# Erros 4xx que se repetem sempre: valem a pena no cache (p. ex. compare 404).
STATUS_ERRO_CACHEAVEL = frozenset({403, 404, 409, 410, 422, 451})
# JSON comprimido: páginas de releases, runs e compare passam de 500 KB cada em texto.
SUFIXO_CACHE = ".json.gz"
NIVEL_GZIP = 6
# Só estes cabeçalhos são guardados: o resto (cookies, cota) não serve à retomada.
CABECALHOS_GUARDADOS = ("Link", "Content-Type")

_REGEX_LINK = re.compile(r'<([^>]*)>\s*;\s*rel="([^"]+)"')


@dataclass(frozen=True)
class Response:
    """Resposta da API: `json` é o corpo já decodificado (None se vazio, ex.: 204)."""

    json: Any
    headers: dict[str, str] = field(default_factory=dict)
    status_code: int = 200
    text: str = ""


class ErroHTTP(Exception):
    """Resposta HTTP de erro. `str(e)` traz o status e a mensagem da API."""

    def __init__(self, response: Response, metodo_e_caminho: str):
        self.response = response
        self.status_code = response.status_code
        mensagem = _mensagem_da_api(response)
        super().__init__(f"HTTP {response.status_code} em {metodo_e_caminho}: {mensagem}")


class ErroGraphQL(Exception):
    """Resposta GraphQL com `errors` (ex.: NOT_FOUND). `tipos` traz os `type` dos erros."""

    def __init__(self, erros: list[dict]):
        self.erros = erros
        self.tipos = {str(e.get("type")) for e in erros if e.get("type")}
        mensagens = "; ".join(str(e.get("message", "")) for e in erros)
        super().__init__(f"GraphQL: {mensagens or 'erro sem mensagem'}")


class ColetaCancelada(Exception):
    """A coleta foi cancelada (`GitHubClient.cancelar`, p. ex. no Ctrl+C): nada de rede nova."""


class GitHubClient:
    """Cliente autenticado com cache em disco, controle de cota e novas tentativas.

    Pode ser usado por várias threads ao mesmo tempo (ver docstring do módulo).
    """

    def __init__(
        self,
        token: str,
        cache_dir: Path,
        *,
        sessao: requests.Session | None = None,
        max_tentativas: int = MAX_TENTATIVAS,
        espera_base: float = ESPERA_BASE_S,
        timeout: float = TIMEOUT_S,
        dormir: Callable[[float], None] | None = None,
        agora: Callable[[], float] = time.time,
        intervalo_minimo: float = INTERVALO_MINIMO_S,
        max_simultaneas: int | None = None,
    ):
        if not token or not token.strip():
            raise ValueError("token do GitHub vazio")
        if max_tentativas < 1:
            raise ValueError("max_tentativas deve ser >= 1")
        if max_simultaneas is not None and max_simultaneas < 1:
            raise ValueError("max_simultaneas deve ser >= 1")
        # teto de requisições HTTP em voo, somando todas as threads (None = sem teto)
        self._simultaneas = (
            threading.BoundedSemaphore(max_simultaneas) if max_simultaneas is not None else None
        )
        self._cache_dir = Path(cache_dir)
        self._cabecalhos = {
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": VERSAO_API,
            "User-Agent": "lab03-mineracao-metricas-dora",
        }
        # sessão injetada (testes) é compartilhada; senão, uma requests.Session por thread
        self._sessao_fixa = sessao
        if sessao is not None:
            sessao.headers.update(self._cabecalhos)
        self._sessoes = threading.local()
        self._max_tentativas = max_tentativas
        self._espera_base = espera_base
        self._timeout = timeout
        self._cancelada = threading.Event()
        self._dormir = dormir or self._dormir_interrompivel
        self._agora = agora
        self._intervalo_minimo = intervalo_minimo
        # `_trava` protege cota, pausas, ritmo, contadores e o mapa de travas por arquivo;
        # nunca é mantida durante rede, disco ou espera.
        self._trava = threading.Lock()
        self._travas_arquivo: dict[Path, threading.Lock] = {}
        # recurso ("core", "search"…) → (requisições restantes, epoch da renovação)
        self._cota: dict[str, tuple[int, float]] = {}
        self._pausa: dict[str, float] = {}  # recurso → epoch até quando ninguém chama
        self._avisos_cota: dict[str, float] = {}  # renovação já avisada no log, por recurso
        self._proxima_partida = 0.0
        self.requisicoes_rede = 0
        self.acertos_cache = 0

    def __repr__(self) -> str:  # nunca expõe o token
        return f"GitHubClient(cache_dir={str(self._cache_dir)!r})"

    def cancelar(self) -> None:
        """Acorda as threads em espera e faz toda nova requisição à rede levantar `ColetaCancelada`."""
        self._cancelada.set()

    # --- contrato 5.1 -------------------------------------------------------------

    def get(self, path: str, params: dict | None = None) -> Response:
        """GET em `path` (ex.: '/repos/o/r/releases'); usa o cache em disco.

        Levanta `ErroHTTP` para respostas de erro (inclusive as vindas do cache).
        """
        _validar_caminho(path)
        parametros = _normalizar_parametros(params)
        arquivo = self._arquivo_cache(path, parametros)

        with self._trava_do_arquivo(arquivo):
            guardada = self._ler_cache(arquivo)
            if guardada is not None:
                self._contar_acerto_cache()
                log.debug("cache: GET %s", path)
                return self._entregar(guardada, path)

            resposta = self._buscar_na_rede(path, parametros)
            if resposta.status_code < 400 or resposta.status_code in STATUS_ERRO_CACHEAVEL:
                self._gravar_cache(arquivo, path, parametros, resposta)
        return self._entregar(resposta, path)

    def get_paginated(
        self, path: str, params: dict | None = None, item_key: str | None = None
    ) -> list[dict]:
        """Junta os itens de todas as páginas, seguindo `Link rel="next"`.

        Sem `item_key` o corpo de cada página deve ser uma lista; com `item_key`
        (ex.: 'items', 'workflow_runs', 'commits') os itens vêm de `corpo[item_key]`.
        """
        itens: list[dict] = []
        caminho, parametros = path, params
        vistas: set[tuple] = set()
        while True:
            pagina = (caminho, tuple(sorted(_normalizar_parametros(parametros).items())))
            if pagina in vistas:
                raise RuntimeError(f"paginação em laço: {caminho} repetida")
            vistas.add(pagina)

            resposta = self.get(caminho, parametros)
            itens.extend(_itens_da_pagina(resposta.json, item_key, caminho))
            proxima = proxima_pagina(_cabecalho(resposta.headers, "Link"))
            if proxima is None:
                return itens
            caminho, parametros = _separar_url(proxima)

    # --- GraphQL (extensão do contrato 5.1) -------------------------------------------

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        """POST /graphql com o mesmo cache, cota (recurso 'graphql') e backoff do `get`.

        Devolve o campo `data`. Resposta com `errors` levanta `ErroGraphQL` e não vai para
        o cache; `RATE_LIMITED` espera a renovação e repete.
        """
        corpo = {"query": query, "variables": variables or {}}
        arquivo = self._arquivo_da_chave(
            f"POST {CAMINHO_GRAPHQL} " + json.dumps(corpo, sort_keys=True, ensure_ascii=False)
        )
        with self._trava_do_arquivo(arquivo):
            resposta = self._ler_cache(arquivo)
            if resposta is not None:
                self._contar_acerto_cache()
            else:
                resposta = self._buscar_na_rede(CAMINHO_GRAPHQL, {}, corpo)
                if resposta.status_code < 400 and not _erros_graphql(resposta.json):
                    self._gravar_cache(arquivo, CAMINHO_GRAPHQL, corpo["variables"], resposta)
        if resposta.status_code >= 400:
            raise ErroHTTP(resposta, f"POST {CAMINHO_GRAPHQL}")
        erros = _erros_graphql(resposta.json)
        if erros:
            raise ErroGraphQL(erros)
        return resposta.json["data"]

    # --- rede ---------------------------------------------------------------------

    def _buscar_na_rede(
        self, path: str, parametros: dict[str, str], corpo: dict | None = None
    ) -> Response:
        """GET (ou POST com `corpo` JSON, para o GraphQL) com cota, limite e backoff."""
        rotulo = f"{'GET' if corpo is None else 'POST'} {path}"
        recurso_presumido = _recurso_presumido(path)
        falhas = esperas_cota = 0
        while True:
            numero = self._aguardar_vez(recurso_presumido)
            if numero % INTERVALO_PROGRESSO == 0:
                log.info("%d requisições à API (%d respostas vindas do cache)",
                         numero, self.acertos_cache)
            sessao = self._sessao_atual()
            try:
                with self._simultaneas or nullcontext():
                    if self._cancelada.is_set():  # cancelada enquanto esperava a vaga
                        raise ColetaCancelada("coleta cancelada")
                    if corpo is None:
                        bruta = sessao.get(URL_BASE + path, params=parametros, timeout=self._timeout)
                    else:
                        bruta = sessao.post(URL_BASE + path, json=corpo, timeout=self._timeout)
            except requests.RequestException as erro:
                falhas += 1
                if falhas >= self._max_tentativas:
                    raise
                self._esperar_backoff(falhas, rotulo, type(erro).__name__)
                continue

            self._registrar_cota(bruta.headers, path)
            resposta = _converter(bruta)

            if bruta.status_code >= 500:
                falhas += 1
                if falhas >= self._max_tentativas:
                    raise ErroHTTP(resposta, rotulo)
                self._esperar_backoff(falhas, rotulo, f"HTTP {bruta.status_code}")
                continue

            graphql_limitado = corpo is not None and any(
                e.get("type") == "RATE_LIMITED" for e in _erros_graphql(resposta.json)
            )
            if bruta.status_code in (403, 429) or graphql_limitado:
                espera = self._espera_por_limite(resposta, bruta.headers, bruta.status_code)
                if espera is None and graphql_limitado:
                    espera = ESPERA_SECUNDARIA
                if espera is not None:
                    esperas_cota += 1
                    if esperas_cota > MAX_ESPERAS_COTA:
                        raise ErroHTTP(resposta, rotulo)
                    if math.isnan(espera):
                        # sem prazo informado: 60 s, 120 s, 240 s… (boas práticas da API)
                        espera = ESPERA_LIMITE_SECUNDARIO_S * 2 ** (esperas_cota - 1)
                    log.warning("limite de cota atingido em %s: aguardando %.0f s", rotulo, espera)
                    # pausa o recurso para TODAS as threads; a pausa já cobre a renovação,
                    # então a cota anotada sai (evita esperar duas vezes em _aguardar_vez)
                    recurso = _cabecalho(bruta.headers, "X-RateLimit-Resource") or recurso_presumido
                    with self._trava:
                        self._cota.pop(recurso, None)
                        self._cota.pop(recurso_presumido, None)
                        fim_pausa = self._agora() + espera
                        self._pausa[recurso_presumido] = max(
                            self._pausa.get(recurso_presumido, 0.0), fim_pausa
                        )
                    continue
            return resposta

    def _sessao_atual(self) -> requests.Session:
        """A sessão injetada, ou uma `requests.Session` própria desta thread."""
        if self._sessao_fixa is not None:
            return self._sessao_fixa
        sessao = getattr(self._sessoes, "sessao", None)
        if sessao is None:
            sessao = requests.Session()
            sessao.headers.update(self._cabecalhos)
            self._sessoes.sessao = sessao
        return sessao

    def _dormir_interrompivel(self, segundos: float) -> None:
        """Espera real que `cancelar()` interrompe (levanta `ColetaCancelada`).

        Em fatias curtas: no Windows um `Event.wait` longo não deixa o Ctrl+C chegar
        à thread principal até o fim da espera.
        """
        fim = time.monotonic() + max(segundos, 0.0)
        while (restante := fim - time.monotonic()) > 0:
            if self._cancelada.wait(min(restante, FATIA_ESPERA_S)):
                raise ColetaCancelada("coleta cancelada durante a espera")

    def _contar_acerto_cache(self) -> None:
        with self._trava:
            self.acertos_cache += 1

    def _trava_do_arquivo(self, arquivo: Path) -> threading.Lock:
        with self._trava:
            return self._travas_arquivo.setdefault(arquivo, threading.Lock())

    def _esperar_backoff(self, falhas: int, rotulo: str, motivo: str) -> None:
        espera = self._espera_base * 2 ** (falhas - 1)
        log.warning("%s falhou (%s); tentativa %d/%d em %.0f s",
                    rotulo, motivo, falhas + 1, self._max_tentativas, espera)
        self._dormir(espera)

    # --- rate limit ---------------------------------------------------------------

    def _registrar_cota(self, headers: Mapping[str, str], path: str) -> None:
        """Anota a cota informada pela resposta.

        Na mesma janela (mesmo `Reset`) vale o menor `Remaining`: com threads, uma resposta
        mais antiga pode chegar depois e não pode devolver cota já reservada. Janela nova
        substitui; resposta de janela anterior é ignorada.
        """
        restantes = _inteiro(_cabecalho(headers, "X-RateLimit-Remaining"))
        renovacao = _inteiro(_cabecalho(headers, "X-RateLimit-Reset"))
        if restantes is None or renovacao is None:
            return
        recurso = _cabecalho(headers, "X-RateLimit-Resource") or _recurso_presumido(path)
        with self._trava:
            anotada = self._cota.get(recurso)
            if anotada is None or renovacao > anotada[1]:
                self._cota[recurso] = (restantes, float(renovacao))
            elif renovacao == anotada[1]:
                self._cota[recurso] = (min(restantes, anotada[0]), anotada[1])

    def _aguardar_vez(self, recurso: str) -> int:
        """Espera pausa, cota e ritmo; reserva uma requisição da cota e devolve o nº dela.

        Cota esgotada: espera a renovação sem gastar chamada (todas as threads esperam).
        Levanta `ColetaCancelada` depois de `cancelar()`.
        """
        while True:
            with self._trava:
                if self._cancelada.is_set():
                    raise ColetaCancelada("coleta cancelada")
                agora = self._agora()
                espera = self._pausa.get(recurso, 0.0) - agora
                if espera <= 0:
                    self._pausa.pop(recurso, None)
                    restantes, renovacao = self._cota.get(recurso, (1, 0.0))
                    if restantes <= 0:
                        espera = renovacao - agora + FOLGA_RENOVACAO_S
                        if espera <= 0:  # renovou: a próxima resposta anota a cota nova
                            del self._cota[recurso]
                            continue
                        if self._avisos_cota.get(recurso) != renovacao:
                            self._avisos_cota[recurso] = renovacao
                            log.warning("cota '%s' esgotada: aguardando %.0f s pela renovação",
                                        recurso, espera)
                if espera <= 0:
                    espera = self._proxima_partida - agora
                    if espera <= 0:
                        if recurso in self._cota:
                            restantes, renovacao = self._cota[recurso]
                            self._cota[recurso] = (restantes - 1, renovacao)
                        self._proxima_partida = agora + self._intervalo_minimo
                        self.requisicoes_rede += 1
                        return self.requisicoes_rede
            self._dormir(espera)

    def _espera_por_limite(
        self, resposta: Response, headers: Mapping[str, str], status: int
    ) -> float | None:
        """Segundos a esperar se o 403/429 é limite de cota; None se é outro erro.

        Devolve `ESPERA_SECUNDARIA` quando é limite mas a API não diz até quando
        (limite secundário): quem chama aplica a espera crescente.
        """
        retry_after = _inteiro(_cabecalho(headers, "Retry-After"))
        if retry_after is not None:
            return float(retry_after) + FOLGA_RENOVACAO_S
        if _cabecalho(headers, "X-RateLimit-Remaining") == "0":
            renovacao = _inteiro(_cabecalho(headers, "X-RateLimit-Reset"))
            if renovacao is not None:
                return max(renovacao - self._agora(), 0.0) + FOLGA_RENOVACAO_S
            return ESPERA_SECUNDARIA
        mensagem = _mensagem_da_api(resposta).lower()
        if status == 429 or any(termo in mensagem for termo in TERMOS_LIMITE_SECUNDARIO):
            return ESPERA_SECUNDARIA
        return None

    # --- cache --------------------------------------------------------------------

    def _arquivo_cache(self, path: str, parametros: dict[str, str]) -> Path:
        consulta = urlencode(sorted(parametros.items()))
        return self._arquivo_da_chave(f"GET {path}?{consulta}")

    def _arquivo_da_chave(self, requisicao: str) -> Path:
        chave = hashlib.sha256(requisicao.encode()).hexdigest()
        return self._cache_dir / chave[:2] / f"{chave}{SUFIXO_CACHE}"

    def _ler_cache(self, arquivo: Path) -> Response | None:
        """Resposta guardada, ou None. Aceita também o formato antigo (`.json` sem gzip)."""
        antigo = arquivo.with_name(arquivo.name.removesuffix(".gz"))
        for candidato, comprimido in ((arquivo, True), (antigo, False)):
            try:
                bruto = candidato.read_bytes()
            except FileNotFoundError:
                continue
            except OSError:
                break
            try:
                registro = json.loads(gzip.decompress(bruto) if comprimido else bruto)
                return Response(
                    json=registro["body"],
                    headers=dict(registro["headers"]),
                    status_code=int(registro["status_code"]),
                    text=registro.get("text", ""),
                )
            except (OSError, EOFError, ValueError, KeyError, TypeError):
                break
        else:
            return None
        log.warning("cache ilegível descartado: %s", arquivo.name)
        return None

    def _gravar_cache(
        self, arquivo: Path, path: str, parametros: dict[str, str], resposta: Response
    ) -> None:
        """Grava de forma atômica: Ctrl+C no meio não deixa arquivo pela metade."""
        registro = {
            "path": path,
            "params": parametros,
            "status_code": resposta.status_code,
            "headers": resposta.headers,
            "body": resposta.json,
            "text": resposta.text,
        }
        dados = gzip.compress(
            json.dumps(registro, ensure_ascii=False).encode("utf-8"), compresslevel=NIVEL_GZIP
        )
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        descritor, temporario = tempfile.mkstemp(dir=arquivo.parent, suffix=".tmp")
        try:
            with os.fdopen(descritor, "wb") as f:
                f.write(dados)
            os.replace(temporario, arquivo)
        except BaseException:
            Path(temporario).unlink(missing_ok=True)
            raise

    @staticmethod
    def _entregar(resposta: Response, path: str) -> Response:
        if resposta.status_code >= 400:
            raise ErroHTTP(resposta, f"GET {path}")
        return resposta


# --- funções auxiliares (puras) -------------------------------------------------------


def proxima_pagina(link: str | None) -> str | None:
    """URL do `rel="next"` de um cabeçalho `Link`, ou None na última página."""
    for url, relacao in _REGEX_LINK.findall(link or ""):
        if "next" in relacao.split():
            return url
    return None


def _separar_url(url: str) -> tuple[str, dict[str, str]]:
    """Caminho e parâmetros de uma URL de paginação; recusa qualquer outro host.

    Impede que um `Link` adulterado leve o token para fora de api.github.com.
    """
    partes = urlsplit(url)
    if partes.scheme != "https" or partes.hostname != HOST_API or partes.port not in (None, 443):
        raise ValueError(f"URL de paginação fora de {HOST_API} ignorada: {partes.scheme}://{partes.netloc}")
    return partes.path, dict(parse_qsl(partes.query, keep_blank_values=True))


def _validar_caminho(path: str) -> None:
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError(f"use um caminho relativo da API (ex.: '/repos/o/r'), recebido {path!r}")


def _normalizar_parametros(params: Mapping[str, Any] | None) -> dict[str, str]:
    """Valores como texto (bool vira 'true'/'false', como a API espera)."""
    return {
        str(chave): str(valor).lower() if isinstance(valor, bool) else str(valor)
        for chave, valor in (params or {}).items()
    }


def _recurso_presumido(path: str) -> str:
    if path == CAMINHO_GRAPHQL:
        return "graphql"
    return "search" if path.startswith("/search") else "core"


def _erros_graphql(corpo: Any) -> list[dict]:
    """Lista `errors` de uma resposta GraphQL (vazia se não houver)."""
    if isinstance(corpo, dict) and isinstance(corpo.get("errors"), list):
        return [e for e in corpo["errors"] if isinstance(e, dict)]
    return []


def _cabecalho(headers: Mapping[str, str] | None, nome: str) -> str | None:
    for chave, valor in (headers or {}).items():
        if chave.lower() == nome.lower():
            return valor
    return None


def _inteiro(valor: str | None) -> int | None:
    try:
        return int(valor) if valor is not None else None
    except ValueError:
        return None


def _converter(bruta: requests.Response) -> Response:
    """requests.Response → Response (só cabeçalhos úteis; corpo vazio vira None)."""
    headers = {
        nome: valor
        for nome in CABECALHOS_GUARDADOS
        if (valor := bruta.headers.get(nome)) is not None
    }
    sucesso = bruta.status_code < 400
    if bruta.status_code == 204 or not bruta.content.strip():
        return Response(None, headers, bruta.status_code)
    try:
        corpo = bruta.json()
    except ValueError:
        if sucesso:
            raise ValueError(f"resposta {bruta.status_code} sem JSON válido") from None
        return Response(None, headers, bruta.status_code, text=bruta.text[:500])
    texto = "" if sucesso else bruta.text[:500]
    return Response(corpo, headers, bruta.status_code, text=texto)


def _mensagem_da_api(resposta: Response) -> str:
    if isinstance(resposta.json, dict) and resposta.json.get("message"):
        return str(resposta.json["message"])
    erros = _erros_graphql(resposta.json)
    if erros:
        return "; ".join(str(e.get("message", "")) for e in erros)
    return resposta.text or "sem mensagem"


def _itens_da_pagina(corpo: Any, item_key: str | None, caminho: str) -> list[dict]:
    if corpo is None:
        return []
    if item_key is None:
        if not isinstance(corpo, list):
            raise ValueError(f"{caminho}: corpo não é uma lista; informe item_key")
        return corpo
    if not isinstance(corpo, dict) or item_key not in corpo:
        raise ValueError(f"{caminho}: campo '{item_key}' ausente na resposta")
    return corpo[item_key]
