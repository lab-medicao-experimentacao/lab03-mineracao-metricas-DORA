"""Comparação de releases com respostas simuladas."""

import csv
from datetime import datetime, timezone

import pytest

from pipeline.commits import coletar_commits_entre_releases, salvar_commits
from pipeline.config import Janela


def data(dia):
    return datetime(2025, 10, dia, tzinfo=timezone.utc)


def release(tag, publicada, draft=False, prerelease=False):
    return {"tag_name": tag, "published_at": publicada,
            "draft": draft, "prerelease": prerelease}


def commit(sha, data_autor):
    return {"sha": sha, "commit": {
        "author": {"date": data_autor.isoformat()}, "message": f"fix: {sha}"}}


class ErroHTTP(Exception):
    def __init__(self, status):
        self.response = type("Resposta", (), {"status_code": status})()


class ClienteFalso:
    def __init__(self, respostas):
        self.respostas = respostas
        self.chamadas = []

    def get_paginated(self, path, params=None, item_key=None):
        self.chamadas.append((path, params, item_key))
        resposta = self.respostas[path]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def test_usa_antecessora_fora_da_janela_e_pede_compare_paginado(tmp_path):
    caminho = "/repos/org/repo/compare/v0...v1"
    cliente = ClienteFalso({caminho: [commit(str(i), data(1)) for i in range(251)]})
    janela = Janela(data(1), data(31))
    releases = [release("v1", data(15)), release("v0", datetime(2025, 9, 30, tzinfo=timezone.utc))]

    resultado = coletar_commits_entre_releases(cliente, "org/repo", releases, janela)

    assert len(resultado.commits_por_release["v1"]) == 251
    assert resultado.commits_por_release["v1"][0] == {
        "sha": "0", "author_date": data(1), "message": "fix: 0"}
    assert resultado.releases_sem_anterior == ()
    assert cliente.chamadas == [(caminho, {"per_page": 100}, "commits")]

    arquivo_csv = salvar_commits({"org/repo": resultado.commits_por_release}, tmp_path)
    with arquivo_csv.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    assert len(linhas) == 251
    assert linhas[0]["tag_name"] == "v1"


def test_primeira_release_e_404_sao_registrados_sem_comparacao():
    caminho = "/repos/org/repo/compare/v1...v2"
    cliente = ClienteFalso({caminho: ErroHTTP(404)})
    janela = Janela(data(1), data(31))

    resultado = coletar_commits_entre_releases(
        cliente, "org/repo", [release("v2", data(20)), release("v1", data(10))], janela)

    assert resultado.commits_por_release == {}
    assert resultado.releases_sem_anterior == ("v1",)
    assert resultado.releases_com_404 == ("v2",)
    assert resultado.n_404 == 1


def test_prerelease_e_draft_nao_entram_na_cadeia_principal():
    caminho = "/repos/org/repo/compare/v1...v2"
    cliente = ClienteFalso({caminho: []})
    janela = Janela(data(1), data(31))

    resultado = coletar_commits_entre_releases(cliente, "org/repo", [
        release("v1", data(2)), release("rc", data(5), prerelease=True),
        release("draft", None, draft=True), release("v2", data(10)),
    ], janela)

    assert resultado.commits_por_release == {"v2": []}
    assert cliente.chamadas == [(caminho, {"per_page": 100}, "commits")]


def test_erro_diferente_de_404_e_propagado():
    caminho = "/repos/org/repo/compare/v1...v2"
    cliente = ClienteFalso({caminho: ErroHTTP(500)})
    with pytest.raises(ErroHTTP):
        coletar_commits_entre_releases(
            cliente, "org/repo", [release("v1", data(1)), release("v2", data(2))],
            Janela(data(1), data(31)),
        )
