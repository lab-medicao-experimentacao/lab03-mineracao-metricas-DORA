from datetime import datetime, timezone

import pytest

import os

from pipeline.config import (
    MAX_WORKERS,
    WORKERS_PADRAO,
    ErroConfiguracao,
    FaixaEstrelas,
    carregar_config,
    carregar_dotenv,
    ler_token,
)


def test_carrega_config_valido(escrever_config):
    config = carregar_config(escrever_config())

    assert config.janela.inicio == datetime(2025, 10, 1, tzinfo=timezone.utc)
    assert config.janela.fim == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert config.faixas_estrelas == (FaixaEstrelas(1000, 1999), FaixaEstrelas(2000, None))
    assert (config.min_releases, config.min_runs) == (5, 50)
    assert (config.tamanho_amostra, config.semente) == (100, 42)


def test_janela_de_12_meses_tem_cerca_de_52_semanas(escrever_config):
    janela = carregar_config(escrever_config()).janela
    assert janela.semanas == pytest.approx(365 / 7)


def test_janela_inclui_ultimo_dia_e_exclui_dia_seguinte(escrever_config):
    janela = carregar_config(escrever_config()).janela
    assert janela.contem(datetime(2025, 10, 1, 0, 0, tzinfo=timezone.utc))
    assert janela.contem(datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc))
    assert not janela.contem(datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc))
    assert not janela.contem(datetime(2025, 9, 30, 23, 59, 59, tzinfo=timezone.utc))


def test_filtro_created_usa_datas_inclusivas(escrever_config):
    janela = carregar_config(escrever_config()).janela
    assert janela.filtro_created() == "2025-10-01..2026-09-30"


@pytest.mark.parametrize(
    "faixa, esperado",
    [(FaixaEstrelas(1000, 1499), "stars:1000..1499"), (FaixaEstrelas(50000, None), "stars:>=50000")],
)
def test_consulta_da_faixa_de_estrelas(faixa, esperado):
    assert faixa.consulta() == esperado


@pytest.mark.parametrize(
    "substituicoes",
    [
        {"fim: 2026-09-30": "fim: 2025-09-01"},                     # fim antes do início
        {"fim: 2026-09-30": "fim: 30/09/2026"},                     # formato de data inválido
        {"{min: 2000, max: null}": "{min: 1500, max: null}"},       # faixas sobrepostas
        {"{min: 1000, max: 1999}": "{min: 1000, max: 900}"},        # max < min
        {"min_runs: 50": "min_runs: 0"},                            # limite não positivo
        {"  semente: 42\n": ""},                                    # chave obrigatória ausente
        {"fim: 2026-09-30": "fim: 2026-02-30"},                     # data impossível (erro no PyYAML)
        {"janela:": "janela: [\n"},                                 # YAML inválido
        {"  inicio: 2025-10-01\n  fim: 2026-09-30\n": ""},          # seção vazia (não é mapeamento)
        {"min_releases: 5": "min_releases: cinco"},                 # inteiro inválido
        {"min_releases: 5": "min_releases: 5.5"},                   # inteiro não exato
        {"semente: 42": "semente: true"},                           # booleano no lugar de inteiro
        {"excluir_forks: true": "excluir_forks: 'false'"},          # string no lugar de booleano
        {"{min: 2000, max: null}": "{min: 2500, max: null}"},       # lacuna entre faixas
        {"{min: 2000, max: null}": "{min: 2000}"},                  # max ausente (use null explícito)
        {"{min: 1000, max: 1999}": "{min: -1, max: 1999}"},         # min negativo
        {"    - {min: 1000, max: 1999}\n    - {min: 2000, max: null}\n": ""},  # lista de faixas nula
        {"  faixas_estrelas:\n    - {min: 1000, max: 1999}\n    - {min: 2000, max: null}\n": "  faixas_estrelas: []\n"},  # lista vazia
    ],
)
def test_config_invalido_gera_erro(escrever_config, substituicoes):
    with pytest.raises(ErroConfiguracao):
        carregar_config(escrever_config(substituicoes))


def test_workers_ausente_usa_o_padrao(escrever_config):
    assert carregar_config(escrever_config()).workers == WORKERS_PADRAO == 4


@pytest.mark.parametrize("valor", [1, 4, 8])
def test_workers_lido_da_secao_coleta(escrever_config, valor):
    config = carregar_config(escrever_config({"caminhos:": f"coleta:\n  workers: {valor}\ncaminhos:"}))
    assert config.workers == valor


@pytest.mark.parametrize("valor", ["0", "-1", f"{MAX_WORKERS + 1}", "dois", "true", "2.5"])
def test_workers_invalido_gera_erro(escrever_config, valor):
    with pytest.raises(ErroConfiguracao):
        carregar_config(escrever_config({"caminhos:": f"coleta:\n  workers: {valor}\ncaminhos:"}))


def test_secao_coleta_que_nao_e_mapeamento_gera_erro(escrever_config):
    with pytest.raises(ErroConfiguracao):
        carregar_config(escrever_config({"caminhos:": "coleta: 4\ncaminhos:"}))


def test_config_que_nao_e_mapeamento_gera_erro(tmp_path):
    caminho = tmp_path / "config.yaml"
    caminho.write_text("- uma\n- lista\n", encoding="utf-8")
    with pytest.raises(ErroConfiguracao):
        carregar_config(caminho)


def test_arquivo_inexistente_gera_erro(tmp_path):
    with pytest.raises(ErroConfiguracao):
        carregar_config(tmp_path / "nao_existe.yaml")


def test_ler_token_da_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "  abc123  ")
    assert ler_token() == "abc123"


def test_ler_token_ausente_gera_erro(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ErroConfiguracao):
        ler_token()


# --- .env (lido sem dependência nova; a variável de ambiente tem precedência) ---------


@pytest.fixture
def ambiente(monkeypatch):
    """Cópia isolada de os.environ: o que o .env definir some ao fim do teste."""
    copia = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "OUTRA")}
    monkeypatch.setattr(os, "environ", copia)
    return copia


def test_carregar_dotenv_define_variaveis_ausentes(tmp_path, ambiente):
    (tmp_path / ".env").write_text(
        '# comentário\n\nexport GITHUB_TOKEN="ghp_do_arquivo"\nOUTRA = valor # nota\n',
        encoding="utf-8",
    )
    assert carregar_dotenv(tmp_path / ".env") == {"GITHUB_TOKEN", "OUTRA"}
    assert ler_token() == "ghp_do_arquivo"
    assert ambiente["OUTRA"] == "valor"


def test_carregar_dotenv_nao_sobrescreve_variavel_ja_definida(tmp_path, ambiente):
    ambiente["GITHUB_TOKEN"] = "do_ambiente"
    (tmp_path / ".env").write_text("GITHUB_TOKEN=do_arquivo\n", encoding="utf-8")
    assert carregar_dotenv(tmp_path / ".env") == set()
    assert ler_token() == "do_ambiente"


def test_carregar_dotenv_sem_arquivo_nao_faz_nada(tmp_path, ambiente):
    assert carregar_dotenv(tmp_path / ".env") == set()
    assert "GITHUB_TOKEN" not in ambiente


def test_carregar_dotenv_aceita_aspas_simples_bom_e_crlf(tmp_path, ambiente):
    (tmp_path / ".env").write_bytes("﻿GITHUB_TOKEN='abc#1'\r\nlinha sem igual\r\n".encode("utf-8"))
    assert carregar_dotenv(tmp_path / ".env") == {"GITHUB_TOKEN"}
    assert ler_token() == "abc#1"
