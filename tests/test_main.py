from pipeline.__main__ import main


def test_main_executa_com_config_e_token(escrever_config, monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "token-de-teste")
    assert main(["--config", str(escrever_config())]) == 0
    assert (tmp_path / "cache").is_dir()
    assert (tmp_path / "output").is_dir()


def test_main_falha_sem_token(escrever_config, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main(["--config", str(escrever_config())]) == 2


def test_main_falha_com_config_inexistente(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "token-de-teste")
    assert main(["--config", str(tmp_path / "x.yaml")]) == 2
