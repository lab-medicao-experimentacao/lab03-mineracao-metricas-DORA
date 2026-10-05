"""Coleta de releases e tags do GitHub (#7)."""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from pipeline.selecao import ClienteGitHub, corpo_json

log = logging.getLogger(__name__)

COLUNAS_RELEASES = ("full_name", "tag_name", "published_at", "draft", "prerelease")
COLUNAS_TAGS = ("full_name", "tag_name", "commit_sha", "commit_date")


def _data_utc(valor: str | None) -> datetime | None:
    """Converte uma data ISO 8601 da API para datetime UTC; aceita data ausente."""
    return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(timezone.utc) if valor else None


def converter_release(item: dict) -> dict:
    """Converte a resposta da API para o contrato Release (datas em UTC)."""
    return {
        "tag_name": item["tag_name"],
        "published_at": _data_utc(item.get("published_at")),
        "draft": bool(item["draft"]),
        "prerelease": bool(item["prerelease"]),
    }


def coletar_releases(cliente: ClienteGitHub, full_name: str) -> list[dict]:
    """Coleta todas as releases, inclusive a antecessora fora da janela.

    O funil e as métricas filtram a janela depois. A API não garante ordem por
    publicação, então a lista é ordenada por ``published_at`` em ordem crescente.
    Drafts sem data de publicação ficam no final.
    """
    itens = cliente.get_paginated(f"/repos/{full_name}/releases", {"per_page": 100})
    releases = [converter_release(item) for item in itens]
    releases.sort(key=lambda r: (
        r["published_at"] is None,
        r["published_at"] or datetime.max.replace(tzinfo=timezone.utc),
    ))
    log.info("%s: %d releases coletadas", full_name, len(releases))
    return releases


def coletar_tags(cliente: ClienteGitHub, full_name: str) -> list[dict]:
    """Coleta tags e a data de autoria do commit apontado por cada uma (UTC).

    A lista de tags não contém datas. ``commit.sha`` é resolvido no endpoint de
    commits, que também aceita tags anotadas. Tags são a variante da RQ 07.
    """
    itens = cliente.get_paginated(f"/repos/{full_name}/tags", {"per_page": 100})
    tags = []
    for item in itens:
        sha = item["commit"]["sha"]
        resposta = cliente.get(f"/repos/{full_name}/commits/{quote(sha, safe='')}")
        commit = corpo_json(resposta)
        tags.append({
            "tag_name": item["name"],
            "commit_sha": commit["sha"],
            "commit_date": _data_utc(commit["commit"]["author"]["date"]),
        })
    log.info("%s: %d tags coletadas", full_name, len(tags))
    return tags


def salvar_releases(releases_por_repo: Mapping[str, Iterable[dict]], dir_processados: Path) -> Path:
    """Salva os registros Release em ``releases.csv``."""
    caminho = Path(dir_processados) / "releases.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_RELEASES)
        escritor.writeheader()
        for full_name, releases in releases_por_repo.items():
            for release in releases:
                data = release["published_at"]
                escritor.writerow({"full_name": full_name, **release,
                                   "published_at": data.isoformat() if data else ""})
    return caminho


def salvar_tags(tags_por_repo: Mapping[str, Iterable[dict]], dir_processados: Path) -> Path:
    """Salva tags e datas dos respectivos commits em ``tags.csv``."""
    caminho = Path(dir_processados) / "tags.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_TAGS)
        escritor.writeheader()
        for full_name, tags in tags_por_repo.items():
            for tag in tags:
                escritor.writerow({"full_name": full_name, **tag,
                                   "commit_date": tag["commit_date"].isoformat()})
    return caminho
