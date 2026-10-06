"""Seleção de candidatos (#3): busca na Search API fatiada por faixas de estrelas.

A Search API devolve no máximo 1.000 resultados por consulta; faixas que passam
disso são subdivididas ao meio, recursivamente, até caberem no teto.
Forks e arquivados NÃO são filtrados aqui: a exclusão é uma etapa do funil (#5).
Contribuidores ficam de fora do registro: são coletados na Issue #4.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from pipeline.config import FaixaEstrelas

log = logging.getLogger(__name__)

CAMINHO_BUSCA = "/search/repositories"
TETO_BUSCA = 1000  # limite fixo da Search API por consulta (não é parâmetro do estudo)
POR_PAGINA = 100   # máximo aceito pela API
ARQUIVO_CANDIDATOS = "candidatos.csv"
COLUNAS_CANDIDATOS = (
    "full_name", "default_branch", "stars", "language", "created_at", "fork", "archived",
)


class ClienteGitHub(Protocol):
    """Contrato 5.1 das DIRETRIZES (implementado em pipeline/github_client.py, #2)."""

    def get(self, path: str, params: dict | None = None) -> Any: ...

    def get_paginated(
        self, path: str, params: dict | None = None, item_key: str | None = None
    ) -> list[dict]: ...

    def graphql(self, query: str, variables: dict | None = None) -> dict: ...


# --- transformação (pura) -------------------------------------------------------


def corpo_json(resposta: Any) -> Any:
    """Corpo JSON de uma resposta do cliente (dict ou list).

    O contrato 5.1 define `.json` como atributo; aceita também o método do requests.Response.
    """
    return resposta.json() if callable(resposta.json) else resposta.json


def converter_item(item: dict) -> dict:
    """Item da Search API → registro Repo (contrato 5.2) sem `contributors`."""
    return {
        "full_name": item["full_name"],
        "default_branch": item["default_branch"],
        "stars": int(item["stargazers_count"]),
        "language": item.get("language"),
        "created_at": _para_datetime_utc(item["created_at"]),
        "fork": bool(item["fork"]),
        "archived": bool(item["archived"]),
    }


def deduplicar(repos: Iterable[dict]) -> list[dict]:
    """Remove repetições por `full_name`, mantendo a primeira ocorrência."""
    vistos: set[str] = set()
    unicos = []
    for repo in repos:
        if repo["full_name"] not in vistos:
            vistos.add(repo["full_name"])
            unicos.append(repo)
    return unicos


def _para_datetime_utc(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


# --- coleta (rede, via cliente) -------------------------------------------------


def fatiar_faixa(cliente: ClienteGitHub, faixa: FaixaEstrelas) -> list[tuple[FaixaEstrelas, int]]:
    """Divide a faixa em fatias com ≤ 1.000 resultados; devolve (fatia, total_count) em ordem crescente.

    Uma fatia de valor único (ex.: 1000..1000) que ainda exceda o teto é mantida com aviso:
    só os primeiros 1.000 resultados dela serão coletados.
    """
    corpo = _consultar(cliente, faixa, por_pagina=1)
    total = int(corpo["total_count"])
    if total <= TETO_BUSCA:
        return [(faixa, total)]

    if faixa.max is None:
        itens = corpo.get("items") or []
        topo = int(itens[0]["stargazers_count"]) if itens else faixa.min
        if topo <= faixa.min:
            _avisar_teto(faixa, total)
            return [(faixa, total)]
        meio = (faixa.min + topo) // 2
        superior = FaixaEstrelas(meio + 1, None)
    else:
        if faixa.min == faixa.max:
            _avisar_teto(faixa, total)
            return [(faixa, total)]
        meio = (faixa.min + faixa.max) // 2
        superior = FaixaEstrelas(meio + 1, faixa.max)

    log.info("%s tem %d resultados (> %d): subdividindo", faixa.consulta(), total, TETO_BUSCA)
    inferior = FaixaEstrelas(faixa.min, meio)
    return fatiar_faixa(cliente, inferior) + fatiar_faixa(cliente, superior)


def buscar_candidatos(cliente: ClienteGitHub, faixas: Iterable[FaixaEstrelas]) -> list[dict]:
    """Todos os candidatos das faixas, deduplicados e ordenados por estrelas (desc) e nome."""
    repos: list[dict] = []
    for faixa in faixas:
        for fatia, total in fatiar_faixa(cliente, faixa):
            if total == 0:
                continue
            itens = cliente.get_paginated(CAMINHO_BUSCA, _parametros(fatia, POR_PAGINA), item_key="items")
            log.info("%s: %d de %d repositórios coletados", fatia.consulta(), len(itens), total)
            repos.extend(converter_item(i) for i in itens)

    unicos = deduplicar(repos)
    if len(unicos) < len(repos):
        log.info("%d duplicatas removidas entre fatias", len(repos) - len(unicos))
    unicos.sort(key=lambda r: (-r["stars"], r["full_name"]))
    log.info("%d candidatos únicos", len(unicos))
    return unicos


def _parametros(faixa: FaixaEstrelas, por_pagina: int) -> dict:
    return {"q": faixa.consulta(), "sort": "stars", "order": "desc", "per_page": por_pagina}


def _consultar(cliente: ClienteGitHub, faixa: FaixaEstrelas, por_pagina: int) -> dict:
    corpo = corpo_json(cliente.get(CAMINHO_BUSCA, _parametros(faixa, por_pagina)))
    if corpo.get("incomplete_results"):
        log.warning("%s: a API sinalizou incomplete_results (timeout da busca)", faixa.consulta())
    return corpo


def _avisar_teto(faixa: FaixaEstrelas, total: int) -> None:
    log.warning(
        "%s tem %d resultados e não pode ser subdividida por estrelas: "
        "só os primeiros %d serão coletados",
        faixa.consulta(), total, TETO_BUSCA,
    )


# --- disco ----------------------------------------------------------------------


def salvar_candidatos(repos: Iterable[dict], dir_saida: Path) -> Path:
    """Escreve `candidatos.csv` em dir_saida (datas em ISO 8601 UTC); devolve o caminho."""
    dir_saida = Path(dir_saida)
    dir_saida.mkdir(parents=True, exist_ok=True)
    caminho = dir_saida / ARQUIVO_CANDIDATOS
    with caminho.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_CANDIDATOS, extrasaction="ignore")
        escritor.writeheader()
        for repo in repos:
            escritor.writerow(repo | {"created_at": repo["created_at"].isoformat()})
    log.info("candidatos salvos em %s", caminho)
    return caminho
