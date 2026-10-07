"""Coleta de workflow runs com cliente falso, sem chamadas de rede."""

import csv
import logging
from datetime import date, datetime, timezone

import pytest

from metricas import CONCLUSOES_FALHA, CONCLUSOES_SUCESSO, classe_conclusao
from pipeline.config import Janela
from pipeline.funil import contar_runs_validos
from pipeline.github_client import ErroHTTP, Response
from pipeline.workflow_runs import (
    CONCLUSOES_CONTADAS,
    TETO_RUNS,
    RunsColetados,
    coletar_runs,
    contar_runs_validos_api,
    converter_run,
    fatias_mensais,
    filtro_created,
    salvar_runs,
)

JANELA = Janela(
    inicio=datetime(2025, 10, 1, tzinfo=timezone.utc),
    fim=datetime(2026, 10, 1, tzinfo=timezone.utc),
)


def item(id: int, criado: str, conclusion: str | None = "success", **campos) -> dict:
    base = {
        "id": id, "workflow_id": 7, "event": "push", "head_branch": "main",
        "conclusion": conclusion, "created_at": criado,
        "run_started_at": criado, "updated_at": criado,
    }
    return base | campos


class ClienteFalso:
    """Devolve os runs cujo `created_at` cai no filtro `created` da consulta."""

    def __init__(self, itens, extras_por_periodo=None):
        self.itens = itens
        self.extras = extras_por_periodo or {}
        self.chamadas = []

    def get_paginated(self, path, params=None, item_key=None):
        self.chamadas.append((path, params, item_key))
        inicio, fim = params["created"].split("..")
        dentro = [i for i in self.itens if inicio <= i["created_at"][:10] <= fim]
        return dentro + self.extras.get(params["created"], [])

    def get(self, path, params=None):  # pragma: no cover - não deve ser usado
        raise AssertionError("coletar_runs só usa get_paginated")


# --- fatiamento mensal -----------------------------------------------------------------


def test_janela_de_12_meses_vira_12_fatias_mensais():
    fatias = fatias_mensais(JANELA)
    assert len(fatias) == 12
    assert fatias[0] == (date(2025, 10, 1), date(2025, 10, 31))
    assert fatias[3] == (date(2026, 1, 1), date(2026, 1, 31))
    assert fatias[-1] == (date(2026, 9, 1), date(2026, 9, 30))


def test_fatias_cobrem_a_janela_sem_lacuna_nem_sobreposicao():
    fatias = fatias_mensais(JANELA)
    for (_, fim), (inicio, _) in zip(fatias, fatias[1:]):
        assert inicio.toordinal() == fim.toordinal() + 1


def test_fevereiro_bissexto_e_comum():
    janela = Janela(datetime(2027, 12, 1, tzinfo=timezone.utc), datetime(2028, 3, 1, tzinfo=timezone.utc))
    assert fatias_mensais(janela) == [
        (date(2027, 12, 1), date(2027, 12, 31)),
        (date(2028, 1, 1), date(2028, 1, 31)),
        (date(2028, 2, 1), date(2028, 2, 29)),
    ]


def test_janela_que_nao_alinha_com_meses_tem_pontas_parciais():
    janela = Janela(datetime(2025, 10, 15, tzinfo=timezone.utc), datetime(2025, 12, 11, tzinfo=timezone.utc))
    assert fatias_mensais(janela) == [
        (date(2025, 10, 15), date(2025, 10, 31)),
        (date(2025, 11, 1), date(2025, 11, 30)),
        (date(2025, 12, 1), date(2025, 12, 10)),
    ]


def test_janela_de_um_dia_tem_uma_fatia():
    janela = Janela(datetime(2026, 3, 5, tzinfo=timezone.utc), datetime(2026, 3, 6, tzinfo=timezone.utc))
    assert fatias_mensais(janela) == [(date(2026, 3, 5), date(2026, 3, 5))]


def test_filtro_created_usa_datas_inclusivas():
    assert filtro_created((date(2025, 10, 1), date(2025, 10, 31))) == "2025-10-01..2025-10-31"


# --- conversão -------------------------------------------------------------------------


