from datetime import datetime, timezone

import pytest

from metricas.cfr import cfr_ci

BASE = datetime(2025, 10, 1, tzinfo=timezone.utc)


def run(conclusion: str | None, id: int = 1) -> dict:
    return {
        "id": id, "workflow_id": 10, "event": "push", "head_branch": "main",
        "conclusion": conclusion, "created_at": BASE,
        "run_started_at": BASE, "updated_at": BASE,
    }


def runs_de(*conclusoes: str | None) -> list[dict]:
    return [run(c, id=i) for i, c in enumerate(conclusoes)]


def test_exemplo_de_papel_tres_falhas_em_dez_runs():
    runs = runs_de(*["success"] * 7, "failure", "timed_out", "startup_failure")
    assert cfr_ci(runs) == pytest.approx(0.3)


def test_so_sucessos_da_zero_e_nao_none():
    assert cfr_ci(runs_de("success", "success")) == 0.0


def test_so_falhas_da_um():
    assert cfr_ci(runs_de("failure", "timed_out")) == 1.0


@pytest.mark.parametrize("falha", ["failure", "timed_out", "startup_failure"])
def test_cada_conclusao_de_falha_conta_como_falha(falha):
    assert cfr_ci(runs_de("success", falha)) == 0.5


@pytest.mark.parametrize(
    "ignorada", ["cancelled", "skipped", "neutral", "action_required", "stale", None]
)
def test_runs_ignorados_ficam_fora_do_numerador_e_do_denominador(ignorada):
    runs = runs_de("success", "failure", ignorada, ignorada, ignorada)
    assert cfr_ci(runs) == 0.5


def test_sem_runs_retorna_none():
    assert cfr_ci([]) is None


def test_so_runs_ignorados_retorna_none():
    assert cfr_ci(runs_de("cancelled", "skipped", None)) is None


def test_aceita_qualquer_iteravel():
    assert cfr_ci(iter(runs_de("success", "failure"))) == 0.5
