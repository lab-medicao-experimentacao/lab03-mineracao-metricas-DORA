"""Amostra-ouro (#29): sorteio de repositórios e releases e planilhas de rotulagem manual.

Seção 6 do enunciado, passos 1 e 2. Uso: ``python -m pipeline.amostra_ouro --config config.yaml``.

Sorteio (parâmetros em ``config.yaml → amostra_ouro``):

- **repositórios:** ``amostra_ouro.tamanho`` (60) da amostra final (``output/repos.csv``) com
  ``df.sort_values("full_name").sample(n=tamanho, random_state=semente)``. A ordenação por
  ``full_name`` antes do sorteio faz o resultado depender só do conjunto de repositórios e da
  semente, não da ordem das linhas do arquivo;
- **releases:** ``amostra_ouro.releases_por_repo`` (5) de cada repositório sorteado, entre os
  deploys da definição principal (``draft = false``, ``prerelease = false``, ``published_at`` na
  janela — ``metricas.frequencia.releases_publicadas``, a mesma do funil), com
  ``random.Random(f"{semente}:{full_name}")``: semente própria por repositório, derivada de forma
  determinística (``random`` semeia strings por SHA-512, sem depender de ``PYTHONHASHSEED``).
  Com menos releases que o pedido (não acontece na amostra, que exige ≥ 5 na janela), usa todas
  e avisa.

Cada release sorteada traz o link da página dela e o ``compare`` com a release principal
publicada imediatamente antes (mesma regra de ``pipeline/commits.py`` no lead time: não draft,
não pré-release, ordem por ``published_at`` e desempate pela tag, podendo estar antes da janela).

As planilhas (``rotulos_<A|B|C>_repos.csv`` e ``rotulos_<A|B|C>_releases.csv``) **nunca** trazem
saída da heurística de release corretiva: os avaliadores rotulam sem vê-la. Os rótulos são
trabalho manual, então uma planilha com qualquer célula de rótulo/observação preenchida não é
sobrescrita sem ``--forcar``. As releases vêm de ``coletar_releases`` (#7) pelo ``GitHubClient``,
com o cache em disco de sempre: rodar de novo não repete chamadas.
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from metricas.frequencia import releases_publicadas
from pipeline.__main__ import ARQUIVO_ENV
from pipeline.config import (
    AmostraOuro,
    Config,
    ErroConfiguracao,
    Janela,
    carregar_config,
    carregar_dotenv,
    ler_token,
)
from pipeline.github_client import GitHubClient
from pipeline.metadados import ARQUIVO_REPOS
from pipeline.paralelo import mapear
from pipeline.releases import coletar_releases
from pipeline.selecao import ClienteGitHub

log = logging.getLogger(__name__)

PASTA_AMOSTRA_OURO = "amostra_ouro"  # dentro de caminhos.saida
ARQUIVO_SORTEIO_REPOS = "sorteio_repos.csv"
ARQUIVO_SORTEIO_RELEASES = "sorteio_releases.csv"
ARQUIVO_LEIAME = "LEIAME.md"
AVALIADORES = ("A", "B", "C")
URL_GITHUB = "https://github.com"

COLUNAS_SORTEIO_REPOS = ("full_name", "url_repo", "url_releases", "linguagem")
COLUNAS_SORTEIO_RELEASES = (
    "full_name", "tag_name", "published_at", "url_release", "tag_anterior", "url_compare",
)

# Valores válidos de cada coluna de rótulo (seção 6 do enunciado).
VALORES_ROTULOS_REPOS = {
    "tipo_projeto": ("biblioteca/framework", "aplicação/serviço", "ferramenta CLI", "outro"),
    "entregas_reais": ("sim", "não", "incerto"),
}
VALORES_ROTULOS_RELEASES = {"corretiva": ("sim", "não")}
COLUNA_OBSERVACOES = "observacoes"  # texto livre, opcional

COLUNAS_ROTULOS_REPOS = (*COLUNAS_SORTEIO_REPOS, *VALORES_ROTULOS_REPOS, COLUNA_OBSERVACOES)
COLUNAS_ROTULOS_RELEASES = (*COLUNAS_SORTEIO_RELEASES, *VALORES_ROTULOS_RELEASES, COLUNA_OBSERVACOES)
# Colunas preenchidas à mão: se alguma tiver conteúdo, a planilha não é regravada sem --forcar.
COLUNAS_MANUAIS = frozenset((*VALORES_ROTULOS_REPOS, *VALORES_ROTULOS_RELEASES, COLUNA_OBSERVACOES))

# As planilhas vão para Excel/Google Planilhas: BOM para o Excel reconhecer UTF-8 (acentos).
CODIFICACAO_PLANILHAS = "utf-8-sig"


class ErroAmostraOuro(RuntimeError):
    """Sorteio impossível ou planilha com rótulos que seria sobrescrita."""


# --- sorteio (puro) ---------------------------------------------------------------------


def sortear_repos(repos: pd.DataFrame, tamanho: int, semente: int) -> pd.DataFrame:
    """`tamanho` linhas de `repos` com `sample(random_state=semente)`, na ordem sorteada.

    Ordena por `full_name` antes, para o sorteio não depender da ordem do arquivo.
    """
    duplicados = repos["full_name"][repos["full_name"].duplicated()].tolist()
    if duplicados:
        raise ErroAmostraOuro(f"repositórios duplicados na amostra final: {', '.join(duplicados)}")
    if len(repos) < tamanho:
        raise ErroAmostraOuro(
            f"a amostra final tem {len(repos)} repositórios, menos que os {tamanho} "
            "da amostra-ouro (amostra_ouro.tamanho)"
        )
    ordenados = repos.sort_values("full_name", kind="mergesort").reset_index(drop=True)
    return ordenados.sample(n=tamanho, random_state=semente).reset_index(drop=True)


def sortear_releases(candidatas: Iterable[dict], n: int, semente: int, full_name: str) -> list[dict]:
    """Até `n` releases sorteadas com `random.Random(f"{semente}:{full_name}")`, em ordem de publicação.

    As candidatas são ordenadas (publicação, tag) antes do sorteio, que assim não depende da
    ordem recebida. Com menos de `n` candidatas, devolve todas e avisa no log.
    """
    ordenadas = sorted(candidatas, key=lambda r: (r["published_at"], r["tag_name"]))
    if len(ordenadas) < n:
        log.warning("%s: só %d releases elegíveis na janela (pedidas %d); usando todas",
                    full_name, len(ordenadas), n)
        return ordenadas
    sorteadas = random.Random(f"{semente}:{full_name}").sample(ordenadas, n)
    return sorted(sorteadas, key=lambda r: (r["published_at"], r["tag_name"]))


def anteriores_por_tag(releases: Iterable[dict], janela: Janela) -> dict[str, str | None]:
    """Tag → tag da release principal publicada imediatamente antes (None se for a primeira).

    Mesma regra de `pipeline/commits.py` (lead time): releases não draft, não pré-release,
    com `published_at` antes do fim da janela, ordenadas por (`published_at`, `tag_name`);
    a anterior pode ser de antes da janela.
    """
    historico = sorted(
        (
            r for r in releases
            if not r["draft"] and not r["prerelease"]
            and r["published_at"] is not None and r["published_at"] < janela.fim
        ),
        key=lambda r: (r["published_at"], r["tag_name"]),
    )
    anteriores: dict[str, str | None] = {}
    for indice, release in enumerate(historico):
        anteriores[release["tag_name"]] = historico[indice - 1]["tag_name"] if indice else None
    return anteriores


def _ref(ref: str) -> str:
    """Tag escapada para um segmento de URL (`/`, `@`, `#`, espaço… viram %XX)."""
    return quote(ref, safe="")


def url_repo(full_name: str) -> str:
    return f"{URL_GITHUB}/{full_name}"


def url_release(full_name: str, tag: str) -> str:
    """Página da release no GitHub (release notes)."""
    return f"{URL_GITHUB}/{full_name}/releases/tag/{_ref(tag)}"


def url_compare(full_name: str, anterior: str | None, tag: str) -> str:
    """Commits entre a release anterior e esta no GitHub; vazio se não há anterior."""
    if anterior is None:
        return ""
    return f"{URL_GITHUB}/{full_name}/compare/{_ref(anterior)}...{_ref(tag)}"


def linhas_releases_do_repo(
    full_name: str, releases: list[dict], janela: Janela, n: int, semente: int,
) -> list[dict]:
    """Linhas de `sorteio_releases.csv` de um repositório (até `n` deploys da janela sorteados)."""
    candidatas = releases_publicadas(releases, janela.inicio, janela.fim)
    anteriores = anteriores_por_tag(releases, janela)
    linhas = []
    for release in sortear_releases(candidatas, n, semente, full_name):
        tag = release["tag_name"]
        anterior = anteriores[tag]
        linhas.append({
            "full_name": full_name,
            "tag_name": tag,
            "published_at": release["published_at"].isoformat(),
            "url_release": url_release(full_name, tag),
            "tag_anterior": anterior or "",
            "url_compare": url_compare(full_name, anterior, tag),
        })
    return linhas


def linhas_repos(sorteados: pd.DataFrame) -> list[dict]:
    """Linhas de `sorteio_repos.csv`, na ordem do sorteio."""
    linguagens = sorteados["language"] if "language" in sorteados else pd.Series("", index=sorteados.index)
    return [
        {
            "full_name": nome,
            "url_repo": url_repo(nome),
            "url_releases": f"{url_repo(nome)}/releases",
            "linguagem": "" if pd.isna(linguagem) else str(linguagem),
        }
        for nome, linguagem in zip(sorteados["full_name"], linguagens)
    ]


# --- disco ------------------------------------------------------------------------------


def _arquivo_rotulos(avaliador: str, tipo: str) -> str:
    return f"rotulos_{avaliador}_{tipo}.csv"


def planilhas_com_rotulos(pasta: Path) -> list[Path]:
    """Planilhas `rotulos_*.csv` de `pasta` com alguma célula de rótulo/observação preenchida.

    Uma planilha que não pode ser lida como a gerada (ex.: salva pelo Excel com `;`) também
    conta como preenchida: na dúvida, não apagar trabalho manual.
    """
    preenchidas = []
    for avaliador in AVALIADORES:
        for tipo in ("repos", "releases"):
            caminho = Path(pasta) / _arquivo_rotulos(avaliador, tipo)
            if caminho.is_file() and _tem_rotulos(caminho):
                preenchidas.append(caminho)
    return preenchidas


def _tem_rotulos(caminho: Path) -> bool:
    try:
        with caminho.open(encoding=CODIFICACAO_PLANILHAS, newline="") as f:
            leitor = csv.DictReader(f)
            manuais = COLUNAS_MANUAIS & set(leitor.fieldnames or ())
            if not manuais:
                return True  # formato desconhecido
            return any((linha.get(c) or "").strip() for linha in leitor for c in manuais)
    except (UnicodeDecodeError, csv.Error):
        return True


def _gravar_csv(caminho: Path, colunas: tuple[str, ...], linhas: Iterable[dict]) -> None:
    with caminho.open("w", encoding=CODIFICACAO_PLANILHAS, newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=colunas, restval="")
        escritor.writeheader()
        escritor.writerows(linhas)


def texto_leiame(parametros: AmostraOuro, janela: Janela) -> str:
    """Instruções de rotulagem gravadas junto das planilhas (Markdown)."""
    ultimo_dia = janela.filtro_created().split("..")[1]

    def valores(mapa: dict[str, tuple[str, ...]]) -> str:
        return "\n".join(f"| `{coluna}` | {' · '.join(f'`{v}`' for v in vals)} |"
                         for coluna, vals in mapa.items())

    return f"""# Amostra-ouro — instruções de rotulagem

