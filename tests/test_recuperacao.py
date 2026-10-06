from datetime import datetime, timedelta, timezone

import pytest

from metricas.recuperacao import episodios_recuperacao, tempo_recuperacao

DIA = datetime(2025, 11, 3, tzinfo=timezone.utc)
FIM_JANELA = datetime(2026, 10, 1, tzinfo=timezone.utc)


def em(hora: int, minuto: int = 0, dia: datetime = DIA) -> datetime:
    return dia.replace(hour=hora, minute=minuto)


def run(id: int, conclusion: str | None, inicio: datetime, fim: datetime | None = None,
        workflow_id: int = 10) -> dict:
    return {
        "id": id, "workflow_id": workflow_id, "event": "push", "head_branch": "main",
        "conclusion": conclusion, "created_at": inicio, "run_started_at": inicio,
        "updated_at": fim or inicio + timedelta(minutes=5),
    }


def serie_do_enunciado() -> list[dict]:
    """Workflow CI: 09:00 ok, 10:00 falha, 10:30 falha, 11:15 ok (termina 11:20)."""
    return [
        run(1, "success", em(9)),
        run(2, "failure", em(10)),
        run(3, "failure", em(10, 30)),
        run(4, "success", em(11, 15), fim=em(11, 20)),
    ]


def test_exemplo_do_enunciado_recupera_em_1h20():
    episodios = episodios_recuperacao(serie_do_enunciado(), FIM_JANELA)
    assert episodios == [
        {"inicio": em(10), "fim": em(11, 20), "horas": pytest.approx(80 / 60), "censurado": False}
    ]


def test_tempo_recuperacao_do_exemplo():
    resumo = tempo_recuperacao(serie_do_enunciado(), FIM_JANELA)
    assert resumo["mediana_horas"] == pytest.approx(80 / 60)
    assert resumo["n_episodios"] == 1
    assert resumo["prop_censurados"] == 0.0


def test_ordena_cronologicamente_mesmo_com_entrada_embaralhada():
    runs = serie_do_enunciado()[::-1]
    assert len(episodios_recuperacao(runs, FIM_JANELA)) == 1


def test_falha_nunca_recuperada_e_censurada_ate_o_fim_da_janela():
    runs = [run(1, "success", em(9)), run(2, "failure", em(10))]
    (episodio,) = episodios_recuperacao(runs, FIM_JANELA)
    assert episodio["censurado"] is True
    assert episodio["fim"] == FIM_JANELA
    assert episodio["horas"] == pytest.approx((FIM_JANELA - em(10)) / timedelta(hours=1))


def test_censurados_entram_na_mediana_e_na_proporcao():
    runs = [
        run(1, "success", em(9)),
        run(2, "failure", em(10)),
        run(3, "success", em(11), fim=em(11)),  # episódio de 1 h
        run(4, "failure", em(12)),  # censurado
    ]
    resumo = tempo_recuperacao(runs, em(12) + timedelta(hours=3))
    # episódios de 1 h e 3 h (censurado): mediana = 2 h
    assert resumo["n_episodios"] == 2
    assert resumo["mediana_horas"] == pytest.approx(2.0)
    assert resumo["prop_censurados"] == 0.5


def test_runs_cancelados_sao_ignorados_e_nao_encerram_o_episodio():
    runs = [
        run(1, "success", em(9)),
        run(2, "failure", em(10)),
        run(3, "cancelled", em(10, 20)),
        run(4, "skipped", em(10, 40)),
        run(5, None, em(10, 50)),  # em andamento
        run(6, "success", em(11), fim=em(11)),
    ]
    (episodio,) = episodios_recuperacao(runs, FIM_JANELA)
    assert episodio["inicio"] == em(10)
    assert episodio["horas"] == pytest.approx(1.0)


def test_cancelado_entre_sucessos_nao_abre_episodio():
    runs = [run(1, "success", em(9)), run(2, "cancelled", em(10)), run(3, "success", em(11))]
    assert episodios_recuperacao(runs, FIM_JANELA) == []


def test_falhas_antes_do_primeiro_sucesso_nao_abrem_episodio():
    runs = [run(1, "failure", em(8)), run(2, "failure", em(9)), run(3, "success", em(10))]
    assert episodios_recuperacao(runs, FIM_JANELA) == []


def test_so_falhas_sem_sucesso_anterior_nao_gera_episodio():
    runs = [run(1, "failure", em(8)), run(2, "timed_out", em(9))]
    assert episodios_recuperacao(runs, FIM_JANELA) == []


def test_workflows_diferentes_sao_independentes():
    runs = [
        run(1, "success", em(9), workflow_id=1),
        run(2, "failure", em(10), workflow_id=1),
        run(3, "success", em(10, 30), workflow_id=2),  # sucesso de outro workflow não recupera o 1
        run(4, "success", em(12), fim=em(12), workflow_id=1),
        run(5, "success", em(8), workflow_id=2),
    ]
    (episodio,) = episodios_recuperacao(runs, FIM_JANELA)
    assert episodio["horas"] == pytest.approx(2.0)


def test_mediana_entre_episodios_de_varios_workflows():
    runs = []
    for workflow, horas in ((1, 1), (2, 2), (3, 10)):
        runs += [
            run(workflow * 10, "success", em(0), workflow_id=workflow),
            run(workflow * 10 + 1, "failure", em(1), workflow_id=workflow),
            run(workflow * 10 + 2, "success", em(1) + timedelta(hours=horas),
                fim=em(1) + timedelta(hours=horas), workflow_id=workflow),
        ]
    resumo = tempo_recuperacao(runs, FIM_JANELA)
    assert resumo["n_episodios"] == 3
    assert resumo["mediana_horas"] == pytest.approx(2.0)


def test_dois_episodios_no_mesmo_workflow():
    runs = [
        run(1, "success", em(0)),
        run(2, "failure", em(1)),
        run(3, "success", em(2), fim=em(2)),
        run(4, "timed_out", em(3)),
        run(5, "success", em(5), fim=em(5)),
    ]
    episodios = episodios_recuperacao(runs, FIM_JANELA)
    assert [e["horas"] for e in episodios] == [pytest.approx(1.0), pytest.approx(2.0)]
    assert [e["inicio"] for e in episodios] == [em(1), em(3)]


def test_desempate_por_id_quando_created_at_e_igual():
    runs = [run(2, "failure", em(10)), run(1, "success", em(10)), run(3, "success", em(11), fim=em(11))]
    (episodio,) = episodios_recuperacao(runs, FIM_JANELA)
    assert episodio["horas"] == pytest.approx(1.0)


def test_sem_runs_nao_ha_dados():
    assert tempo_recuperacao([], FIM_JANELA) == {
        "mediana_horas": None, "n_episodios": 0, "prop_censurados": None,
    }


def test_sem_falhas_nao_ha_episodios():
    runs = [run(1, "success", em(9)), run(2, "success", em(10))]
    resumo = tempo_recuperacao(runs, FIM_JANELA)
    assert resumo["n_episodios"] == 0
    assert resumo["mediana_horas"] is None
