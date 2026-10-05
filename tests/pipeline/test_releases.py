"""Coleta de releases e tags com cliente falso, sem chamadas de rede."""

import csv
from datetime import datetime, timezone
from types import SimpleNamespace

from pipeline.releases import coletar_releases, coletar_tags, salvar_releases, salvar_tags


class ClienteFalso:
    def __init__(self, releases=None, tags=None, commits=None):
        self.releases = releases or []
        self.tags = tags or []
        self.commits = commits or {}
        self.chamadas = []

    def get_paginated(self, path, params=None, item_key=None):
        self.chamadas.append((path, params, item_key))
        return self.tags if path.endswith("/tags") else self.releases

    def get(self, path, params=None):
        self.chamadas.append((path, params))
        return SimpleNamespace(json=self.commits[path.rsplit("/", 1)[-1]])


def test_releases_mantem_antecessora_e_ordena_por_publicacao(tmp_path):
    cliente = ClienteFalso(releases=[
        {"tag_name": "v2", "published_at": "2025-10-10T00:00:00Z",
         "draft": False, "prerelease": False},
        {"tag_name": "draft", "published_at": None, "draft": True, "prerelease": False},
        {"tag_name": "v1", "published_at": "2025-09-30T00:00:00Z",
         "draft": False, "prerelease": False},
    ])

    releases = coletar_releases(cliente, "org/repo")

    assert [r["tag_name"] for r in releases] == ["v1", "v2", "draft"]
    assert releases[0]["published_at"] == datetime(2025, 9, 30, tzinfo=timezone.utc)
    assert cliente.chamadas == [("/repos/org/repo/releases", {"per_page": 100}, None)]

    caminho = salvar_releases({"org/repo": releases}, tmp_path)
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    assert len(linhas) == 3
    assert linhas[0]["published_at"] == "2025-09-30T00:00:00+00:00"
    assert linhas[-1]["published_at"] == ""


def test_tags_usam_data_do_commit_apontado_nao_data_da_tag(tmp_path):
    cliente = ClienteFalso(
        tags=[{"name": "v1", "commit": {"sha": "abc"}}],
        commits={"abc": {"sha": "abc", "commit": {
            "author": {"date": "2025-10-02T03:00:00+03:00"},
        }}},
    )

    tags = coletar_tags(cliente, "org/repo")

    assert tags == [{"tag_name": "v1", "commit_sha": "abc",
                     "commit_date": datetime(2025, 10, 2, tzinfo=timezone.utc)}]
    assert cliente.chamadas[0] == ("/repos/org/repo/tags", {"per_page": 100}, None)
    assert cliente.chamadas[1] == ("/repos/org/repo/commits/abc", None)

    caminho = salvar_tags({"org/repo": tags}, tmp_path)
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linha = next(csv.DictReader(arquivo))
    assert linha["commit_date"] == "2025-10-02T00:00:00+00:00"
