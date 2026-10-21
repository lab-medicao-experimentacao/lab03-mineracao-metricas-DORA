"""Testes do dataset final por repositório (#35); cenário calculado à mão."""

import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline import dataset
from pipeline.amostra_ouro import gravar_csv
from pipeline.config import Janela, carregar_config

JANELA = Janela(
    inicio=datetime(2025, 10, 1, tzinfo=timezone.utc),
    fim=datetime(2026, 10, 1, tzinfo=timezone.utc),
)
REPO = {
    "full_name": "org/exemplo", "default_branch": "main", "stars": "1500", "language": "Go",
    "created_at": "2020-01-01T00:00:00+00:00", "contributors": "12", "idade_dias": "2100",
}


def dt(texto: str) -> datetime:
    return datetime.fromisoformat(texto).astimezone(timezone.utc)


def release(tag, data, prerelease=False):
    return {"tag_name": tag, "published_at": dt(data), "draft": False, "prerelease": prerelease}


def commit(sha, data, mensagem):
    return {"sha": sha, "author_date": dt(data), "message": mensagem}


def run(id_, quando, conclusion, classe, branch="main", fim=None):
    return {
        "id": id_, "workflow_id": 1, "event": "push", "head_branch": branch,
        "conclusion": conclusion, "created_at": dt(quando), "run_started_at": dt(quando),
        "updated_at": dt(fim or quando), "classe": classe,
    }


@pytest.fixture
def releases():
    return [
        release("v1.0.0", "2025-09-20T12:00:00+00:00"),  # antes da janela
        release("v1.0.1", "2025-10-10T12:00:00+00:00"),
        release("v1.1.0", "2025-11-10T12:00:00+00:00"),
        release("v1.1.1", "2025-11-12T12:00:00+00:00"),
        release("v2.0.0-rc.1", "2026-01-01T12:00:00+00:00", prerelease=True),
        release("v1.2.0", "2026-03-01T12:00:00+00:00"),
        release("v1.3.0", "2026-09-28T12:00:00+00:00"),  # últimos 7 dias: censurada
    ]


@pytest.fixture
def commits():
    return {
        "v1.0.1": [commit("a", "2025-10-09T12:00:00+00:00", "feat: x")],            # 24 h
        "v1.1.0": [commit("b", "2025-11-08T12:00:00+00:00", "feat: y")],            # 48 h
        "v1.1.1": [commit("c", "2025-11-12T06:00:00+00:00", "fix: crash")],         # 6 h
        "v1.2.0": [commit("d", "2026-02-28T12:00:00+00:00", "feat: z"),             # 24 h
                   commit("e", "2026-02-26T12:00:00+00:00", "feat: w")],            # 72 h
    }


@pytest.fixture
def runs():
    return [
        run(1, "2025-10-05T10:00:00+00:00", "success", "sucesso"),
        run(2, "2025-10-06T10:00:00+00:00", "failure", "falha", fim="2025-10-06T10:05:00+00:00"),
        run(3, "2025-10-06T12:00:00+00:00", "success", "sucesso", fim="2025-10-06T12:30:00+00:00"),
        run(4, "2025-10-07T10:00:00+00:00", "cancelled", "ignorado"),
        run(5, "2025-10-08T10:00:00+00:00", "success", "sucesso", branch="dev"),  # fora do default
        run(6, "2026-09-29T10:00:00+00:00", "failure", "falha"),  # nunca recuperada
    ]


def calcular(releases, commits, runs, **extra):
    argumentos = {"sem_compare": Counter(), "n_meses_saturados": 0, "consenso": None} | extra
    return dataset.calcular_repositorio(
        REPO, releases, commits, runs, argumentos["sem_compare"],
        argumentos["n_meses_saturados"], JANELA, argumentos["consenso"])


def test_frequencia_conta_so_releases_principais_da_janela(releases, commits, runs):
    linha = calcular(releases, commits, runs)
    assert linha["n_releases"] == 5
    assert linha["n_prereleases"] == 1
    assert linha["frequencia_semana"] == pytest.approx(5 / (365 / 7))


def test_lead_time_nas_duas_variantes(releases, commits, runs):
    linha = calcular(releases, commits, runs)
    # (a) um valor por release (commit mais antigo): 24, 48, 6 e 72 h → mediana 36
    assert linha["lead_time_release_horas"] == pytest.approx(36)
    # (b) um valor por commit: 24, 48, 6, 24 e 72 h → mediana 24
    assert linha["lead_time_commit_horas"] == pytest.approx(24)
    assert linha["n_releases_lead_time"] == 4
    assert linha["n_commits_lead_time"] == 5


