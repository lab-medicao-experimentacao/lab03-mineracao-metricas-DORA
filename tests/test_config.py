from datetime import datetime, timezone

import pytest

from pipeline.config import ErroConfiguracao, FaixaEstrelas, carregar_config, ler_token


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
    ],
)
def test_config_invalido_gera_erro(escrever_config, substituicoes):
    with pytest.raises(ErroConfiguracao):
        carregar_config(escrever_config(substituicoes))


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