def test_converter_run_entrega_o_contrato_com_datas_utc():
    run = converter_run(item(5, "2025-10-02T01:00:00Z", "failure",
                             run_started_at="2025-10-02T03:30:00+03:00",
                             updated_at="2025-10-02T00:45:00Z"))
    assert run == {
        "id": 5, "workflow_id": 7, "event": "push", "head_branch": "main",
        "conclusion": "failure",
        "created_at": datetime(2025, 10, 2, 1, tzinfo=timezone.utc),
        "run_started_at": datetime(2025, 10, 2, 0, 30, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 10, 2, 0, 45, tzinfo=timezone.utc),
    }


def test_run_started_at_ausente_cai_para_created_at():
    bruto = item(1, "2025-10-02T01:00:00Z")
    bruto["run_started_at"] = None
    assert converter_run(bruto)["run_started_at"] == datetime(2025, 10, 2, 1, tzinfo=timezone.utc)


def test_conclusion_em_andamento_fica_none():
    assert converter_run(item(1, "2025-10-02T01:00:00Z", None))["conclusion"] is None


# --- coleta ----------------------------------------------------------------------------


def test_uma_consulta_por_mes_com_filtros_de_push_e_default_branch():
    cliente = ClienteFalso([])
    coletar_runs(cliente, "org/repo", "trunk", JANELA)

    assert len(cliente.chamadas) == 12
    caminho, params, item_key = cliente.chamadas[0]
    assert caminho == "/repos/org/repo/actions/runs"
    assert params == {
        "branch": "trunk", "event": "push", "created": "2025-10-01..2025-10-31", "per_page": 100,
    }
    assert item_key == "workflow_runs"
    assert [c[1]["created"] for c in cliente.chamadas][-1] == "2026-09-01..2026-09-30"


def test_junta_os_meses_ordena_e_converte():
    cliente = ClienteFalso([
        item(3, "2026-02-10T10:00:00Z"),
        item(1, "2025-10-01T00:00:00Z", "failure"),
        item(2, "2025-12-31T23:59:59Z", "cancelled"),
    ])
    resultado = coletar_runs(cliente, "org/repo", "main", JANELA)
    assert [r["id"] for r in resultado.runs] == [1, 2, 3]
    assert resultado.runs[0]["created_at"] == datetime(2025, 10, 1, tzinfo=timezone.utc)
    assert resultado.meses_saturados == ()


def test_run_duplicado_entre_paginas_conta_uma_vez():
    cliente = ClienteFalso([item(1, "2025-10-05T00:00:00Z")],
                           extras_por_periodo={"2025-10-01..2025-10-31": [item(1, "2025-10-05T00:00:00Z")]})
    assert len(coletar_runs(cliente, "org/repo", "main", JANELA).runs) == 1


def test_mes_que_bate_1000_e_avisado_e_registrado(caplog):
    cheio = [item(i, "2025-11-15T00:00:00Z") for i in range(TETO_RUNS)]
    cliente = ClienteFalso(cheio)
    with caplog.at_level(logging.WARNING):
        resultado = coletar_runs(cliente, "org/repo", "main", JANELA)
    assert resultado.meses_saturados == ("2025-11-01..2025-11-30",)
    assert len(resultado.runs) == TETO_RUNS
    assert "teto da API" in caplog.text and "2025-11-01..2025-11-30" in caplog.text


def test_mes_com_999_runs_nao_dispara_alerta(caplog):
    cliente = ClienteFalso([item(i, "2025-11-15T00:00:00Z") for i in range(TETO_RUNS - 1)])
    with caplog.at_level(logging.WARNING):
        resultado = coletar_runs(cliente, "org/repo", "main", JANELA)
    assert resultado.meses_saturados == ()
    assert "teto da API" not in caplog.text


def test_repositorio_sem_runs_devolve_lista_vazia():
    resultado = coletar_runs(ClienteFalso([]), "org/repo", "main", JANELA)
    assert resultado.runs == [] and resultado.meses_saturados == ()


# --- coletor do funil ------------------------------------------------------------------


REPO = {"full_name": "org/repo", "default_branch": "main"}


def test_coletor_devolve_runs_do_contrato_e_guarda_so_os_saturados():
    cheio = [item(i, "2025-11-15T00:00:00Z") for i in range(TETO_RUNS)]
    coletor = RunsColetados(ClienteFalso(cheio), JANELA)
    runs = coletor(REPO)
    assert len(runs) == TETO_RUNS
    assert coletor.saturados == {"org/repo": ("2025-11-01..2025-11-30",)}