def test_cfr_de_entrega_com_censura(releases, commits, runs):
    linha = calcular(releases, commits, runs)
    # v1.1.0 falhou (v1.1.1 corretiva 2 dias depois); v1.3.0 é censurada
    assert linha["cfr_entrega"] == pytest.approx(0.25)
    assert (linha["n_releases_avaliadas"], linha["n_releases_falharam"],
            linha["n_releases_censuradas"]) == (4, 1, 1)


def test_cfr_de_ci_ignora_branch_errado_e_runs_ignorados(releases, commits, runs):
    linha = calcular(releases, commits, runs)
    assert linha["cfr_ci"] == pytest.approx(0.5)
    assert (linha["n_runs_validos"], linha["n_runs_sucesso"], linha["n_runs_falha"]) == (4, 2, 2)
    assert linha["n_runs_ignorados"] == 1


def test_recuperacao_inclui_episodio_censurado(releases, commits, runs):
    linha = calcular(releases, commits, runs)
    # episódios: 10:00 → 12:30 (2,5 h) e 29/09 10:00 → 01/10 00:00 (38 h, censurado)
    assert linha["recuperacao_mediana_horas"] == pytest.approx(20.25)
    assert linha["n_episodios_recuperacao"] == 2
    assert linha["prop_episodios_censurados"] == pytest.approx(0.5)


def test_classificacao_dora_da_combinacao_de_referencia(releases, commits, runs):
    linha = calcular(releases, commits, runs)
    assert [linha[c] for c in ("classe_frequencia", "classe_lead_time", "classe_cfr",
                               "classe_recuperacao", "classe_geral")] == [
        "Low", "High", "Low", "High", "Medium"]


def test_contagens_de_releases_ignoradas_e_metadados(releases, commits, runs):
    linha = calcular(
        releases, commits, runs, n_meses_saturados=2,
        sem_compare=Counter({"sem_anterior": 1, "compare_404": 2, "compare_422": 1}),
        consenso={"tipo_projeto": "biblioteca/framework", "entregas_reais": "sim"})
    assert (linha["n_releases_sem_anterior"], linha["n_releases_compare_404"],
            linha["n_releases_compare_outros"]) == (1, 2, 1)
    assert linha["n_meses_runs_saturados"] == 2
    assert (linha["tipo_projeto"], linha["entregas_reais"]) == ("biblioteca/framework", "sim")
    assert (linha["language"], linha["stars"], linha["idade_dias"]) == ("Go", "1500", "2100")


def test_sem_dados_suficientes_devolve_none_e_nao_zero():
    linha = calcular([release("v1.0.0", "2025-10-10T12:00:00+00:00")], {}, [])
    assert linha["lead_time_release_horas"] is None
    assert linha["cfr_ci"] is None
    assert linha["recuperacao_mediana_horas"] is None
    assert linha["classe_geral"] is None


# --- disco ------------------------------------------------------------------------------


