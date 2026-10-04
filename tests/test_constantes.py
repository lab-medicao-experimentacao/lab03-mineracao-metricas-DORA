import pytest

from metricas import CONCLUSOES_FALHA, CONCLUSOES_SUCESSO, classe_conclusao


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
