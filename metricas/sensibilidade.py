"""Sensibilidade da classificação DORA à definição operacional (RQ 07), sem rede ou disco.

Compara as categorias que duas combinações de definições atribuem aos mesmos repositórios:
proporção que muda de categoria, kappa de Cohen ponderado (pesos lineares, categorias
ordenadas Low < Medium < High < Elite) e matriz de transição.

Tratamento de categoria ausente (`None`, ou NaN do pandas): o repositório não pôde ser
classificado por uma das combinações. Ele **sai da proporção de mudança e do kappa**
(`n_excluidos`), mas aparece na matriz de transição, na linha/coluna `SEM_CLASSIFICACAO`.
"""

from __future__ import annotations

import math
import warnings
from collections import Counter
from collections.abc import Sequence

from sklearn.metrics import cohen_kappa_score

from metricas.classificacao import CATEGORIAS, PONTOS

SEM_CLASSIFICACAO = "sem_classificacao"
# Ordem de apresentação das matrizes: do melhor para o pior desempenho, ausente por último.
ORDEM_MATRIZ = (*reversed(CATEGORIAS), SEM_CLASSIFICACAO)


def _ausente(categoria: object) -> bool:
    return categoria is None or (isinstance(categoria, float) and math.isnan(categoria))


def _validar(categoria: object) -> None:
    if not _ausente(categoria) and categoria not in PONTOS:
        raise ValueError(f"categoria inválida: {categoria!r}")


def kappa_ponderado(a: Sequence[str], b: Sequence[str]) -> float | None:
    """Kappa de Cohen com pesos lineares entre duas classificações completas (sem ausentes).

    Usa `cohen_kappa_score(..., labels=CATEGORIAS, weights="linear")`. Retorna None quando o
    kappa é indefinido: sem itens, ou as duas classificações usam uma única categoria (o
    acordo esperado ao acaso é total e a razão não existe).
    """
    if len(a) != len(b):
        raise ValueError("as classificações devem ter o mesmo tamanho")
    if not a:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # sklearn avisa em vez de falhar
        kappa = cohen_kappa_score(list(a), list(b), labels=list(CATEGORIAS), weights="linear")
    return None if math.isnan(kappa) else float(kappa)


def matriz_transicao(
    de: Sequence[str | None], para: Sequence[str | None]
) -> dict[tuple[str, str], int]:
    """Contagem de repositórios por (categoria em `de`, categoria em `para`).

    Todas as 5 × 5 células de `ORDEM_MATRIZ` estão presentes (zero quando vazias); ausentes
    entram como `SEM_CLASSIFICACAO`.
    """
    if len(de) != len(para):
        raise ValueError("as classificações devem ter o mesmo tamanho")
    for categoria in (*de, *para):
        _validar(categoria)

    def rotulo(categoria: str | None) -> str:
        return SEM_CLASSIFICACAO if _ausente(categoria) else categoria

    contagem = Counter((rotulo(x), rotulo(y)) for x, y in zip(de, para))
    return {(x, y): contagem[(x, y)] for x in ORDEM_MATRIZ for y in ORDEM_MATRIZ}


def comparar_classificacoes(de: Sequence[str | None], para: Sequence[str | None]) -> dict:
    """Compara a categoria geral de duas combinações, repositório a repositório.

    Retorna `n_total`, `n_comparados` (classificados nas duas), `n_excluidos` (ausentes em
    alguma), `n_mudaram`, `prop_mudaram` (fração 0–1 sobre os comparados), `n_melhoraram`
    (categoria em `para` melhor que em `de`), `n_pioraram`, `n_adjacentes` (mudaram uma
    categoria, ex.: High → Medium), `n_saltos` (mudaram duas ou mais, ex.: Elite → Low) e
    `kappa_ponderado` (None se indefinido). Sem comparados, `prop_mudaram` e `kappa_ponderado` são None.
    """
    if len(de) != len(para):
        raise ValueError("as classificações devem ter o mesmo tamanho")
    for categoria in (*de, *para):
        _validar(categoria)
    pares = [(x, y) for x, y in zip(de, para) if not _ausente(x) and not _ausente(y)]
    mudaram = [(x, y) for x, y in pares if x != y]
    melhoraram = sum(1 for x, y in mudaram if PONTOS[y] > PONTOS[x])
    return {
        "n_total": len(de),
        "n_comparados": len(pares),
        "n_excluidos": len(de) - len(pares),
        "n_mudaram": len(mudaram),
        "prop_mudaram": len(mudaram) / len(pares) if pares else None,
        "n_melhoraram": melhoraram,
        "n_pioraram": len(mudaram) - melhoraram,
        "n_adjacentes": sum(1 for x, y in mudaram if abs(PONTOS[y] - PONTOS[x]) == 1),
        "n_saltos": sum(1 for x, y in mudaram if abs(PONTOS[y] - PONTOS[x]) >= 2),
        "kappa_ponderado": kappa_ponderado([x for x, _ in pares], [y for _, y in pares]),
    }