def escrever(caminho, colunas, linhas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    gravar_csv(caminho, colunas, linhas)


@pytest.fixture
def ambiente(escrever_config, releases, commits, runs):
    config = carregar_config(escrever_config())
    escrever(config.dir_saida / "repos.csv", dataset.CABECALHOS["repos.csv"], [REPO])
    escrever(config.dir_processados / "releases.csv", dataset.CABECALHOS["releases.csv"], [
        {"full_name": REPO["full_name"], "tag_name": r["tag_name"],
         "published_at": r["published_at"].isoformat(), "draft": r["draft"],
         "prerelease": r["prerelease"]} for r in releases])
    escrever(config.dir_processados / "commits.csv", dataset.CABECALHOS["commits.csv"], [
        {"full_name": REPO["full_name"], "tag_name": tag, "sha": c["sha"],
         "author_date": c["author_date"].isoformat(), "message": c["message"]}
        for tag, lista in commits.items() for c in lista])
    escrever(config.dir_processados / "runs.csv", dataset.CABECALHOS["runs.csv"], [
        {"full_name": REPO["full_name"], "id": r["id"], "workflow_id": r["workflow_id"],
         "event": r["event"], "head_branch": r["head_branch"], "conclusion": r["conclusion"],
         "classe": r["classe"], "created_at": r["created_at"].isoformat(),
         "run_started_at": r["run_started_at"].isoformat(),
         "updated_at": r["updated_at"].isoformat()} for r in runs])
    escrever(config.dir_processados / "releases_sem_compare.csv",
             dataset.CABECALHOS["releases_sem_compare.csv"],
             [{"full_name": REPO["full_name"], "tag_name": "v1.3.0", "motivo": "compare_404"}])
    escrever(config.dir_processados / "runs_meses_saturados.csv",
             dataset.CABECALHOS["runs_meses_saturados.csv"], [])
    return config


def ler(caminho):
    with caminho.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_gera_csv_com_todas_as_colunas_do_dicionario(ambiente):
    caminho = dataset.gerar_dataset(ambiente)
    assert caminho == ambiente.dir_saida / dataset.ARQUIVO_DATASET
    with caminho.open(encoding="utf-8", newline="") as f:
        assert next(csv.reader(f)) == list(dataset.COLUNAS_DATASET)
    (linha,) = ler(caminho)
    assert linha["full_name"] == "org/exemplo"
    assert float(linha["lead_time_release_horas"]) == pytest.approx(36)
    assert linha["n_releases_compare_404"] == "1"
    assert linha["tipo_projeto"] == ""  # sem consenso_repos.csv
    assert linha["classe_geral"] == "Medium"


def test_consenso_da_amostra_ouro_preenche_tipo_do_projeto(ambiente):
    escrever(ambiente.dir_saida / "amostra_ouro" / "consenso_repos.csv",
             ("full_name", "tipo_projeto", "origem_tipo_projeto", "entregas_reais",
              "origem_entregas_reais"),
             [{"full_name": "org/exemplo", "tipo_projeto": "ferramenta CLI",
               "origem_tipo_projeto": "unanime", "entregas_reais": "sim",
               "origem_entregas_reais": "maioria"}])
    (linha,) = ler(dataset.gerar_dataset(ambiente))
    assert (linha["tipo_projeto"], linha["entregas_reais"]) == ("ferramenta CLI", "sim")


def test_repositorio_sem_commits_coletados_ainda_gera_linha(ambiente):
    (ambiente.dir_processados / "commits.csv").write_text(
        ",".join(dataset.CABECALHOS["commits.csv"]) + "\n", encoding="utf-8")
    (linha,) = ler(dataset.gerar_dataset(ambiente))
    assert linha["lead_time_release_horas"] == ""
    assert linha["n_releases"] == "5"


def test_erro_quando_repositorio_nao_tem_releases_ou_runs(ambiente):
    escrever(ambiente.dir_saida / "repos.csv", dataset.CABECALHOS["repos.csv"],
             [REPO, REPO | {"full_name": "org/outro"}])
    with pytest.raises(dataset.ErroDataset, match="org/outro"):
        dataset.gerar_dataset(ambiente)


def test_erro_quando_commits_de_um_repositorio_nao_sao_contiguos(ambiente):
    colunas = dataset.CABECALHOS["commits.csv"]

    def linha(nome, sha):
        return {"full_name": nome, "tag_name": "v1.1.0", "sha": sha,
                "author_date": "2025-11-08T12:00:00+00:00", "message": "feat"}

    escrever(ambiente.dir_processados / "commits.csv", colunas,
             [linha("org/exemplo", "1"), linha("org/outro", "2"), linha("org/exemplo", "3")])
    with pytest.raises(dataset.ErroDataset, match="não são contíguas"):
        dataset.gerar_dataset(ambiente)


def test_erro_com_cabecalho_inesperado(ambiente):
    (ambiente.dir_processados / "runs.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(dataset.ErroDataset, match="cabeçalho inválido"):
        dataset.gerar_dataset(ambiente)


def test_main_devolve_2_quando_a_entrada_esta_incompleta(escrever_config):
    caminho = escrever_config()
    assert dataset.main(["--config", str(caminho)]) == 2


def test_main_gera_o_arquivo(ambiente, tmp_path):
    assert dataset.main(["--config", str(tmp_path / "config.yaml")]) == 0
    assert (ambiente.dir_saida / dataset.ARQUIVO_DATASET).is_file()


def test_dicionario_de_dados_documenta_todas_as_colunas_do_dataset():
    texto = (Path(__file__).parents[2] / "output" / "dicionario_dados.md").read_text(encoding="utf-8")
    assert [c for c in dataset.COLUNAS_DATASET if f"`{c}`" not in texto] == []