Gerado por `python -m pipeline.amostra_ouro --config config.yaml` (seção 6 do enunciado, #29).
Sorteio: {parametros.tamanho} repositórios de `output/{ARQUIVO_REPOS}` (semente {parametros.semente}) e
{parametros.releases_por_repo} releases de cada um, entre as publicadas (não draft, não pré-release)
de {janela.inicio.date().isoformat()} a {ultimo_dia}.

## Regras

1. Cada avaliador preenche **só a própria planilha** (`rotulos_<letra>_repos.csv` e
   `rotulos_<letra>_releases.csv`), **sem consultar os demais** até todos terminarem.
2. **Não consulte a saída da heurística de release corretiva** (nem o código dela) antes de
   terminar. As planilhas não a trazem de propósito.
3. Use exatamente os valores da tabela abaixo (minúsculas, com acento). Deixe `observacoes`
   para dúvidas e justificativas curtas.
4. Não altere as demais colunas, a ordem das linhas nem o separador (vírgula). Ao salvar pelo
   Excel, mantenha CSV UTF-8 separado por vírgulas; no Google Planilhas, Arquivo → Fazer
   download → CSV.

## Valores válidos

| Coluna | Valores |
|---|---|
{valores(VALORES_ROTULOS_REPOS)}
{valores(VALORES_ROTULOS_RELEASES)}

- `tipo_projeto` e `entregas_reais` (planilha `_repos`): leia o README e a página de releases
  (`url_repo`, `url_releases`). `entregas_reais = sim` quando as releases são versões entregues
  a usuários (pacote, binário, deploy); `não` quando são marcos internos, snapshots automáticos
  etc.; `incerto` quando não dá para decidir.
- `corretiva` (planilha `_releases`): `sim` se a release existe principalmente para corrigir
  defeitos; decida lendo as release notes (`url_release`) e os commits desde a release anterior
  (`url_compare`; vazio quando é a primeira release publicada do repositório).

Gerar de novo não apaga planilhas com algum rótulo preenchido (só com `--forcar`).
"""


# --- orquestração (rede via cliente) ----------------------------------------------------


def gerar_amostra_ouro(cliente: ClienteGitHub, config: Config, forcar: bool = False) -> Path:
    """Sorteia a amostra-ouro e grava sorteio, planilhas dos avaliadores e LEIAME; devolve a pasta.

    Aborta com `ErroAmostraOuro`, antes de qualquer chamada à API, se alguma planilha já tem
    rótulos e `forcar` é falso.
    """
    parametros = config.amostra_ouro
    if parametros is None:
        raise ErroConfiguracao("config sem a seção amostra_ouro")
    pasta = Path(config.dir_saida) / PASTA_AMOSTRA_OURO

    caminho_repos = Path(config.dir_saida) / ARQUIVO_REPOS
    if not caminho_repos.is_file():
        raise ErroAmostraOuro(
            f"{caminho_repos} não encontrado: rode `python -m pipeline --config ...` antes")
    repos = pd.read_csv(caminho_repos, dtype={"full_name": str})
    sorteados = sortear_repos(repos, parametros.tamanho, parametros.semente)

    preenchidas = planilhas_com_rotulos(pasta)
    if preenchidas and not forcar:
        raise ErroAmostraOuro(
            "planilhas com rótulos preenchidos não serão sobrescritas: "
            + ", ".join(p.name for p in preenchidas)
            + " (use --forcar para descartá-los e gerar de novo)"
        )
    if preenchidas:
        log.warning("--forcar: sobrescrevendo planilhas com rótulos: %s",
                    ", ".join(p.name for p in preenchidas))

    nomes = sorteados["full_name"].tolist()
    log.info("amostra-ouro: %d de %d repositórios sorteados (semente %d)",
             len(nomes), len(repos), parametros.semente)
    historicos = mapear(lambda nome: coletar_releases(cliente, nome), nomes, config.workers)

    repos_linhas = linhas_repos(sorteados)
    releases_linhas = [
        linha
        for nome, releases in zip(nomes, historicos)
        for linha in linhas_releases_do_repo(
            nome, releases, config.janela, parametros.releases_por_repo, parametros.semente)
    ]

    pasta.mkdir(parents=True, exist_ok=True)
    _gravar_csv(pasta / ARQUIVO_SORTEIO_REPOS, COLUNAS_SORTEIO_REPOS, repos_linhas)
    _gravar_csv(pasta / ARQUIVO_SORTEIO_RELEASES, COLUNAS_SORTEIO_RELEASES, releases_linhas)
    for avaliador in AVALIADORES:
        _gravar_csv(pasta / _arquivo_rotulos(avaliador, "repos"), COLUNAS_ROTULOS_REPOS, repos_linhas)
        _gravar_csv(pasta / _arquivo_rotulos(avaliador, "releases"), COLUNAS_ROTULOS_RELEASES,
                    releases_linhas)
    (pasta / ARQUIVO_LEIAME).write_text(texto_leiame(parametros, config.janela), encoding="utf-8")
    log.info("amostra-ouro: %d repositórios e %d releases gravados em %s",
             len(repos_linhas), len(releases_linhas), pasta)
    return pasta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pipeline.amostra_ouro",
        description="Sorteia a amostra-ouro e gera as planilhas de rotulagem (seção 6 do enunciado)",
    )
    parser.add_argument("--config", default="config.yaml", help="caminho do config.yaml")
    parser.add_argument(
        "--forcar", action="store_true",
        help="regrava as planilhas mesmo que já tenham rótulos preenchidos (descarta-os)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        config = carregar_config(args.config)
        if carregar_dotenv(ARQUIVO_ENV):
            log.info("variáveis lidas de %s", ARQUIVO_ENV)
        token = ler_token()
    except ErroConfiguracao as e:
        log.error("%s", e)
        return 2

    cliente = GitHubClient(token, config.dir_cache, max_simultaneas=config.workers)
    try:
        gerar_amostra_ouro(cliente, config, forcar=args.forcar)
    except ErroAmostraOuro as e:
        log.error("%s", e)
        return 1
    except KeyboardInterrupt:
        log.warning("interrompido: rode o mesmo comando para continuar (cache em %s)", config.dir_cache)
        return 130
    finally:
        cancelar = getattr(cliente, "cancelar", None)
        if cancelar is not None:
            cancelar()
        log.info(
            "requisições à rede nesta execução: %d (respostas do cache: %d)",
            getattr(cliente, "requisicoes_rede", 0), getattr(cliente, "acertos_cache", 0),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
