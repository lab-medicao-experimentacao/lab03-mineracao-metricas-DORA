"""Deployment frequency (RQ 01)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta


def deployment_frequency(
    releases: Iterable[dict],
    inicio: datetime,
    fim: datetime,
    incluir_prerelease: bool = False,
) -> float:
    """Releases publicadas por semana na janela [inicio, fim).

    Conta releases com `draft = false` e `published_at` dentro da janela. Pré-releases
    só entram com `incluir_prerelease=True` (variante da RQ 07).
    Retorna releases/semana; 0.0 quando não há releases na janela.
    """
    if fim <= inicio:
        raise ValueError("fim da janela deve ser posterior ao início")

    publicadas = sum(
        1
        for r in releases
        if not r["draft"]
        and (incluir_prerelease or not r["prerelease"])
        and r["published_at"] is not None
        and inicio <= r["published_at"] < fim
    )
    semanas = (fim - inicio) / timedelta(weeks=1)
    return publicadas / semanas
