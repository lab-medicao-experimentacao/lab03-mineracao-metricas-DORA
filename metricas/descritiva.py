"""Estatística descritiva das métricas DORA (RQ 01 a RQ 04).

Mediana e quartis seguem o método linear, o mesmo de `numpy.percentile` (padrão) e de
`pandas.Series.quantile`. Valores ausentes (None ou NaN do pandas) são contados à parte.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from metricas.classificacao import CATEGORIAS

SEM_CLASSIFICACAO = "sem_classificacao"
# Ordem de apresentação: do melhor para o pior desempenho, ausentes por último.
ORDEM_DISTRIBUICAO = (*reversed(CATEGORIAS), SEM_CLASSIFICACAO)


def _ausente(valor: object) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def _quantil(ordenados: list[float], fracao: float) -> float:
    """Quantil pelo método linear sobre uma lista já ordenada e não vazia."""
    posicao = (len(ordenados) - 1) * fracao
    abaixo = math.floor(posicao)
    acima = min(abaixo + 1, len(ordenados) - 1)
    peso = posicao - abaixo
    return ordenados[abaixo] + peso * (ordenados[acima] - ordenados[abaixo])


def resumo_descritivo(valores: Iterable[float | None]) -> dict:
    """n, ausentes, mediana, q1, q3, IQR, mínimo e máximo dos valores válidos.

    As estatísticas ficam na unidade da entrada. None e NaN entram em `n_ausentes`;
    sem valores válidos, todas as estatísticas são None. Infinito levanta ValueError.
    """
    validos: list[float] = []
    n_ausentes = 0
    for valor in valores:
        if _ausente(valor):
            n_ausentes += 1
            continue
        if math.isinf(valor):
            raise ValueError(f"valor infinito: {valor}")
        validos.append(float(valor))

    resumo: dict = {"n": len(validos), "n_ausentes": n_ausentes}
    if not validos:
        return resumo | dict.fromkeys(("mediana", "q1", "q3", "iqr", "minimo", "maximo"))

    validos.sort()
    q1 = _quantil(validos, 0.25)
    q3 = _quantil(validos, 0.75)
    return resumo | {
        "mediana": _quantil(validos, 0.5),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "minimo": validos[0],
        "maximo": validos[-1],
    }


def distribuicao_categorias(categorias: Iterable[str | None]) -> dict[str, dict]:
    """Contagem e proporção (fração 0–1 do total de itens) por categoria DORA.

    Chaves na ordem Elite, High, Medium, Low, sem_classificacao (None ou NaN). A
    proporção usa o total incluindo os sem classificação; com total 0, é None.
    """
    contagens = dict.fromkeys(ORDEM_DISTRIBUICAO, 0)
    for categoria in categorias:
        if _ausente(categoria):
            contagens[SEM_CLASSIFICACAO] += 1
        elif categoria in CATEGORIAS:
            contagens[categoria] += 1
        else:
            raise ValueError(f"categoria inválida: {categoria!r}; use uma de {CATEGORIAS}")

    total = sum(contagens.values())
    return {
        chave: {"n": n, "proporcao": n / total if total else None}
        for chave, n in contagens.items()
    }
