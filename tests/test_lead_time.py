"""Exemplo numérico e casos de borda da RQ 02."""

from datetime import datetime, timezone

from metricas.lead_time import lead_time_por_commit, lead_time_por_release


def data(dia):
    return datetime(2025, 3, dia, tzinfo=timezone.utc)


def release(tag, dia, draft=False, prerelease=False):
    return {"tag_name": tag, "published_at": data(dia),
            "draft": draft, "prerelease": prerelease}


def commits(*dias):
    return [{"sha": str(dia), "author_date": data(dia), "message": "mudança"}
            for dia in dias]


def test_exemplo_do_enunciado_em_horas():
    releases = [release("v1.1", 15)]
    por_release = {"v1.1": commits(2, 10, 14)}

    assert lead_time_por_release(por_release, releases) == 13 * 24
    assert lead_time_por_commit(por_release, releases) == 5 * 24


def test_mediana_por_release_e_mediana_por_commit_pesam_diferente():
    releases = [release("v1.1", 15), release("v1.2", 20)]
    por_release = {"v1.1": commits(2, 10, 14), "v1.2": commits(19)}

    assert lead_time_por_release(por_release, releases) == 7 * 24
    assert lead_time_por_commit(por_release, releases) == 3 * 24


def test_primeira_release_sem_antecessora_e_release_sem_commits_sao_ignoradas():
    releases = [release("primeira", 1), release("v2", 15)]
    assert lead_time_por_release({"v2": []}, releases) is None
    assert lead_time_por_commit({"v2": []}, releases) is None


def test_draft_prerelease_e_compare_404_nao_contribuem():
    releases = [release("draft", 10, draft=True),
                release("rc", 11, prerelease=True), release("404", 12),
                release("ok", 15)]
    por_release = {"draft": commits(1), "rc": commits(1), "ok": commits(14)}

    assert lead_time_por_release(por_release, releases) == 24
    assert lead_time_por_commit(por_release, releases) == 24
