"""Deployment frequency (RQ 01)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta


def releases_publicadas(
    releases: Iterable[dict],
    inicio: datetime,
    fim: datetime,
    incluir_prerelease: bool = False,
) -> list[dict]:
    """Releases que contam como deploy na janela [inicio, fim), na ordem recebida.

    Definição operacional (seção 3 do enunciado): `draft = false` e `published_at`
    dentro da janela. Pré-releases só entram com `incluir_prerelease=True` (variante da
    RQ 07). Também usada pelo critério de inclusão do funil (#5).
    """
    if fim <= inicio:
        raise ValueError("fim da janela deve ser posterior ao início")
    return [
        r
        for r in releases
        if not r["draft"]
        and (incluir_prerelease or not r["prerelease"])
        and r["published_at"] is not None
        and inicio <= r["published_at"] < fim
    ]


def deployment_frequency(
    releases: Iterable[dict],
    inicio: datetime,
    fim: datetime,
    incluir_prerelease: bool = False,
) -> float:
    """Releases publicadas por semana na janela [inicio, fim).

    Conta as releases de `releases_publicadas` (mesma definição de deploy).
    Retorna releases/semana; 0.0 quando não há releases na janela.
    """
    publicadas = releases_publicadas(releases, inicio, fim, incluir_prerelease)
    semanas = (fim - inicio) / timedelta(weeks=1)
    return len(publicadas) / semanas
