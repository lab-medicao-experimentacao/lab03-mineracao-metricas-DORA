"""Exemplos sintéticos com resultados calculáveis à mão."""

import pytest

from metricas.validacao import avaliar_classificacao


def test_exemplo_do_enunciado():
    # 40 previsões positivas, 30 confirmadas, 50 positivas reais.
    reais = [True] * 30 + [False] * 10 + [True] * 20 + [False] * 40
    previstos = [True] * 40 + [False] * 60
    resultado = avaliar_classificacao(reais, previstos)
    assert resultado == {
        "n_itens": 100, "n_corretivas_reais": 50, "n_corretivas_previstas": 40,
        "vp": 30, "fp": 10, "fn": 20, "vn": 40,
        "precisao": 0.75, "recall": 0.6, "f1": pytest.approx(2 / 3), "situacao": "refinar",
    }


@pytest.mark.parametrize("vp, fp, fn, situacao", [
    (7, 3, 3, "atingiu_meta"), (6, 4, 4, "refinar"), (1, 0, 0, "atingiu_meta"),
])
def test_meta_sem_arredondamento(vp, fp, fn, situacao):
    resultado = avaliar_classificacao([True] * vp + [False] * fp + [True] * fn,
                                      [True] * (vp + fp) + [False] * fn)
    assert resultado["situacao"] == situacao


@pytest.mark.parametrize("reais, previstos, situacao", [
    ([True, False], [False, False], "refinar"),
    ([False, False], [False, False], "sem_positivos"),
    ([False, False], [True, True], "sem_positivos"),
    ([True, False], [False, True], "refinar"),
])
def test_zeros_nao_geram_nan(reais, previstos, situacao):
    resultado = avaliar_classificacao(reais, previstos)
    assert resultado["precisao"] == resultado["recall"] == resultado["f1"] == 0.0
    assert resultado["situacao"] == situacao


@pytest.mark.parametrize("reais, previstos", [
    ([], []), ([True], []), ([True], [True, False]),
    (["sim"], [True]), ([1], [True]), ([True], [None]),
])
def test_entradas_invalidas(reais, previstos):
    with pytest.raises(ValueError):
        avaliar_classificacao(reais, previstos)
