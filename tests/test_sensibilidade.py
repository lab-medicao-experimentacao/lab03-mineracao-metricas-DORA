"""Testes de metricas/sensibilidade.py com resultados calculados à mão (RQ 07)."""

import pytest

from metricas.sensibilidade import (
    ORDEM_MATRIZ,
    SEM_CLASSIFICACAO,
    comparar_classificacoes,
    kappa_ponderado,
    matriz_transicao,
)

# Low=0, Medium=1, High=2, Elite=3; peso linear |i − j| / 3
A = ["Low", "Low", "High", "High"]
B = ["Low", "Medium", "High", "Elite"]


def test_kappa_ponderado_calculado_a_mao():
    # Do = (0 + 1/3 + 0 + 1/3) / 4 = 1/6
    # De = 0,5·(0,25·(0+1+2+3)/3) + 0,5·(0,25·(2+1+0+1)/3) = 0,25 + 1/6 = 5/12
    # kappa = 1 − Do/De = 1 − (1/6)/(5/12) = 0,6
    assert kappa_ponderado(A, B) == pytest.approx(0.6)


def test_kappa_ponderado_pesa_menos_trocas_entre_categorias_vizinhas():
    base = ["Elite", "Elite", "Low", "Low"]
    vizinha = ["High", "Elite", "Low", "Low"]   # Elite → High
    distante = ["Low", "Elite", "Low", "Low"]   # Elite → Low
    assert kappa_ponderado(base, vizinha) > kappa_ponderado(base, distante)


def test_kappa_ponderado_concordancia_perfeita_vale_um():
    assert kappa_ponderado(A, A) == pytest.approx(1.0)


def test_kappa_ponderado_indefinido_com_uma_unica_categoria_ou_sem_itens():
    assert kappa_ponderado(["High", "High"], ["High", "High"]) is None
    assert kappa_ponderado([], []) is None


def test_kappa_ponderado_exige_mesmo_tamanho():
    with pytest.raises(ValueError, match="mesmo tamanho"):
        kappa_ponderado(["High"], ["High", "Low"])


def test_comparar_classificacoes_conta_mudancas_e_direcao():
    r = comparar_classificacoes(A, B)
    assert r["n_total"] == r["n_comparados"] == 4
    assert r["n_excluidos"] == 0
    assert r["n_mudaram"] == 2                 # Low→Medium e High→Elite
    assert r["prop_mudaram"] == pytest.approx(0.5)
    assert (r["n_melhoraram"], r["n_pioraram"]) == (2, 0)
    assert r["kappa_ponderado"] == pytest.approx(0.6)


def test_comparar_classificacoes_separa_mudancas_adjacentes_de_saltos():
    r = comparar_classificacoes(["Elite", "High", "Low", "Medium"], ["Low", "Medium", "Low", "Medium"])
    assert (r["n_mudaram"], r["n_adjacentes"], r["n_saltos"]) == (2, 1, 1)  # High→Medium; Elite→Low


def test_comparar_classificacoes_conta_pioras():
    r = comparar_classificacoes(["Elite", "High", "Low"], ["Low", "High", "Medium"])
    assert (r["n_mudaram"], r["n_melhoraram"], r["n_pioraram"]) == (2, 1, 1)


def test_categorias_ausentes_saem_da_proporcao_e_do_kappa():
    de = ["Low", "Low", None, "High", float("nan")]
    para = ["Low", "Medium", "High", None, "Elite"]
    r = comparar_classificacoes(de, para)
    assert (r["n_total"], r["n_comparados"], r["n_excluidos"]) == (5, 2, 3)
    assert (r["n_mudaram"], r["prop_mudaram"]) == (1, pytest.approx(0.5))


def test_sem_nenhum_comparado_nao_ha_proporcao_nem_kappa():
    r = comparar_classificacoes([None, "Low"], ["High", None])
    assert r["n_comparados"] == 0
    assert r["prop_mudaram"] is None and r["kappa_ponderado"] is None


def test_sem_mudancas_a_proporcao_e_zero_e_nao_none():
    r = comparar_classificacoes(["Low", "High"], ["Low", "High"])
    assert r["prop_mudaram"] == 0.0 and r["n_mudaram"] == 0


def test_categoria_invalida_e_erro():
    with pytest.raises(ValueError, match="categoria inválida"):
        comparar_classificacoes(["Alta"], ["High"])
    with pytest.raises(ValueError, match="categoria inválida"):
        matriz_transicao(["High"], ["alta"])


def test_matriz_de_transicao_tem_todas_as_celulas_e_conta_ausentes():
    matriz = matriz_transicao(["Low", "Low", "High", None], ["Low", "Medium", None, "Elite"])
    assert len(matriz) == len(ORDEM_MATRIZ) ** 2
    assert matriz[("Low", "Low")] == 1
    assert matriz[("Low", "Medium")] == 1
    assert matriz[("High", SEM_CLASSIFICACAO)] == 1
    assert matriz[(SEM_CLASSIFICACAO, "Elite")] == 1
    assert sum(matriz.values()) == 4
    assert matriz[("Elite", "Elite")] == 0


def test_tamanhos_diferentes_sao_erro_nas_comparacoes():
    with pytest.raises(ValueError, match="mesmo tamanho"):
        comparar_classificacoes(["High"], ["High", "Low"])
    with pytest.raises(ValueError, match="mesmo tamanho"):
        matriz_transicao(["High"], ["High", "Low"])
