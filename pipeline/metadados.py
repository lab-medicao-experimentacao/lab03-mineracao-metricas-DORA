"""Metadados dos repositórios (#4): contribuidores e idade.

A busca (#3) já traz estrelas, linguagem, `created_at`, `default_branch`, fork e
arquivado; aqui só se acrescenta o que exige chamada extra (contribuidores) ou
depende da janela (idade).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pipeline.config import Janela
from pipeline.selecao import ClienteGitHub, corpo_json

log = logging.getLogger(__name__)

CAMINHO_CONTRIBUIDORES = "/repos/{full_name}/contributors"
# per_page=1: o nº da última página no Link é o nº de contribuidores; anon=true inclui
# autores sem conta no GitHub (identificados só pelo e-mail dos commits).
PARAMETROS_CONTRIBUIDORES = {"per_page": 1, "anon": "true"}
# Erro 403 da API em repositórios com histórico grande demais (ex.: torvalds/linux)
MENSAGEM_LISTA_GRANDE = "too large to list contributors"
INTERVALO_PROGRESSO = 100  # a cada quantos repositórios logar o progresso

_LINK = re.compile(r"<([^>]*)>([^<]*)")
_PARAMETRO = re.compile(r';\s*([\w-]+)\s*=\s*("[^"]*"|[^;,\s]*)')


# --- transformação (pura) -------------------------------------------------------


def extrair_links(cabecalho: str | None) -> dict[str, str]:
    """Cabeçalho `Link` (RFC 8288) → {rel: url}; rels em minúsculas, primeira ocorrência vence."""
    links: dict[str, str] = {}
    for url, resto in _LINK.findall(cabecalho or ""):
        for nome, valor in _PARAMETRO.findall(resto):
            if nome.lower() != "rel":
                continue
            for rel in valor.strip('"').lower().split():
                links.setdefault(rel, url.strip())
    return links


def ultima_pagina(cabecalho: str | None) -> int | None:
    """Número da página `rel="last"` do cabeçalho `Link`; None se não houver."""
    url = extrair_links(cabecalho).get("last")
    if url is None:
        return None
    valores = parse_qs(urlsplit(url).query).get("page")
    if not valores or not valores[0].isdigit() or int(valores[0]) < 1:
        return None
    return int(valores[0])


def contar_contribuidores(corpo: Any, headers: Mapping[str, str] | None) -> int | None:
    """Nº de contribuidores (inclui anônimos) de uma resposta com `per_page=1`.

    Usa a página `rel="last"` do Link; sem Link, conta os itens (0 ou 1). Corpo vazio
    (repositório vazio, HTTP 204) → 0. Corpo de erro (dict com `message`, ex.: lista
    grande demais) ou inesperado → None ("desconhecido", nunca 0 por padrão).
    """
    if corpo is None or corpo == "" or corpo == []:
        return 0
    if not isinstance(corpo, list):
        return None
    ultima = ultima_pagina(_cabecalho(headers, "Link"))
    return ultima if ultima is not None else len(corpo)


def idade_dias(created_at: datetime, fim_janela: datetime) -> int:
    """Idade do repositório em dias inteiros (arredondada para baixo) no fim da janela.

    `fim_janela` é `Janela.fim`, que é EXCLUSIVO (00:00 UTC do dia seguinte ao último
    dia da janela), ou seja, o instante em que a janela termina. Negativa se o
    repositório foi criado depois da janela (não é truncada: o funil decide).
    """
    return (fim_janela - created_at).days


def _cabecalho(headers: Mapping[str, str] | None, nome: str) -> str | None:
    """Busca de cabeçalho sem diferenciar maiúsculas (dict comum ou CaseInsensitiveDict)."""
    for chave, valor in (headers or {}).items():
        if chave.lower() == nome.lower():
            return valor
    return None


# --- coleta (rede, via cliente) -------------------------------------------------


def coletar_contribuidores(cliente: ClienteGitHub, full_name: str) -> int | None:
    """Nº de contribuidores de um repositório com 1 requisição; None se a API não souber dizer.

    "Lista grande demais" (403) vira None com aviso, venha como corpo de erro ou como
    exceção do cliente; qualquer outra exceção (rate limit, 5xx, rede) é propagada.
    """
    caminho = CAMINHO_CONTRIBUIDORES.format(full_name=full_name)
    try:
        resposta = cliente.get(caminho, dict(PARAMETROS_CONTRIBUIDORES))
    except Exception as erro:
        if MENSAGEM_LISTA_GRANDE not in _texto_do_erro(erro):
            raise
        log.warning("%s: contribuidores desconhecidos (lista grande demais para a API: %s)", full_name, erro)
        return None

    corpo = _ler_corpo(resposta)
    total = contar_contribuidores(corpo, getattr(resposta, "headers", None))
    if total is None:
        mensagem = corpo.get("message") if isinstance(corpo, dict) else repr(corpo)[:200]
        log.warning("%s: contribuidores desconhecidos (%s)", full_name, mensagem)
    return total


def enriquecer_metadados(
    cliente: ClienteGitHub, repos: Iterable[dict], janela: Janela
) -> list[dict]:
    """Copia cada Repo acrescentando `contributors` (nº ou None) e `idade_dias` (dias).

    Custa 1 requisição por repositório RECEBIDO. A busca devolve dezenas de milhares
    de candidatos, então esta função não deve ser chamada sobre todos eles: quem
    decide o subconjunto (ex.: só os sorteados/elegíveis) é o funil (#5).
    """
    enriquecidos = []
    for repo in repos:
        enriquecidos.append(repo | {
            "contributors": coletar_contribuidores(cliente, repo["full_name"]),
            "idade_dias": idade_dias(repo["created_at"], janela.fim),
        })
        if len(enriquecidos) % INTERVALO_PROGRESSO == 0:
            log.info("metadados: %d repositórios processados", len(enriquecidos))

    desconhecidos = sum(r["contributors"] is None for r in enriquecidos)
    if desconhecidos:
        log.warning(
            "contribuidores desconhecidos em %d de %d repositórios", desconhecidos, len(enriquecidos)
        )
    log.info("metadados coletados para %d repositórios", len(enriquecidos))
    return enriquecidos


def _ler_corpo(resposta: Any) -> Any:
    """Corpo JSON; None para HTTP 204 / corpo vazio (o .json() do requests falha nesse caso)."""
    if getattr(resposta, "status_code", None) == 204:
        return None
    try:
        return corpo_json(resposta)
    except ValueError:
        conteudo = getattr(resposta, "content", None)
        if conteudo is not None and not conteudo.strip():
            return None
        raise


def _texto_do_erro(erro: Exception) -> str:
    """Mensagem da exceção + corpo da resposta anexada (como em requests.HTTPError)."""
    resposta = getattr(erro, "response", None)
    return f"{erro} {getattr(resposta, 'text', '') or ''}"
