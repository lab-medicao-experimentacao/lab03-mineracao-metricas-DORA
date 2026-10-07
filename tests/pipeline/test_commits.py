"""Comparação de releases com respostas simuladas."""

import csv
import random
import threading
import time
from datetime import datetime, timezone

import pytest

from pipeline.commits import (
    coletar_commits_entre_releases,
    salvar_commits,
    salvar_releases_sem_compare,
)
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
        self.status_code = status


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


@pytest.mark.parametrize("status", [422, 500, 502])
def test_compare_que_a_api_nao_calcula_e_registrado_com_o_status(status):
    caminho = "/repos/org/repo/compare/v1...v2"
    cliente = ClienteFalso({caminho: ErroHTTP(status)})
    resultado = coletar_commits_entre_releases(
        cliente, "org/repo", [release("v1", data(1)), release("v2", data(2))],
        Janela(data(1), data(31)),
    )
    assert resultado.commits_por_release == {}
    assert resultado.releases_com_404 == ()
    assert resultado.releases_com_erro == (("v2", status),)


def test_releases_sem_compare_sao_salvas_com_o_motivo(tmp_path):
    cliente = ClienteFalso({
        "/repos/org/repo/compare/v1...v2": ErroHTTP(404),
        "/repos/org/repo/compare/v2...v3": ErroHTTP(422),
        "/repos/org/repo/compare/v3...v4": [],
    })
    resultado = coletar_commits_entre_releases(cliente, "org/repo", [
        release("v1", data(1)), release("v2", data(2)), release("v3", data(3)), release("v4", data(4)),
    ], Janela(data(1), data(31)))

    caminho = salvar_releases_sem_compare({"org/repo": resultado}, tmp_path)

    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    assert [(l["full_name"], l["tag_name"], l["motivo"]) for l in linhas] == [
        ("org/repo", "v1", "sem_anterior"),
        ("org/repo", "v2", "compare_404"),
        ("org/repo", "v3", "compare_422"),
    ]


def cadeia(n):
    """n releases em sequência na janela e respostas variadas para os compares."""
    releases = [release(f"v{i}", data(1 + i)) for i in range(n)]
    respostas = {}
    for i in range(1, n):
        caminho = f"/repos/org/repo/compare/v{i - 1}...v{i}"
        if i % 7 == 3:
            respostas[caminho] = ErroHTTP(404)
        elif i % 7 == 5:
            respostas[caminho] = ErroHTTP(422)
        else:
            respostas[caminho] = [commit(f"{i}-{k}", data(1)) for k in range(i % 4)]
    return releases, respostas


def test_com_workers_os_compares_da_mesma_release_rodam_juntos_e_o_resultado_nao_muda():
    releases, respostas = cadeia(20)
    janela = Janela(data(1), data(31))
    sequencial = coletar_commits_entre_releases(ClienteFalso(respostas), "org/repo", releases, janela)

    barreira = threading.Barrier(4, timeout=5)  # quebra se não houver 4 compares simultâneos
    trava = threading.Lock()
    iniciadas = []

    class ClienteSimultaneo(ClienteFalso):
        def get_paginated(self, path, params=None, item_key=None):
            with trava:
                ordem = len(iniciadas)
                iniciadas.append(path)
            if ordem < 8:  # os 8 primeiros compares passam em dois grupos de 4 simultâneos
                barreira.wait()
            time.sleep(random.uniform(0, 0.003))
            return super().get_paginated(path, params, item_key)

    concorrente = coletar_commits_entre_releases(
        ClienteSimultaneo(respostas), "org/repo", releases, janela, workers=4)

    assert concorrente == sequencial
    assert list(concorrente.commits_por_release) == list(sequencial.commits_por_release)
    assert concorrente.releases_com_404 and concorrente.releases_com_erro


def test_com_workers_erro_de_credencial_e_propagado():
    releases, respostas = cadeia(10)
    respostas["/repos/org/repo/compare/v5...v6"] = ErroHTTP(401)
    with pytest.raises(ErroHTTP):
        coletar_commits_entre_releases(
            ClienteFalso(respostas), "org/repo", releases, Janela(data(1), data(31)), workers=4)


def test_erro_de_credencial_e_propagado():
    caminho = "/repos/org/repo/compare/v1...v2"
    cliente = ClienteFalso({caminho: ErroHTTP(401)})
    with pytest.raises(ErroHTTP):
        coletar_commits_entre_releases(
            cliente, "org/repo", [release("v1", data(1)), release("v2", data(2))],
            Janela(data(1), data(31)),
        )