def test_coletor_sem_saturacao_nao_registra_nada():
    coletor = RunsColetados(ClienteFalso([item(1, "2025-10-05T00:00:00Z")]), JANELA)
    coletor(REPO)
    assert coletor.saturados == {}


def test_da_amostra_segue_a_ordem_da_amostra():
    coletor = RunsColetados(ClienteFalso([item(1, "2025-10-05T00:00:00Z")]), JANELA)
    outra = {"full_name": "org/outra", "default_branch": "main"}
    assert list(coletor.da_amostra([outra, REPO])) == ["org/outra", "org/repo"]


# --- pré-filtro por contagem (total_count) ----------------------------------------------


class ApiRunsFalsa:
    """Simula `/actions/runs` como a API real (conferido com sondas em 2026-10-06).

    Filtros: `branch` (= head_branch), `event`, `status` (= conclusion; valor desconhecido
    devolve 0) e `created` (datas inclusivas, em dias UTC). `total_count` conta todos os
    filtrados; a lista vem limitada a `per_page` em `get` e ao teto de 1.000 em
    `get_paginated`.
    """

    def __init__(self, itens, total_maximo=None):
        self.itens = itens
        self.total_maximo = total_maximo  # a API real limita o total_count (ex.: 2.500)
        self.chamadas = []

    def _filtrar(self, params):
        inicio, fim = params["created"].split("..")
        return [
            i for i in self.itens
            if inicio <= i["created_at"][:10] <= fim
            and i["head_branch"] == params["branch"]
            and i["event"] == params["event"]
            and ("status" not in params or i["conclusion"] == params["status"])
        ]

    def get(self, path, params=None):
        self.chamadas.append(("get", path, dict(params)))
        filtrados = self._filtrar(params)
        total = len(filtrados) if self.total_maximo is None else min(len(filtrados), self.total_maximo)
        return Response({"total_count": total, "workflow_runs": filtrados[: int(params["per_page"])]})

    def get_paginated(self, path, params=None, item_key=None):
        self.chamadas.append(("get_paginated", path, dict(params)))
        return self._filtrar(params)[:TETO_RUNS]


def test_contagem_faz_uma_consulta_per_page_1_por_conclusao_valida():
    api = ApiRunsFalsa([
        item(1, "2025-10-05T00:00:00Z", "success"),
        item(2, "2025-11-05T00:00:00Z", "failure"),
        item(3, "2025-12-05T00:00:00Z", "timed_out"),
        item(4, "2026-01-05T00:00:00Z", "startup_failure"),
        item(5, "2026-02-05T00:00:00Z", "cancelled"),
    ])

    assert contar_runs_validos_api(api, "org/repo", "main", JANELA) == 4

    consultas = [params for _, _, params in api.chamadas]
    assert [p["status"] for p in consultas] == list(CONCLUSOES_CONTADAS)
    for params in consultas:
        assert params == {
            "branch": "main", "event": "push", "created": "2025-10-01..2026-09-30",
            "status": params["status"], "per_page": 1,
        }
    assert {c for _, c, _ in api.chamadas} == {"/repos/org/repo/actions/runs"}


def test_conclusoes_contadas_sao_exatamente_as_validas_do_enunciado():
    assert set(CONCLUSOES_CONTADAS) == CONCLUSOES_SUCESSO | CONCLUSOES_FALHA
    assert set(CONCLUSOES_CONTADAS) == {"success", "failure", "timed_out", "startup_failure"}
    assert len(CONCLUSOES_CONTADAS) == len(set(CONCLUSOES_CONTADAS))
    for ignorada in ("cancelled", "skipped", "neutral", "action_required", "stale", None):
        assert classe_conclusao(ignorada) == "ignorado"
    assert all(classe_conclusao(c) != "ignorado" for c in CONCLUSOES_CONTADAS)


def test_contagem_para_ao_atingir_o_limiar():
    api = ApiRunsFalsa([item(i, "2025-10-05T00:00:00Z") for i in range(60)])
    assert contar_runs_validos_api(api, "org/repo", "main", JANELA, parar_em=50) == 60
    assert len(api.chamadas) == 1  # success já basta: as outras conclusões não mudam a decisão


def test_contagem_abaixo_do_limiar_consulta_todas_as_conclusoes():
    api = ApiRunsFalsa([item(i, "2025-10-05T00:00:00Z") for i in range(49)])
    assert contar_runs_validos_api(api, "org/repo", "main", JANELA, parar_em=50) == 49
    assert len(api.chamadas) == len(CONCLUSOES_CONTADAS)


