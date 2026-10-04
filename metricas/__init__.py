"""Cálculo puro das métricas DORA (sem rede, sem disco).

Constantes compartilhadas pelas definições operacionais (seção 3 do enunciado).
"""

# Classificação do campo `conclusion` de um workflow run.
CONCLUSOES_SUCESSO = frozenset({"success"})
CONCLUSOES_FALHA = frozenset({"failure", "timed_out", "startup_failure"})
# Qualquer outro valor (cancelled, skipped, neutral, action_required, stale, None) é ignorado.


def classe_conclusao(conclusion: str | None) -> str:
    """Retorna 'sucesso', 'falha' ou 'ignorado' para um `conclusion` da API."""
    if conclusion in CONCLUSOES_SUCESSO:
        return "sucesso"
    if conclusion in CONCLUSOES_FALHA:
        return "falha"
    return "ignorado"
