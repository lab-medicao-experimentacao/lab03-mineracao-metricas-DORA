from datetime import datetime, timedelta, timezone

import pytest

from metricas.frequencia import deployment_frequency

INICIO = datetime(2025, 10, 1, tzinfo=timezone.utc)
FIM = datetime(2026, 10, 1, tzinfo=timezone.utc)  # exclusivo; 365 dias
SEMANAS = 365 / 7


def release(publicada: datetime | None, draft: bool = False, prerelease: bool = False) -> dict:
    return {"tag_name": "v", "published_at": publicada, "draft": draft, "prerelease": prerelease}


def test_divide_releases_da_janela_pelas_semanas():
    releases = [release(INICIO + timedelta(days=d)) for d in range(0, 50, 10)]  # 5 releases
    assert deployment_frequency(releases, INICIO, FIM) == pytest.approx(5 / SEMANAS)


def test_janela_de_12_meses_tem_cerca_de_52_1_semanas():
    releases = [release(INICIO + timedelta(days=1))]
    assert 1 / deployment_frequency(releases, INICIO, FIM) == pytest.approx(52.1, abs=0.05)


def test_sem_releases_frequencia_zero():
    assert deployment_frequency([], INICIO, FIM) == 0.0


def test_ignora_drafts_e_prereleases():
    releases = [
        release(INICIO + timedelta(days=1)),
        release(INICIO + timedelta(days=2), prerelease=True),
        release(None, draft=True),  # drafts não têm published_at
        release(INICIO + timedelta(days=3), draft=True),
    ]
    assert deployment_frequency(releases, INICIO, FIM) == pytest.approx(1 / SEMANAS)


def test_variante_incluindo_prereleases():
    releases = [
        release(INICIO + timedelta(days=1)),
        release(INICIO + timedelta(days=2), prerelease=True),
    ]
    resultado = deployment_frequency(releases, INICIO, FIM, incluir_prerelease=True)
    assert resultado == pytest.approx(2 / SEMANAS)


def test_limites_da_janela_inicio_inclusivo_fim_exclusivo():
    releases = [
        release(INICIO),                               # entra
        release(FIM - timedelta(microseconds=1)),      # entra
        release(FIM),                                  # fora
        release(INICIO - timedelta(microseconds=1)),   # fora
    ]
    assert deployment_frequency(releases, INICIO, FIM) == pytest.approx(2 / SEMANAS)


def test_janela_invalida_gera_erro():
    with pytest.raises(ValueError):
        deployment_frequency([], FIM, INICIO)
