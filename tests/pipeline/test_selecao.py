import copy
import csv
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline.config import FaixaEstrelas
from pipeline.selecao import (
    COLUNAS_CANDIDATOS,
    TETO_BUSCA,
    buscar_candidatos,
    converter_item,
    corpo_json,
    deduplicar,
    fatiar_faixa,
    salvar_candidatos,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "busca_repositorios.json"


def carregar_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def item(full_name: str, estrelas: int) -> dict:
    """Item da Search API no formato real (fixture), com nome e estrelas trocados."""
    base = copy.deepcopy(carregar_fixture()["items"][0])
    base["full_name"] = full_name
    base["name"] = full_name.split("/")[1]
    base["stargazers_count"] = estrelas
    return base


@dataclass
class Resposta:
    json: dict | list
    headers: dict = field(default_factory=dict)


class ClienteFalso:
    """Implementa o contrato 5.1 simulando /search/repositories sobre um universo fixo."""

    def __init__(self, itens: list[dict], incompleto: bool = False):
        self.itens = itens
        self.incompleto = incompleto
        self.gets: list[dict] = []
        self.paginados: list[dict] = []

    def _filtrar(self, path: str, params: dict) -> list[dict]:
        assert path == "/search/repositories"
        assert params["sort"] == "stars"
        q = params["q"]
        if m := re.fullmatch(r"stars:(\d+)\.\.(\d+)", q):
            lo, hi = int(m[1]), int(m[2])
        elif m := re.fullmatch(r"stars:>=(\d+)", q):
            lo, hi = int(m[1]), None
        else:
            raise AssertionError(f"consulta inesperada: {q}")
        filtrados = [
            i for i in self.itens
            if i["stargazers_count"] >= lo and (hi is None or i["stargazers_count"] <= hi)
        ]
        return sorted(filtrados, key=lambda i: i["stargazers_count"], reverse=True)

    def get(self, path: str, params: dict | None = None) -> Resposta:
        self.gets.append(dict(params or {}))
        filtrados = self._filtrar(path, params or {})
        por_pagina = int((params or {}).get("per_page", 30))
        return Resposta(
            json={
                "total_count": len(filtrados),
                "incomplete_results": self.incompleto,
                "items": filtrados[:por_pagina],
            },
            headers={"X-RateLimit-Remaining": "29"},
        )

    def get_paginated(
        self, path: str, params: dict | None = None, item_key: str | None = None
    ) -> list[dict]:
        assert item_key == "items"
        self.paginados.append(dict(params or {}))
        return self._filtrar(path, params or {})[:TETO_BUSCA]  # a API nunca passa de 1.000


def universo(n: int, estrelas_min: int, estrelas_max: int, prefixo: str = "org") -> list[dict]:
    """n repositórios com estrelas espalhadas uniformemente em [estrelas_min, estrelas_max]."""
    passo = (estrelas_max - estrelas_min) / max(n - 1, 1)
    return [item(f"{prefixo}/r{k}", estrelas_min + round(k * passo)) for k in range(n)]


# --- conversão (pura) -------------------------------------------------------


def test_converte_item_real_da_busca():
    bruto = carregar_fixture()["items"][0]
    repo = converter_item(bruto)
    assert repo == {
        "full_name": "jakevdp/PythonDataScienceHandbook",
        "default_branch": "master",
        "stars": 50088,
        "language": "Jupyter Notebook",
        "created_at": datetime(2016, 8, 10, 14, 24, 36, tzinfo=timezone.utc),
        "fork": False,
        "archived": False,
    }
    assert "contributors" not in repo  # preenchido pela Issue #4


def test_created_at_e_datetime_utc():
    repo = converter_item(item("a/b", 10) | {"created_at": "2024-12-01T16:33:36Z"})
    assert repo["created_at"].tzinfo is not None
    assert repo["created_at"].utcoffset().total_seconds() == 0
    assert repo["created_at"] == datetime(2024, 12, 1, 16, 33, 36, tzinfo=timezone.utc)


def test_linguagem_ausente_vira_none():
    assert converter_item(item("a/b", 10) | {"language": None})["language"] is None


def test_corpo_json_aceita_atributo_e_metodo():
    class ComMetodo:
        def json(self):
            return [1]

    assert corpo_json(Resposta(json={"a": 1})) == {"a": 1}
    assert corpo_json(ComMetodo()) == [1]


def test_deduplicar_mantem_primeira_ocorrencia():
    a1 = {"full_name": "a/x", "stars": 10}
    b = {"full_name": "b/y", "stars": 20}
    a2 = {"full_name": "a/x", "stars": 11}
    assert deduplicar([a1, b, a2]) == [a1, b]


# --- fatiamento --------------------------------------------------------------


def test_faixa_pequena_nao_e_subdividida():
    cliente = ClienteFalso(universo(300, 1000, 1499))
    fatias = fatiar_faixa(cliente, FaixaEstrelas(1000, 1499))
    assert fatias == [(FaixaEstrelas(1000, 1499), 300)]


def test_faixa_acima_do_teto_e_subdividida_sem_lacunas():
    cliente = ClienteFalso(universo(2500, 1000, 1499))
    fatias = fatiar_faixa(cliente, FaixaEstrelas(1000, 1499))

    assert len(fatias) > 1
    assert all(total <= TETO_BUSCA for _, total in fatias)
    assert sum(total for _, total in fatias) == 2500
    # as fatias cobrem a faixa original, em ordem e sem sobreposição
    assert fatias[0][0].min == 1000 and fatias[-1][0].max == 1499
    for (anterior, _), (seguinte, _) in zip(fatias, fatias[1:]):
        assert seguinte.min == anterior.max + 1


def test_faixa_sem_limite_superior_acima_do_teto_e_subdividida():
    cliente = ClienteFalso(universo(1500, 50000, 400000))
    fatias = fatiar_faixa(cliente, FaixaEstrelas(50000, None))

    assert all(total <= TETO_BUSCA for _, total in fatias)
    assert sum(total for _, total in fatias) == 1500
    assert fatias[0][0].min == 50000
    assert fatias[-1][0].max is None  # a última fatia continua aberta


def test_fatia_de_uma_estrela_acima_do_teto_gera_aviso_e_para(caplog):
    cliente = ClienteFalso([item(f"org/r{k}", 1000) for k in range(1200)])
    with caplog.at_level(logging.WARNING, logger="pipeline.selecao"):
        fatias = fatiar_faixa(cliente, FaixaEstrelas(1000, 1001))

    assert (FaixaEstrelas(1000, 1000), 1200) in fatias
    assert any("1000..1000" in r.getMessage() for r in caplog.records)


def test_faixa_aberta_com_todos_no_mesmo_valor_gera_aviso_e_para(caplog):
    cliente = ClienteFalso([item(f"org/r{k}", 70000) for k in range(1100)])
    with caplog.at_level(logging.WARNING, logger="pipeline.selecao"):
        fatias = fatiar_faixa(cliente, FaixaEstrelas(70000, None))

    assert fatias == [(FaixaEstrelas(70000, None), 1100)]
    assert any(r.levelno == logging.WARNING for r in caplog.records)


# --- busca completa ------------------------------------------------------------


def test_busca_com_fixture_real():
    dados = carregar_fixture()
    cliente = ClienteFalso(dados["items"])
    repos = buscar_candidatos(cliente, [FaixaEstrelas(50000, 50100)])

    assert [r["full_name"] for r in repos] == [i["full_name"] for i in dados["items"]]
    assert cliente.paginados[0]["per_page"] == 100
    assert cliente.paginados[0]["q"] == "stars:50000..50100"


def test_busca_nao_filtra_fork_nem_arquivado_na_consulta():
    cliente = ClienteFalso([item("a/b", 1200) | {"fork": True, "archived": True}])
    repos = buscar_candidatos(cliente, [FaixaEstrelas(1000, 1499)])

    assert all("fork" not in p["q"] and "archived" not in p["q"] for p in cliente.gets)
    assert repos[0]["fork"] is True and repos[0]["archived"] is True


def test_busca_coleta_tudo_quando_faixa_excede_o_teto():
    cliente = ClienteFalso(universo(2500, 1000, 1499) + universo(1500, 50000, 400000, "big"))
    repos = buscar_candidatos(cliente, [FaixaEstrelas(1000, 1499), FaixaEstrelas(50000, None)])

    assert len(repos) == 4000
    assert len({r["full_name"] for r in repos}) == 4000


def test_busca_ordena_por_estrelas_desc_e_nome():
    cliente = ClienteFalso([item("b/x", 1200), item("a/x", 1200), item("c/x", 2500)])
    repos = buscar_candidatos(cliente, [FaixaEstrelas(1000, 1999), FaixaEstrelas(2000, None)])
    assert [r["full_name"] for r in repos] == ["c/x", "a/x", "b/x"]


def test_duplicata_entre_faixas_e_removida():
    """Um repositório que ganha estrelas durante a coleta aparece em duas faixas."""

    class ClienteComMovimento(ClienteFalso):
        def get_paginated(self, path, params=None, item_key=None):
            itens = super().get_paginated(path, params, item_key)
            return itens + [item("mov/repo", 1999)]

    cliente = ClienteComMovimento([item("a/x", 1500), item("b/y", 2500)])
    repos = buscar_candidatos(cliente, [FaixaEstrelas(1000, 1999), FaixaEstrelas(2000, None)])

    nomes = [r["full_name"] for r in repos]
    assert sorted(nomes) == ["a/x", "b/y", "mov/repo"]


def test_faixa_vazia_nao_faz_busca_paginada():
    cliente = ClienteFalso([])
    assert buscar_candidatos(cliente, [FaixaEstrelas(1000, 1499)]) == []
    assert cliente.paginados == []


def test_resultados_incompletos_geram_aviso(caplog):
    cliente = ClienteFalso([item("a/b", 1200)], incompleto=True)
    with caplog.at_level(logging.WARNING, logger="pipeline.selecao"):
        buscar_candidatos(cliente, [FaixaEstrelas(1000, 1499)])
    assert any("incomplet" in r.getMessage() for r in caplog.records)


def test_aceita_resposta_com_json_como_metodo():
    """O stub de #2 pode devolver um requests.Response, em que .json é um método."""

    class RespostaRequests:
        def __init__(self, corpo):
            self._corpo = corpo
            self.headers = {}

        def json(self):
            return self._corpo

    class ClienteRequests(ClienteFalso):
        def get(self, path, params=None):
            return RespostaRequests(super().get(path, params).json)

    repos = buscar_candidatos(ClienteRequests([item("a/b", 1200)]), [FaixaEstrelas(1000, 1499)])
    assert [r["full_name"] for r in repos] == ["a/b"]


# --- disco -------------------------------------------------------------------------


def test_salvar_candidatos_escreve_csv(tmp_path):
    repos = [
        converter_item(item("a/x", 1200)),
        converter_item(item("b/y", 1100) | {"language": None, "fork": True}),
    ]
    caminho = salvar_candidatos(repos, tmp_path / "output")

    assert caminho == tmp_path / "output" / "candidatos.csv"
    with caminho.open(encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert list(linhas[0]) == list(COLUNAS_CANDIDATOS)
    assert linhas[0]["full_name"] == "a/x"
    assert linhas[0]["stars"] == "1200"
    assert linhas[0]["created_at"] == "2016-08-10T14:24:36+00:00"
    assert linhas[1]["language"] == ""
    assert linhas[1]["fork"] == "True"


def test_salvar_sem_candidatos_escreve_so_cabecalho(tmp_path):
    caminho = salvar_candidatos([], tmp_path)
    assert caminho.read_text(encoding="utf-8").strip() == ",".join(COLUNAS_CANDIDATOS)
