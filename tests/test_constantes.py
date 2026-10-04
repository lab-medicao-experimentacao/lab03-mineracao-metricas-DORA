from datetime import datetime, timedelta, timezone

import pytest

from metricas import CONCLUSOES_FALHA, CONCLUSOES_SUCESSO, classe_conclusao, run_valido

INICIO = datetime(2025, 10, 1, tzinfo=timezone.utc)
FIM = datetime(2026, 10, 1, tzinfo=timezone.utc)  # exclusivo


@pytest.mark.parametrize(
    "conclusion, esperado",
    [
        ("success", "sucesso"),
        ("failure", "falha"),
        ("timed_out", "falha"),
        ("startup_failure", "falha"),
        ("cancelled", "ignorado"),
        ("skipped", "ignorado"),
        ("neutral", "ignorado"),
        ("action_required", "ignorado"),
        ("stale", "ignorado"),
        (None, "ignorado"),
    ],
)
def test_classe_conclusao_segue_tabela_do_enunciado(conclusion, esperado):
    assert classe_conclusao(conclusion) == esperado


def test_classes_de_sucesso_e_falha_sao_disjuntas():
    assert not CONCLUSOES_SUCESSO & CONCLUSOES_FALHA


def run(**campos) -> dict:
    base = {
        "id": 1, "workflow_id": 10, "event": "push", "head_branch": "main",
        "conclusion": "success", "created_at": INICIO + timedelta(days=1),
        "run_started_at": INICIO + timedelta(days=1), "updated_at": INICIO + timedelta(days=1),
    }
    return base | campos


@pytest.mark.parametrize("conclusion", ["success", "failure", "timed_out", "startup_failure"])
def test_run_valido_com_push_no_default_branch_e_conclusao_classificada(conclusion):
    assert run_valido(run(conclusion=conclusion), "main", INICIO, FIM)


@pytest.mark.parametrize(
    "campos",
    [
        {"event": "schedule"},
        {"event": "workflow_dispatch"},
        {"event": "pull_request"},
        {"head_branch": "dev"},
        {"head_branch": None},
        {"conclusion": "cancelled"},
        {"conclusion": "skipped"},
        {"conclusion": None},
        {"created_at": FIM},
        {"created_at": INICIO - timedelta(microseconds=1)},
    ],
)
def test_run_invalido(campos):
    assert not run_valido(run(**campos), "main", INICIO, FIM)


def test_run_valido_nos_limites_da_janela():
    assert run_valido(run(created_at=INICIO), "main", INICIO, FIM)
    assert run_valido(run(created_at=FIM - timedelta(microseconds=1)), "main", INICIO, FIM)


def test_run_valido_compara_com_o_default_branch_do_repositorio():
    assert run_valido(run(head_branch="master"), "master", INICIO, FIM)
    assert not run_valido(run(head_branch="main"), "master", INICIO, FIM)
