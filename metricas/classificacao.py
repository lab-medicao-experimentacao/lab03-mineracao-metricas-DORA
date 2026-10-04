"""Classificação DORA (Elite / High / Medium / Low) pela tabela de referência da disciplina.

Unidades esperadas: frequência em releases/semana, lead time e recuperação em horas,
CFR como fração entre 0 e 1.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable

CATEGORIAS = ("Low", "Medium", "High", "Elite")  # ordem crescente de desempenho
PONTOS = {categoria: pontos for pontos, categoria in enumerate(CATEGORIAS, start=1)}

# "1 por mês" convertido para releases/semana: 12 meses ÷ (365,25 / 7) semanas ≈ 0,23.
UMA_POR_MES_EM_SEMANAS = 12 / (365.25 / 7)

HORA = 1.0
DIA = 24 * HORA
SEMANA = 7 * DIA


def _frequencia(valor: float) -> str:
    if valor >= 7:
        return "Elite"
    if valor >= 1:
        return "High"
    if valor >= UMA_POR_MES_EM_SEMANAS:
        return "Medium"
    return "Low"


def _lead_time(horas: float) -> str:
    if horas < DIA:
        return "Elite"
    if horas < SEMANA:
        return "High"
    if horas < 30 * DIA:
        return "Medium"
    return "Low"


def _cfr(fracao: float) -> str:
    if fracao > 1:
        raise ValueError(f"CFR deve estar entre 0 e 1, recebido {fracao}")
    if fracao <= 0.15:
        return "Elite"
    if fracao <= 0.30:
        return "High"
    if fracao <= 0.45:
        return "Medium"
    return "Low"


def _recuperacao(horas: float) -> str:
    if horas < HORA:
        return "Elite"
    if horas < DIA:
        return "High"
    if horas < SEMANA:
        return "Medium"
    return "Low"


_CLASSIFICADORES = {
    "frequencia": _frequencia,
    "lead_time": _lead_time,
    "cfr": _cfr,
    "recuperacao": _recuperacao,
}


def classificar_metrica(nome: str, valor: float | None) -> str | None:
    """Categoria DORA de uma métrica; None quando o valor não pôde ser calculado."""
    if nome not in _CLASSIFICADORES:
        raise ValueError(f"métrica desconhecida: {nome!r}; use uma de {sorted(_CLASSIFICADORES)}")
    if valor is None:
        return None
    if valor < 0:
        raise ValueError(f"valor negativo para {nome}: {valor}")
    return _CLASSIFICADORES[nome](valor)


def classificacao_geral(categorias: Iterable[str | None]) -> str | None:
    """Mediana dos pontos (Elite=4 … Low=1), arredondada para baixo.

    Métricas sem valor (None) são ignoradas; retorna None se nenhuma tiver valor.
    """
    pontos = []
    for categoria in categorias:
        if categoria is None:
            continue
        if categoria not in PONTOS:
            raise ValueError(f"categoria inválida: {categoria!r}")
        pontos.append(PONTOS[categoria])
    if not pontos:
        return None
    return CATEGORIAS[math.floor(statistics.median(pontos)) - 1]


def classificar_repositorio(
    frequencia: float | None,
    lead_time: float | None,
    cfr: float | None,
    recuperacao: float | None,
) -> dict[str, str | None]:
    """Categoria de cada métrica e a classificação geral do repositório."""
    resultado = {
        "frequencia": classificar_metrica("frequencia", frequencia),
        "lead_time": classificar_metrica("lead_time", lead_time),
        "cfr": classificar_metrica("cfr", cfr),
        "recuperacao": classificar_metrica("recuperacao", recuperacao),
    }
    resultado["geral"] = classificacao_geral(resultado.values())
    return resultado
