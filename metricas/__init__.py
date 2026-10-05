"""Cálculo puro das métricas DORA (sem rede, sem disco).

Constantes compartilhadas pelas definições operacionais (seção 3 do enunciado).
"""

from __future__ import annotations

from datetime import datetime

# Classificação do campo `conclusion` de um workflow run.
CONCLUSOES_SUCESSO = frozenset({"success"})
CONCLUSOES_FALHA = frozenset({"failure", "timed_out", "startup_failure"})
# Qualquer outro valor (cancelled, skipped, neutral, action_required, stale, None) é ignorado.

# Só runs disparados por push representam mudanças entregues (schedule, manual etc. ficam de fora).
EVENTO_RUN_VALIDO = "push"


def classe_conclusao(conclusion: str | None) -> str:
    """Retorna 'sucesso', 'falha' ou 'ignorado' para um `conclusion` da API."""
    if conclusion in CONCLUSOES_SUCESSO:
        return "sucesso"
    if conclusion in CONCLUSOES_FALHA:
        return "falha"
    return "ignorado"


def run_valido(run: dict, default_branch: str, inicio: datetime, fim: datetime) -> bool:
    """True se o run (contrato Run) conta nas métricas de CI e no critério de inclusão.

    Válido = `event = push`, `head_branch` igual ao default branch do repositório,
    `conclusion` classificado como sucesso ou falha e `created_at` em [inicio, fim).
    """
    return (
        run["event"] == EVENTO_RUN_VALIDO
        and run["head_branch"] == default_branch
        and classe_conclusao(run["conclusion"]) != "ignorado"
        and inicio <= run["created_at"] < fim
    )
