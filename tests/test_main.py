import csv
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import pipeline.__main__ as entrada
from pipeline import commits, funil, metadados, releases, selecao, workflow_runs
from pipeline.__main__ import executar, main
from pipeline.commits import ResultadoCommits
from pipeline.config import carregar_config
from pipeline.workflow_runs import ResultadoRuns

DENTRO = datetime(2025, 11, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def pasta_sem_env(tmp_path, monkeypatch):
    """Roda cada teste numa pasta vazia: um .env real do repositório nunca é lido."""
    monkeypatch.chdir(tmp_path)


def test_main_le_token_do_dotenv(escrever_config, monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    (tmp_path / ".env").write_text("GITHUB_TOKEN=token-do-arquivo\n", encoding="utf-8")
    tokens = []
    monkeypatch.setattr(entrada, "GitHubClient", lambda token, cache: tokens.append(token) or object())
    monkeypatch.setattr(entrada, "executar", lambda cliente, config, avaliar_todos: None)
    try:
        assert main(["--config", str(escrever_config())]) == 0
    finally:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert tokens == ["token-do-arquivo"]


def test_main_ctrl_c_avisa_que_basta_rodar_de_novo(escrever_config, monkeypatch, caplog):
    monkeypatch.setenv("GITHUB_TOKEN", "token-de-teste")

    def interrompe(cliente, config, avaliar_todos):
        raise KeyboardInterrupt

    monkeypatch.setattr(entrada, "executar", interrompe)
    assert main(["--config", str(escrever_config())]) == 130
    assert "rode o mesmo comando" in caplog.text


def test_main_executa_com_config_e_token(escrever_config, monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "token-de-teste")
    chamadas = []
    monkeypatch.setattr(entrada, "executar", lambda cliente, config, avaliar_todos: chamadas.append(avaliar_todos))
    assert main(["--config", str(escrever_config())]) == 0
    assert chamadas == [False]
    assert (tmp_path / "cache").is_dir()
    assert (tmp_path / "output").is_dir()


def test_main_repassa_funil_completo(escrever_config, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token-de-teste")
    chamadas = []
    monkeypatch.setattr(entrada, "executar", lambda cliente, config, avaliar_todos: chamadas.append(avaliar_todos))
    assert main(["--config", str(escrever_config()), "--funil-completo"]) == 0
    assert chamadas == [True]


def test_main_falha_sem_token(escrever_config, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main(["--config", str(escrever_config())]) == 2


def test_main_falha_com_config_inexistente(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "token-de-teste")
    assert main(["--config", str(tmp_path / "x.yaml")]) == 2


# --- executar: coletores trocados por fakes (sem rede) ---------------------------


def _repo(nome: str) -> dict:
    return {
        "full_name": nome, "default_branch": "main", "stars": 1500, "language": "Python",
        "created_at": DENTRO - timedelta(days=1000), "fork": False, "archived": False,
    }


def _run(i: int) -> dict:
    return {
        "id": i, "workflow_id": 1, "event": "push", "head_branch": "main",
        "conclusion": "success", "created_at": DENTRO, "run_started_at": DENTRO, "updated_at": DENTRO,
    }


@pytest.fixture
def coleta_falsa(monkeypatch):
    """Três candidatos: `o/sem-actions` cai na etapa 3; `o/a` e `o/b` são elegíveis."""
    chamadas = {"runs": [], "tags": [], "commits": []}
    monkeypatch.setattr(selecao, "buscar_candidatos", lambda cliente, faixas: [
        _repo("o/a"), _repo("o/b"), _repo("o/sem-actions"),
    ])
    monkeypatch.setattr(funil, "usa_github_actions", lambda cliente, nome: nome != "o/sem-actions")
    monkeypatch.setattr(funil, "coletar_releases", lambda cliente, nome: [
        {"tag_name": f"v{i}", "published_at": DENTRO + timedelta(days=i), "draft": False, "prerelease": False}
        for i in range(5)
    ])

    def runs(cliente, nome, branch, janela):
        chamadas["runs"].append(nome)
        return ResultadoRuns([_run(i) for i in range(50)], ("2025-11-01..2025-11-30",) if nome == "o/b" else ())

    monkeypatch.setattr(workflow_runs, "coletar_runs", runs)
    monkeypatch.setattr(metadados, "coletar_contribuidores", lambda cliente, nome: 7)

    def tags(cliente, nome):
        chamadas["tags"].append(nome)
        return [{"tag_name": "v0", "commit_sha": "abc", "commit_date": DENTRO}]

    monkeypatch.setattr(releases, "coletar_tags", tags)

    def commits_entre(cliente, nome, rels, janela):
        chamadas["commits"].append((nome, len(rels)))
        commit = {"sha": "abc", "author_date": DENTRO, "message": "m"}
        return ResultadoCommits({"v1": [commit]}, ("v0",), ())

    monkeypatch.setattr(commits, "coletar_commits_entre_releases", commits_entre)
    return chamadas


def _linhas(caminho) -> list[dict]:
    with caminho.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_executar_grava_todos_os_artefatos_da_amostra(escrever_config, coleta_falsa, caplog):
    config = carregar_config(escrever_config())

    executar(object(), config)

    saida, processados = config.dir_saida, config.dir_processados
    assert len(_linhas(saida / "candidatos.csv")) == 3
    funil_csv = _linhas(saida / "funil.csv")
    assert funil_csv[-1]["n_restantes"] == "2"
    repos = _linhas(saida / "repos.csv")
    assert sorted(r["full_name"] for r in repos) == ["o/a", "o/b"]
    assert {r["contributors"] for r in repos} == {"7"}
    assert len(_linhas(processados / "releases.csv")) == 10
    assert len(_linhas(processados / "tags.csv")) == 2
    assert len(_linhas(processados / "commits.csv")) == 2
    assert len(_linhas(processados / "runs.csv")) == 100
    assert [(l["full_name"], l["periodo"]) for l in _linhas(processados / "runs_meses_saturados.csv")] == [
        ("o/b", "2025-11-01..2025-11-30"),
    ]
    assert sorted((l["full_name"], l["motivo"]) for l in _linhas(processados / "releases_sem_compare.csv")) == [
        ("o/a", "sem_anterior"), ("o/b", "sem_anterior"),
    ]
    assert sorted(coleta_falsa["tags"]) == ["o/a", "o/b"]
    assert sorted(coleta_falsa["commits"]) == [("o/a", 5), ("o/b", 5)]
    assert "o/sem-actions" not in coleta_falsa["runs"]
    assert "teto de 1.000 runs: o/b" in caplog.text


def test_executar_amostra_limitada_pelo_tamanho(escrever_config, coleta_falsa):
    config = replace(carregar_config(escrever_config()), tamanho_amostra=1)

    executar(object(), config)

    assert len(_linhas(config.dir_saida / "repos.csv")) == 1
    assert len(_linhas(config.dir_processados / "runs.csv")) == 50
