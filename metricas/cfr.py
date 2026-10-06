"""Change failure rate (RQ 03), variante (a): proxy de CI."""
from __future__ import annotations

from collections.abc import Iterable

from metricas import classe_conclusao


def cfr_ci(runs: Iterable[dict]) -> float | None:
    """Fração (0–1) de workflow runs com falha: falhas ÷ (falhas + sucessos).

    Classifica pelo `conclusion` (seção 3 do enunciado): `success` é sucesso;
    `failure`, `timed_out` e `startup_failure` são falhas; qualquer outro valor
    (cancelled, skipped, neutral, action_required, stale, None) é ignorado e não
    entra no numerador nem no denominador.

    Espera runs já restritos ao default branch, a `event = push` e à janela
    (ver `metricas.run_valido`). Retorna None quando não há nenhum run com
    sucesso ou falha (nunca 0 por padrão).
    """
    falhas = sucessos = 0
    for run in runs:
        classe = classe_conclusao(run["conclusion"])
        if classe == "falha":
            falhas += 1
        elif classe == "sucesso":
            sucessos += 1
    total = falhas + sucessos
    if total == 0:
        return None
    return falhas / total
