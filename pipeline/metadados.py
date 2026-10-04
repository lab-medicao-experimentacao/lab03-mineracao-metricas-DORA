"""Metadados dos repositórios (#4): contribuidores e idade.

A busca (#3) já traz estrelas, linguagem, `created_at`, `default_branch`, fork e
arquivado; aqui só se acrescenta o que exige chamada extra (contribuidores) ou
depende da janela (idade).
"""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, urlsplit

log = logging.getLogger(__name__)

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
