"""Lead time for changes (RQ 02), calculado sem rede ou disco (#11)."""

from __future__ import annotations

from statistics import median


def _pares_validos(
    commits_por_release: dict[str, list[dict]], releases: list[dict]
) -> list[tuple[dict, list[dict]]]:
    """Releases principais com comparação válida e ao menos um commit novo."""
    return [
        (release, commits_por_release[release["tag_name"]])
        for release in releases
        if not release["draft"]
        and not release["prerelease"]
        and release["published_at"] is not None
        and commits_por_release.get(release["tag_name"])
    ]


def lead_time_por_release(
    commits_por_release: dict[str, list[dict]], releases: list[dict]
) -> float | None:
    """Mediana, em horas, do tempo do commit mais antigo até cada release."""
    valores = [
        (release["published_at"] - min(c["author_date"] for c in commits)).total_seconds() / 3600
        for release, commits in _pares_validos(commits_por_release, releases)
    ]
    return float(median(valores)) if valores else None


def lead_time_por_commit(
    commits_por_release: dict[str, list[dict]], releases: list[dict]
) -> float | None:
    """Mediana, em horas, dos tempos de todos os commits incluídos nas releases."""
    valores = [
        (release["published_at"] - commit["author_date"]).total_seconds() / 3600
        for release, commits in _pares_validos(commits_por_release, releases)
        for commit in commits
    ]
    return float(median(valores)) if valores else None
