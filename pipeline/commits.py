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
from pipeline.paralelo import em_ordem
from pipeline.selecao import ClienteGitHub

log = logging.getLogger(__name__)

COLUNAS_COMMITS = ("full_name", "tag_name", "sha", "author_date", "message")
ARQUIVO_SEM_COMPARE = "releases_sem_compare.csv"
COLUNAS_SEM_COMPARE = ("full_name", "tag_name", "motivo")
# Respostas do compare que significam "não dá para comparar estas duas releases" (tag
# apagada/reescrita, sem ancestral comum, diff grande demais) e não falha da coleta.
STATUS_COMPARE_IGNORAVEL = frozenset({404, 422})


@dataclass(frozen=True)
class ResultadoCommits:
    """Commits por tag de destino e comparações não calculáveis."""

    commits_por_release: dict[str, list[dict]]
    releases_sem_anterior: tuple[str, ...]
    releases_com_404: tuple[str, ...]
    releases_com_erro: tuple[tuple[str, int], ...] = ()  # (tag, status) de 422 e 5xx persistente

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


def _status(erro: Exception) -> int | None:
    resposta = getattr(erro, "response", None)
    return getattr(resposta, "status_code", None) or getattr(erro, "status_code", None)


def coletar_commits_entre_releases(
    cliente: ClienteGitHub, full_name: str, releases: Iterable[dict], janela: Janela,
    workers: int = 1,
) -> ResultadoCommits:
    """Compara cada release principal da janela à release principal anterior.

    A antecessora pode ser anterior à janela. A primeira release da história não
    possui comparação. Um compare 404 (FAQ do enunciado), 422 ou 5xx que persiste após
    as novas tentativas do cliente é registrado e a release fica fora do lead time;
    outros erros (ex.: 401) sobem. 5xx não fica no cache: é tentado de novo na próxima
    execução. O cliente pagina o campo ``commits`` da resposta do compare. Com
    `workers > 1`, os compares são pedidos em paralelo; o resultado (e a ordem) é o mesmo.
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
    com_erro: list[tuple[str, int]] = []

    pares: list[tuple[str, str]] = []  # (anterior, tag), na ordem de publicação
    for indice, release in enumerate(historico):
        if release["published_at"] < janela.inicio:
            continue
        if indice == 0:
            sem_anterior.append(release["tag_name"])
        else:
            pares.append((historico[indice - 1]["tag_name"], release["tag_name"]))

    def comparar(par: tuple[str, str]) -> list[dict]:
        anterior, tag = par
        caminho = (
            f"/repos/{full_name}/compare/"
            f"{quote(anterior, safe='')}...{quote(tag, safe='')}"
        )
        return cliente.get_paginated(caminho, {"per_page": 100}, item_key="commits")

    for (anterior, tag), itens, erro in em_ordem(comparar, pares, workers):
        if erro is not None:
            status = _status(erro)
            if status == 404:
                com_404.append(tag)
            elif status in STATUS_COMPARE_IGNORAVEL or (status or 0) >= 500:
                com_erro.append((tag, status))
            else:
                raise erro
            log.warning("%s: compare %s...%s retornou %s; release fora do lead time",
                        full_name, anterior, tag, status)
            continue
        por_release[tag] = [converter_commit(item) for item in itens]

    log.info(
        "%s: commits de %d releases; %d sem antecessora; %d compare 404; %d outros erros",
        full_name, len(por_release), len(sem_anterior), len(com_404), len(com_erro),
    )
    return ResultadoCommits(por_release, tuple(sem_anterior), tuple(com_404), tuple(com_erro))


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


def salvar_releases_sem_compare(
    resultados: Mapping[str, ResultadoCommits], dir_processados: Path
) -> Path:
    """Salva em ``releases_sem_compare.csv`` as releases da janela sem commits calculáveis.

    `motivo`: `sem_anterior` (primeira release da história), `compare_404` ou
    `compare_<status>`. O enunciado pede para contar as ignoradas por 404.
    """
    caminho = Path(dir_processados) / ARQUIVO_SEM_COMPARE
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_SEM_COMPARE)
        escritor.writeheader()
        for full_name, resultado in resultados.items():
            linhas = [(t, "sem_anterior") for t in resultado.releases_sem_anterior]
            linhas += [(t, "compare_404") for t in resultado.releases_com_404]
            linhas += [(t, f"compare_{s}") for t, s in resultado.releases_com_erro]
            for tag, motivo in linhas:
                escritor.writerow({"full_name": full_name, "tag_name": tag, "motivo": motivo})
    return caminho
