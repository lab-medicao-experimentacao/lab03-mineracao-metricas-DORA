"""Coleta de releases e tags com cliente falso, sem chamadas de rede."""

import csv
from datetime import datetime, timezone

from pipeline.releases import coletar_releases, coletar_tags, salvar_releases, salvar_tags


class ClienteFalso:
    def __init__(self, releases=None):
        self.releases = releases or []
        self.chamadas = []

    def get_paginated(self, path, params=None, item_key=None):
        self.chamadas.append((path, params, item_key))
        return self.releases


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


def _no_tag(nome, alvo):
    return {"name": nome, "target": alvo}


def _commit(oid, data):
    return {"__typename": "Commit", "oid": oid, "authoredDate": data}


class ClienteGraphQL:
    """Responde à consulta de tags por página (cursor → página)."""

    def __init__(self, paginas):
        self.paginas = paginas
        self.chamadas = []

    def graphql(self, query, variables=None):
        self.chamadas.append(variables)
        nodes, proximo = self.paginas[variables.get("cursor")]
        return {"repository": {"refs": {
            "pageInfo": {"hasNextPage": proximo is not None, "endCursor": proximo},
            "nodes": nodes,
        }}}

    def get(self, path, params=None):  # pragma: no cover - não deve ser chamado
        raise AssertionError("tags não devem custar uma chamada REST por tag")

    get_paginated = get


def test_tags_usam_data_de_autoria_do_commit_apontado_via_graphql(tmp_path):
    cliente = ClienteGraphQL({
        None: ([_no_tag("v1", _commit("abc", "2025-10-02T03:00:00+03:00"))], "c1"),
        "c1": ([_no_tag("v2", {"__typename": "Tag",
                               "target": _commit("def", "2025-11-01T00:00:00Z")})], None),
    })

    tags = coletar_tags(cliente, "org/repo")

    assert tags == [
        {"tag_name": "v1", "commit_sha": "abc", "commit_date": datetime(2025, 10, 2, tzinfo=timezone.utc)},
        {"tag_name": "v2", "commit_sha": "def", "commit_date": datetime(2025, 11, 1, tzinfo=timezone.utc)},
    ]
    assert [c["cursor"] for c in cliente.chamadas] == [None, "c1"]
    assert cliente.chamadas[0]["owner"] == "org" and cliente.chamadas[0]["name"] == "repo"

    caminho = salvar_tags({"org/repo": tags}, tmp_path)
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linha = next(csv.DictReader(arquivo))
    assert linha["commit_date"] == "2025-10-02T00:00:00+00:00"


def test_tag_anotada_em_cadeia_chega_ao_commit():
    alvo = {"__typename": "Tag", "target": {"__typename": "Tag", "target": _commit("abc", "2025-10-02T00:00:00Z")}}
    cliente = ClienteGraphQL({None: ([_no_tag("v1", alvo)], None)})
    assert coletar_tags(cliente, "org/repo")[0]["commit_sha"] == "abc"


def test_tag_que_nao_aponta_para_commit_e_ignorada_com_aviso(caplog):
    cliente = ClienteGraphQL({None: ([
        _no_tag("arvore", {"__typename": "Tree"}),
        _no_tag("v1", _commit("abc", "2025-10-02T00:00:00Z")),
    ], None)})
    tags = coletar_tags(cliente, "org/repo")
    assert [t["tag_name"] for t in tags] == ["v1"]
    assert "arvore" in caplog.text


def test_repositorio_sem_tags():
    assert coletar_tags(ClienteGraphQL({None: ([], None)}), "org/repo") == []
