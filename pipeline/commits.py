"""Commits entre releases pela API compare do GitHub (#8)."""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from pipeline.config import Janela
from pipeline.selecao import ClienteGitHub

log = logging.getLogger(__name__)

COLUNAS_COMMITS = ("full_name", "tag_name", "sha", "author_date", "message")


@dataclass(frozen=True)
class ResultadoCommits:
    """Commits por tag de destino e comparações não calculáveis."""

    commits_por_release: dict[str, list[dict]]
    releases_sem_anterior: tuple[str, ...]
    releases_com_404: tuple[str, ...]

    @property
    def n_404(self) -> int:
        return len(self.releases_com_404)


def converter_commit(item: dict) -> dict:
    """Converte um commit da API para o contrato Commit (data de autoria UTC)."""
    commit = item["commit"]
    data = commit["author"]["date"]
    return {
        "sha": item["sha"],
        "author_date": datetime.fromisoformat(data.replace("Z", "+00:00")).astimezone(timezone.utc),
        "message": commit["message"],
    }


def _e_404(erro: Exception) -> bool:
    resposta = getattr(erro, "response", None)
    status = getattr(resposta, "status_code", None) or getattr(erro, "status_code", None)
    return status == 404


def coletar_commits_entre_releases(
    cliente: ClienteGitHub, full_name: str, releases: Iterable[dict], janela: Janela
) -> ResultadoCommits:
    """Compara cada release principal da janela à release principal anterior.

    A antecessora pode ser anterior à janela. A primeira release da história não
    possui comparação. Um compare 404 é registrado e ignorado; outros erros sobem.
    O cliente pagina o campo ``commits`` da resposta do compare.
    """
    historico = sorted(
        (
            r for r in releases
            if not r["draft"] and not r["prerelease"]
            and r["published_at"] is not None and r["published_at"] < janela.fim
        ),
        key=lambda r: (r["published_at"], r["tag_name"]),
    )
    por_release: dict[str, list[dict]] = {}
    sem_anterior: list[str] = []
    com_404: list[str] = []

    for indice, release in enumerate(historico):
        if release["published_at"] < janela.inicio:
            continue
        tag = release["tag_name"]
        if indice == 0:
            sem_anterior.append(tag)
            continue
        anterior = historico[indice - 1]["tag_name"]
        caminho = (
            f"/repos/{full_name}/compare/"
            f"{quote(anterior, safe='')}...{quote(tag, safe='')}"
        )
        try:
            itens = cliente.get_paginated(caminho, {"per_page": 100}, item_key="commits")
        except Exception as erro:
            if not _e_404(erro):
                raise
            com_404.append(tag)
            log.warning("%s: compare %s...%s retornou 404", full_name, anterior, tag)
            continue
        por_release[tag] = [converter_commit(item) for item in itens]

    log.info(
        "%s: commits de %d releases; %d sem antecessora; %d compare 404",
        full_name, len(por_release), len(sem_anterior), len(com_404),
    )
    return ResultadoCommits(por_release, tuple(sem_anterior), tuple(com_404))


def salvar_commits(
    commits_por_repo: Mapping[str, Mapping[str, Iterable[dict]]], dir_processados: Path
) -> Path:
    """Salva commits em ``commits.csv``; cada linha associa commit e release."""
    caminho = Path(dir_processados) / "commits.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_COMMITS)
        escritor.writeheader()
        for full_name, por_release in commits_por_repo.items():
            for tag, commits in por_release.items():
                for commit in commits:
                    escritor.writerow({
                        "full_name": full_name,
                        "tag_name": tag,
                        **commit,
                        "author_date": commit["author_date"].isoformat(),
                    })
    return caminho
