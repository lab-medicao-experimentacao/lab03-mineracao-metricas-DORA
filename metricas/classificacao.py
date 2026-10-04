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

# Cortes da tabela de referência (enunciado, RQ 07), do melhor para o pior desempenho.
FREQUENCIA_ELITE = 7.0                   # ≥ 7 releases/semana
FREQUENCIA_HIGH = 1.0                    # ≥ 1 release/semana
FREQUENCIA_MEDIUM = UMA_POR_MES_EM_SEMANAS
LEAD_TIME_ELITE = DIA                    # < 1 dia
LEAD_TIME_HIGH = SEMANA                  # < 1 semana
LEAD_TIME_MEDIUM = 30 * DIA              # < 30 dias
CFR_ELITE = 0.15                         # ≤ 15 %
CFR_HIGH = 0.30                          # ≤ 30 %
CFR_MEDIUM = 0.45                        # ≤ 45 %
RECUPERACAO_ELITE = HORA                 # < 1 hora
RECUPERACAO_HIGH = DIA                   # < 1 dia
RECUPERACAO_MEDIUM = SEMANA              # < 1 semana


def _frequencia(valor: float) -> str:
    if valor >= FREQUENCIA_ELITE:
        return "Elite"
    if valor >= FREQUENCIA_HIGH:
        return "High"
    if valor >= FREQUENCIA_MEDIUM:
        return "Medium"
    return "Low"


def _lead_time(horas: float) -> str:
    if horas < LEAD_TIME_ELITE:
        return "Elite"
    if horas < LEAD_TIME_HIGH:
        return "High"
    if horas < LEAD_TIME_MEDIUM:
        return "Medium"
    return "Low"


def _cfr(fracao: float) -> str:
    if fracao > 1:
        raise ValueError(f"CFR deve estar entre 0 e 1, recebido {fracao}")
    if fracao <= CFR_ELITE:
        return "Elite"
    if fracao <= CFR_HIGH:
        return "High"
    if fracao <= CFR_MEDIUM:
        return "Medium"
    return "Low"


def _recuperacao(horas: float) -> str:
    if horas < RECUPERACAO_ELITE:
        return "Elite"
    if horas < RECUPERACAO_HIGH:
        return "High"
    if horas < RECUPERACAO_MEDIUM:
        return "Medium"
    return "Low"


_CLASSIFICADORES = {
    "frequencia": _frequencia,
    "lead_time": _lead_time,
    "cfr": _cfr,
    "recuperacao": _recuperacao,
}


def classificar_metrica(nome: str, valor: float | None) -> str | None:
    """Categoria DORA de uma métrica; None quando o valor não pôde ser calculado.

    NaN (valor ausente vindo do pandas) é tratado como None.
    """
    if nome not in _CLASSIFICADORES:
        raise ValueError(f"métrica desconhecida: {nome!r}; use uma de {sorted(_CLASSIFICADORES)}")
    if valor is None or math.isnan(valor):
        return None
    if math.isinf(valor):
        raise ValueError(f"valor infinito para {nome}: {valor}")
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
