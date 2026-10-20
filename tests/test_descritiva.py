import math

import numpy as np
import pytest

from metricas.descritiva import distribuicao_categorias, resumo_descritivo

CHAVES_RESUMO = {"n", "n_ausentes", "mediana", "q1", "q3", "iqr", "minimo", "maximo"}
ORDEM_CATEGORIAS = ["Elite", "High", "Medium", "Low", "sem_classificacao"]


# --- resumo_descritivo -------------------------------------------------------


def test_resumo_n_impar():
    resumo = resumo_descritivo([5, 1, 4, 2, 3])
    assert set(resumo) == CHAVES_RESUMO
    assert resumo["n"] == 5
    assert resumo["n_ausentes"] == 0
    assert resumo["mediana"] == 3
    assert resumo["q1"] == 2
    assert resumo["q3"] == 4
    assert resumo["iqr"] == 2
    assert resumo["minimo"] == 1
    assert resumo["maximo"] == 5


def test_resumo_n_par():
    resumo = resumo_descritivo([1, 2, 3, 4])
    assert resumo["n"] == 4
    assert resumo["mediana"] == pytest.approx(2.5)
    assert resumo["q1"] == pytest.approx(1.75)
    assert resumo["q3"] == pytest.approx(3.25)
    assert resumo["iqr"] == pytest.approx(1.5)
    assert resumo["minimo"] == 1
    assert resumo["maximo"] == 4


@pytest.mark.parametrize(
    "valores",
    [
        [1, 2, 3, 4],
        [7.5, 0.1, 3.3, 100.0, 42.0, 8.8, 2.2],
        [13.0, -2.5, 0.0, 5.0, 5.0, 1e6, 3.14, 27.0, 0.5, 9.0, 11.0],
        [10.0, 20.0],
    ],
)
def test_resumo_quartis_iguais_ao_numpy_linear(valores):
    resumo = resumo_descritivo(valores)
    q1, mediana, q3 = np.percentile(valores, [25, 50, 75], method="linear")
    assert resumo["q1"] == pytest.approx(q1)
    assert resumo["mediana"] == pytest.approx(mediana)
    assert resumo["q3"] == pytest.approx(q3)
    assert resumo["iqr"] == pytest.approx(q3 - q1)


def test_resumo_none_e_nan_contam_como_ausentes():
    resumo = resumo_descritivo([None, 1.0, float("nan"), 2.0, 3.0, None, 4.0, 5.0])
    assert resumo["n"] == 5
    assert resumo["n_ausentes"] == 3
    assert resumo["mediana"] == 3
    assert resumo["q1"] == 2
    assert resumo["q3"] == 4


def test_resumo_lista_vazia():
    resumo = resumo_descritivo([])
    assert resumo == {
        "n": 0,
        "n_ausentes": 0,
        "mediana": None,
        "q1": None,
        "q3": None,
        "iqr": None,
        "minimo": None,
        "maximo": None,
    }


def test_resumo_so_ausentes():
    resumo = resumo_descritivo([None, math.nan])
    assert resumo["n"] == 0
    assert resumo["n_ausentes"] == 2
    assert all(resumo[chave] is None for chave in CHAVES_RESUMO - {"n", "n_ausentes"})


def test_resumo_um_unico_valor():
    resumo = resumo_descritivo([42.0])
    assert resumo["n"] == 1
    for chave in ("mediana", "q1", "q3", "minimo", "maximo"):
        assert resumo[chave] == 42.0
    assert resumo["iqr"] == 0


def test_resumo_aceita_gerador():
    resumo = resumo_descritivo(x for x in [1, 2, 3, 4, 5])
    assert resumo["n"] == 5
    assert resumo["mediana"] == 3


def test_resumo_aceita_negativos():
    resumo = resumo_descritivo([-3.0, -1.0, -2.0])
    assert resumo["mediana"] == -2.0
    assert resumo["minimo"] == -3.0


@pytest.mark.parametrize("infinito", [math.inf, -math.inf])
def test_resumo_infinito_levanta_erro(infinito):
    with pytest.raises(ValueError):
        resumo_descritivo([1.0, infinito, 2.0])


# --- distribuicao_categorias -------------------------------------------------


def test_distribuicao_ordem_das_chaves():
    distribuicao = distribuicao_categorias(["Low", "Elite"])
    assert list(distribuicao) == ORDEM_CATEGORIAS


def test_distribuicao_contagens_e_proporcoes():
    distribuicao = distribuicao_categorias(["Elite", "High", "High", "Low"])
    assert distribuicao["Elite"] == {"n": 1, "proporcao": pytest.approx(0.25)}
    assert distribuicao["High"] == {"n": 2, "proporcao": pytest.approx(0.5)}
    assert distribuicao["Medium"] == {"n": 0, "proporcao": 0.0}
    assert distribuicao["Low"] == {"n": 1, "proporcao": pytest.approx(0.25)}
    assert distribuicao["sem_classificacao"] == {"n": 0, "proporcao": 0.0}


def test_distribuicao_none_e_nan_vao_para_sem_classificacao():
    distribuicao = distribuicao_categorias(["Medium", None, float("nan"), "Medium", None])
    assert distribuicao["sem_classificacao"]["n"] == 3
    assert distribuicao["sem_classificacao"]["proporcao"] == pytest.approx(0.6)
    assert distribuicao["Medium"]["proporcao"] == pytest.approx(0.4)
    assert sum(item["proporcao"] for item in distribuicao.values()) == pytest.approx(1.0)


def test_distribuicao_aceita_gerador():
    distribuicao = distribuicao_categorias(c for c in ["Elite", "Elite"])
    assert distribuicao["Elite"] == {"n": 2, "proporcao": 1.0}


@pytest.mark.parametrize("invalida", ["elite", "Excelente", ""])
def test_distribuicao_categoria_invalida(invalida):
    with pytest.raises(ValueError):
        distribuicao_categorias(["High", invalida])


def test_distribuicao_entrada_vazia():
    distribuicao = distribuicao_categorias([])
    assert list(distribuicao) == ORDEM_CATEGORIAS
    assert all(item == {"n": 0, "proporcao": None} for item in distribuicao.values())
