"""Fixtures sintéticas da variante de entrega (#28); sem amostra-ouro."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from metricas.cfr import cfr_entrega, release_corretiva


BASE = datetime(2026, 5, 1, tzinfo=timezone.utc)
FIM = datetime(2026, 7, 1, tzinfo=timezone.utc)


def release(tag, dia, **campos):
    return {"tag_name": tag, "published_at": BASE + timedelta(days=dia),
            "draft": False, "prerelease": False, **campos}


@pytest.mark.parametrize("anterior, atual, esperado", [
    ("v2.3.0", "v2.3.1", True),
    ("2.3.0", "2.3.2", True),
    ("v2.3.0+old", "2.3.1+build.2", True),
    ("v2.4.0", "v2.5.0", False),
    ("v2.3.1", "v2.3.0", False),
    ("v2.3.1", "v2.3.1", False),
    ("v2.3.0", "v3.3.1", False),
    ("v2.3.0", "v2.3.1-rc.1", False),
    ("v02.3.0", "v02.3.1", False),
    ("package@2.3.0", "package@2.3.1", False),
    ("v2.3.0", "v2.3.1+", False),
    ("v2.3", "v2.3.1", False),
])
def test_versoes(anterior, atual, esperado):
    assert release_corretiva(release(atual, 2), release(anterior, 0), []) is esperado


@pytest.mark.parametrize("mensagem", [
    "fix: crash ao abrir arquivo", "Revert change", "HOTFIX: timeout",
    "feat: novo comando\n\nfix(parser): erro de leitura",
])
def test_mensagem_corretiva_independe_da_versao(mensagem):
    assert release_corretiva(release("release-b", 2), None, [{"message": mensagem}])


@pytest.mark.parametrize("mensagem", ["prefix: exemplo", "fixture nova", "feat: add feature", ""])
def test_nao_confunde_substrings(mensagem):
    assert not release_corretiva(release("release-b", 2), None, [{"message": mensagem}])


def test_sem_anterior_ou_commits_nao_inventa_correcao():
    assert not release_corretiva(release("v2.3.1", 2), None, [])


@pytest.mark.parametrize("campo", ["draft", "prerelease"])
def test_release_nao_publicada_nao_e_corretiva(campo):
    assert not release_corretiva(release("v2.3.1", 2, **{campo: True}),
                                 release("v2.3.0", 0), [{"message": "fix: crash"}])


def test_release_sem_data_nao_e_corretiva():
    assert not release_corretiva(release("v2.3.1", 2, published_at=None),
                                 release("v2.3.0", 0), [])


def test_exemplos_do_enunciado():
    releases = [release("v2.3.0", 9), release("v2.3.1", 11),
                release("v2.4.0", 31), release("v2.5.0", 50)]
    assert cfr_entrega(releases, {"v2.3.1": [{"message": "fix: crash"}]}, FIM) == {
        "cfr": 0.25, "n_avaliadas": 4, "n_falharam": 1, "n_censuradas": 0,
    }


@pytest.mark.parametrize("intervalo, falhou", [
    (timedelta(days=7), 1),
    (timedelta(days=7, microseconds=1), 0),
    (timedelta(0), 0),
])
def test_limite_de_sete_dias_e_publicacao_posterior(intervalo, falhou):
    releases = [release("v1.0.0", 0),
                release("v1.0.1", 0, published_at=BASE + intervalo)]
    assert cfr_entrega(releases, {}, FIM)["n_falharam"] == falhou


def test_censura_inclui_inicio_dos_ultimos_sete_dias_mesmo_com_correcao():
    limite = FIM - timedelta(days=7)
    releases = [release("v1.0.0", 0, published_at=limite - timedelta(microseconds=1)),
                release("v2.0.0", 0, published_at=limite),
                release("v2.0.1", 0, published_at=FIM - timedelta(days=1))]
    assert cfr_entrega(releases, {}, FIM) == {
        "cfr": 1.0, "n_avaliadas": 1, "n_falharam": 1, "n_censuradas": 2,
    }


@pytest.mark.parametrize("releases, censuradas", [([], 0), ([release("v1.0.0", 60)], 1)])
def test_sem_avaliaveis_retorna_none(releases, censuradas):
    assert cfr_entrega(releases, {}, FIM) == {
        "cfr": None, "n_avaliadas": 0, "n_falharam": 0, "n_censuradas": censuradas,
    }


def test_ultima_release_com_observacao_completa_e_avaliada():
    assert cfr_entrega([release("v1.0.0", 0)], {}, FIM) == {
        "cfr": 0.0, "n_avaliadas": 1, "n_falharam": 0, "n_censuradas": 0,
    }


def test_ignora_drafts_prereleases_sem_data_e_releases_no_fim_ou_depois():
    releases = [release("v1.0.0", 0), release("v1.0.1", 2, draft=True),
                release("v1.0.2", 3, prerelease=True),
                release("v1.0.3", 4, published_at=None),
                release("v1.0.4", 61), release("v1.0.5", 62)]
    assert cfr_entrega(releases, {}, FIM) == cfr_entrega(releases[:1], {}, FIM)


def test_corretiva_apos_release_intermediaria_tambem_conta():
    releases = [release("v1.0.0", 0), release("v2.0.0", 2), release("v2.0.1", 3)]
    assert cfr_entrega(releases, {}, FIM)["n_falharam"] == 2


def test_varias_corretivas_contam_cada_release_uma_vez():
    releases = [release("v1.0.0", 0), release("v1.0.1", 1), release("v1.0.2", 2)]
    assert cfr_entrega(releases, {}, FIM)["n_falharam"] == 2


def test_ordem_da_entrada_nao_importa_e_nao_muta_dados():
    releases = [release("v1.0.1", 2), release("v1.0.0", 0)]
    commits = {"v1.0.1": [{"message": "fix: crash"}]}
    copia = deepcopy((releases, commits))
    assert cfr_entrega(releases, commits, FIM) == cfr_entrega(list(reversed(releases)), commits, FIM)
    assert (releases, commits) == copia


def test_empate_de_data_e_desempatado_por_tag():
    releases = [release("v1.0.1", 2), release("v1.0.0", 0), release("v1.1.0", 2)]
    assert cfr_entrega(releases, {}, FIM) == cfr_entrega(list(reversed(releases)), {}, FIM)