def test_filtro_recusado_pela_api_devolve_none():
    class ApiQueRecusa(ApiRunsFalsa):
        def get(self, path, params=None):
            raise ErroHTTP(Response({"message": "Validation Failed"}, status_code=422), "GET runs")

    assert contar_runs_validos_api(ApiQueRecusa([]), "org/repo", "main", JANELA) is None


def test_erro_definitivo_na_contagem_sobe_para_o_funil():
    class ApiSemRepo(ApiRunsFalsa):
        def get(self, path, params=None):
            raise ErroHTTP(Response({"message": "Not Found"}, status_code=404), "GET runs")

    with pytest.raises(ErroHTTP):
        contar_runs_validos_api(ApiSemRepo([]), "org/repo", "main", JANELA)


def _runs_variados() -> list[dict]:
    """Runs nos limites da janela (UTC), de outros eventos/branches e de todas as conclusões."""
    conclusoes = ["success", "failure", "timed_out", "startup_failure", "cancelled",
                  "skipped", "neutral", "action_required", "stale", None]
    datas = ["2025-09-30T23:59:59Z", "2025-10-01T00:00:00Z", "2025-10-31T23:59:59Z",
             "2025-11-01T00:00:00Z", "2026-02-28T12:00:00Z", "2026-09-30T23:59:59Z",
             "2026-10-01T00:00:00Z"]
    itens, n = [], 0
    for data in datas:
        for conclusao in conclusoes:
            for evento, branch in (("push", "main"), ("push", "dev"), ("schedule", "main")):
                n += 1
                itens.append(item(n, data, conclusao, event=evento, head_branch=branch))
    return itens


def test_contagem_da_api_coincide_com_a_contagem_local_dos_runs_coletados():
    """Mesmos filtros (UTC, branch, push, conclusões válidas): pré-filtro == critério antigo."""
    api = ApiRunsFalsa(_runs_variados())
    locais = contar_runs_validos(coletar_runs(api, "org/repo", "main", JANELA).runs, "main", JANELA)
    assert locais == 5 * 4  # 5 instantes dentro da janela × 4 conclusões válidas
    assert contar_runs_validos_api(api, "org/repo", "main", JANELA) == locais


def test_contagem_limitada_pela_api_continua_acima_do_limiar():
    api = ApiRunsFalsa([item(i, "2025-10-05T00:00:00Z") for i in range(3000)], total_maximo=2500)
    assert contar_runs_validos_api(api, "org/repo", "main", JANELA, parar_em=50) >= 50


def test_coletor_teto_usa_o_limiar_do_coletor():
    api = ApiRunsFalsa([item(i, "2025-10-05T00:00:00Z") for i in range(60)])
    coletor = RunsColetados(api, JANELA, limiar=50)
    assert coletor.teto(REPO) == 60
    assert len(api.chamadas) == 1


# --- runs.csv --------------------------------------------------------------------------


def test_salvar_runs_grava_colunas_e_classe(tmp_path):
    runs = coletar_runs(ClienteFalso([
        item(1, "2025-10-01T08:00:00Z", "success"),
        item(2, "2025-10-02T08:00:00Z", "timed_out"),
        item(3, "2025-10-03T08:00:00Z", "cancelled"),
        item(4, "2025-10-04T08:00:00Z", None),
    ]), "org/repo", "main", JANELA).runs

    caminho = salvar_runs({"org/repo": runs}, tmp_path)

    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    assert caminho.name == "runs.csv"
    assert [(l["id"], l["classe"]) for l in linhas] == [
        ("1", "sucesso"), ("2", "falha"), ("3", "ignorado"), ("4", "ignorado"),
    ]
    assert linhas[0]["full_name"] == "org/repo"
    assert linhas[0]["created_at"] == "2025-10-01T08:00:00+00:00"
    assert linhas[3]["conclusion"] == ""


def test_salvar_runs_sem_dados_grava_so_o_cabecalho(tmp_path):
    caminho = salvar_runs({}, tmp_path / "novo")
    assert caminho.read_text(encoding="utf-8").strip().split(",")[0] == "full_name"


@pytest.mark.parametrize("pasta", ["a", "a/b"])
def test_salvar_runs_cria_a_pasta(tmp_path, pasta):
    assert salvar_runs({}, tmp_path / pasta).exists()
