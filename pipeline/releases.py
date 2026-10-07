"""Coleta de releases e tags do GitHub (#7)."""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path

from pipeline.selecao import ClienteGitHub

log = logging.getLogger(__name__)

COLUNAS_RELEASES = ("full_name", "tag_name", "published_at", "draft", "prerelease")
COLUNAS_TAGS = ("full_name", "tag_name", "commit_sha", "commit_date")

_ALVO_COMMIT = "... on Commit { oid authoredDate }"
# Tags anotadas podem apontar para outra tag: segue até 3 níveis até chegar ao commit.
CONSULTA_TAGS = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    refs(refPrefix: "refs/tags/", first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        target {
          __typename
          %(commit)s
          ... on Tag { target { __typename %(commit)s
            ... on Tag { target { __typename %(commit)s
              ... on Tag { target { __typename %(commit)s } } } } } }
        }
      }
    }
  }
}
""" % {"commit": _ALVO_COMMIT}


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

    A REST `/tags` não traz datas e exigiria `GET /commits/{sha}` por tag (centenas de
    chamadas em repositórios com muitas tags). A GraphQL resolve a tag (leve ou anotada,
    inclusive em cadeia) até o commit e devolve `authoredDate` (= `commit.author.date`
    da REST), a 1 ponto por página de 100 tags. Tags que não apontam para commit
    (árvore/blob) são ignoradas com aviso. Tags são a variante da RQ 07.
    """
    dono, nome = full_name.split("/", 1)
    tags = []
    cursor = None
    while True:
        dados = cliente.graphql(CONSULTA_TAGS, {"owner": dono, "name": nome, "cursor": cursor})
        refs = dados["repository"]["refs"]
        for no in refs["nodes"]:
            commit = _commit_da_tag(no["target"])
            if commit is None:
                log.warning("%s: tag %s não aponta para um commit; ignorada", full_name, no["name"])
                continue
            tags.append({
                "tag_name": no["name"],
                "commit_sha": commit["oid"],
                "commit_date": _data_utc(commit["authoredDate"]),
            })
        if not refs["pageInfo"]["hasNextPage"]:
            break
        cursor = refs["pageInfo"]["endCursor"]
    log.info("%s: %d tags coletadas", full_name, len(tags))
    return tags


def _commit_da_tag(alvo: dict | None) -> dict | None:
    """Segue tags anotadas (Tag → … → Commit); None se não chegar a um commit."""
    while alvo is not None and alvo.get("__typename") == "Tag":
        alvo = alvo.get("target")
    if alvo is None or alvo.get("__typename") != "Commit":
        return None
    return alvo


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
