"""Fixtures sintéticas: nunca usam API, amostra-ouro ou o dataset real."""

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from analises.rq05 import COLUNAS_PADRAO, analisar_dados, executar, main


def tabela(x=(1, 2, 3, 4, 5), ci=(0, 0.25, 0.5, 1, 0.75), entrega=None):
    return pd.DataFrame({
        "full_name": [f"teste/repo{i}" for i in range(len(x))],
        "deployment_frequency": x, "cfr_ci": ci,
        "cfr_entrega": entrega if entrega is not None else ci,
    })


def test_resultado_conhecido_sem_alterar_entrada():
    dados = tabela(entrega=(1, 0.75, 0.5, 0, 0.25))
    original = dados.copy(deep=True)
    resumo, pares, exclusoes = analisar_dados(dados)
    assert resumo["rho"].tolist() == pytest.approx([0.9, -0.9])
    assert resumo["p_valor"].tolist() == pytest.approx([0.03738607346849874] * 2)
    assert resumo["n"].tolist() == [5, 5]
    assert len(pares) == 10
    assert exclusoes.empty
    pd.testing.assert_frame_equal(dados, original)


def test_empates_com_exemplo_publicado_scipy():
    # Exemplo oficial; dividir y por 10 mantém os postos e expressa fração.
    resumo, _, _ = analisar_dados(tabela(
        x=(7.1, 7.1, 7.2, 8.3, 9.4, 10.5, 11.4),
        ci=(0.28, 0.29, 0.28, 0.26, 0.35, 0.46, 0.50),
    ))
    assert resumo.iloc[0]["rho"] == pytest.approx(0.7)
    assert resumo.iloc[0]["p_valor"] == pytest.approx(0.07991669030889909)


def test_ausencias_sao_excluidas_por_variante_com_motivos():
    resumo, pares, exclusoes = analisar_dados(tabela(
        x=(0, 1, 2, None, 4), ci=(0, None, 0.5, 0.75, 1),
        entrega=(1, 0.75, 0.5, None, None),
    ))
    assert resumo["n"].tolist() == [3, 3]
    assert resumo["n_excluidos"].tolist() == [2, 2]
    assert resumo["n_sem_frequencia"].tolist() == [1, 1]
    assert resumo["n_sem_cfr"].tolist() == [1, 2]
    assert set(pares.loc[pares.variante == "cfr_ci", "full_name"]) == {
        "teste/repo0", "teste/repo2", "teste/repo4",
    }
    assert set(exclusoes.motivo) == {"sem_cfr", "sem_frequencia", "sem_frequencia;sem_cfr"}
    assert resumo["rho"].tolist() == pytest.approx([1, -1])


@pytest.mark.parametrize("x,ci,situacao", [
    ((), (), "pares_insuficientes"),
    ((1,), (0,), "pares_insuficientes"),
    ((1, 2), (0, 1), "pares_insuficientes"),
    ((1, 1, 1), (0, 0.5, 1), "variavel_constante"),
    ((1, 2, 3), (0, 0, 0), "variavel_constante"),
    ((None, None, None), (0, 0.5, 1), "pares_insuficientes"),
])
def test_indefinidos_sem_coeficiente_inventado(x, ci, situacao):
    resumo, _, _ = analisar_dados(tabela(x, ci))
    assert resumo.situacao.tolist() == [situacao, situacao]
    assert resumo.rho.isna().all()
    assert resumo.p_valor.isna().all()


@pytest.mark.parametrize("coluna,valor", [
    ("deployment_frequency", -1), ("deployment_frequency", float("inf")),
    ("deployment_frequency", "abc"), ("cfr_ci", 20), ("cfr_ci", -0.1),
    ("cfr_entrega", float("-inf")), ("cfr_entrega", "inválido"),
])
def test_dados_invalidos_sao_erros(coluna, valor):
    dados = tabela().astype(object)
    dados.loc[0, coluna] = valor
    with pytest.raises(ValueError, match=coluna):
        analisar_dados(dados)


@pytest.mark.parametrize("nome", ["", " ", None, "teste/repo1"])
def test_identificadores_invalidos_ou_duplicados(nome):
    dados = tabela()
    dados.loc[0, "full_name"] = nome
    with pytest.raises(ValueError, match="identificador"):
        analisar_dados(dados)


def test_colunas_customizadas_e_linhas_reordenadas():
    dados = tabela()
    esperado = analisar_dados(dados)
    customizadas = ("repo", "freq", "a", "b")
    dados.columns = customizadas
    obtido = analisar_dados(dados.iloc[::-1], customizadas)
    for x, y in zip(esperado, obtido):
        pd.testing.assert_frame_equal(x, y)
    with pytest.raises(ValueError, match="ausentes"):
        analisar_dados(dados)
    with pytest.raises(ValueError, match="distintas"):
        analisar_dados(dados, ("repo",) * 4)


def test_execucao_offline_reproduz_csv_relatorio_e_png(tmp_path):
    entrada, saida = tmp_path / "entrada.csv", tmp_path / "saida"
    tabela(x=(0, 1, 2, 3, 4)).to_csv(entrada, index=False)
    original = entrada.read_bytes()
    assert main(["--entrada", str(entrada), "--saida", str(saida)]) == 0
    arquivos = {p.name: p.read_bytes() for p in saida.iterdir()}
    assert set(arquivos) == {
        "correlacoes.csv", "pares.csv", "exclusoes.csv", "relatorio.md",
        "dispersao_cfr_ci.png", "dispersao_cfr_entrega.png",
    }
    assert arquivos["dispersao_cfr_ci.png"].startswith(b"\x89PNG\r\n\x1a\n")
    relatorio = arquivos["relatorio.md"].decode()
    assert hashlib.sha256(original).hexdigest() in relatorio
    assert "symlog" in relatorio
    assert "#34" in relatorio
    assert "500" in relatorio
    executar(entrada, saida)
    assert arquivos == {p.name: p.read_bytes() for p in saida.iterdir()}
    assert entrada.read_bytes() == original


@pytest.mark.parametrize("x,ci,escala", [
    ((1, 2, 3), (None, None, None), "linear"),
    ((1, 1, 1), (0, 0, 0), "symlog"),
    ((1, 10, 100), (0, 0.5, 1), "log"),
])
def test_graficos_vazios_constantes_e_log(tmp_path, x, ci, escala):
    entrada = tmp_path / "entrada.csv"
    tabela(x, ci).to_csv(entrada, index=False)
    executar(entrada, tmp_path / "saida", escala=escala)
    assert (tmp_path / "saida" / "dispersao_cfr_ci.png").stat().st_size > 1000


def test_log_recusa_zero_sem_gravar_resultados(tmp_path):
    entrada, saida = tmp_path / "entrada.csv", tmp_path / "saida"
    tabela(x=(0, 1, 2, 3, 4)).to_csv(entrada, index=False)
    with pytest.raises(ValueError, match="positiva"):
        executar(entrada, saida, escala="log")
    assert not saida.exists()


def test_cli_customizada(tmp_path):
    entrada, saida = tmp_path / "entrada.csv", tmp_path / "saida"
    dados = tabela()
    dados.columns = ["repo", "frequencia", "a", "b"]
    dados.to_csv(entrada, index=False)
    assert main(["--entrada", str(entrada), "--saida", str(saida),
                 "--coluna-repo", "repo", "--coluna-frequencia", "frequencia",
                 "--coluna-cfr-ci", "a", "--coluna-cfr-entrega", "b"]) == 0


def test_cli_erros_sem_saida(tmp_path, caplog):
    saida = tmp_path / "saida"
    assert main(["--entrada", str(tmp_path / "ausente.csv"), "--saida", str(saida)]) == 1
    assert "Não foi possível" in caplog.text
    assert not saida.exists()


@pytest.mark.parametrize("texto", [
    "full_name,cfr_ci,cfr_ci\na,0,1\n", "", "full_name\na\n",
    "full_name,deployment_frequency,cfr_ci,cfr_entrega\na,1,abc,0\n",
])
def test_csv_invalido_nao_grava_saida(tmp_path, texto):
    entrada, saida = tmp_path / "entrada.csv", tmp_path / "saida"
    entrada.write_text(texto)
    assert main(["--entrada", str(entrada), "--saida", str(saida)]) == 1
    assert not saida.exists()


def test_protege_entrada_e_valida_escala(tmp_path):
    entrada = tmp_path / "pares.csv"
    tabela().to_csv(entrada, index=False)
    with pytest.raises(ValueError, match="entrada"):
        executar(entrada, tmp_path)
    with pytest.raises(ValueError, match="Escala"):
        executar(entrada, tmp_path / "saida", escala="outra")


def test_csv_bom_e_ausencias(tmp_path):
    entrada = tmp_path / "entrada.csv"
    entrada.write_text(
        ",".join(COLUNAS_PADRAO) + "\nrepo/a,0,0,NaN\nrepo/b,1,1,0\nrepo/c,2,,1\n",
        encoding="utf-8-sig",
    )
    resumo = executar(entrada, tmp_path / "saida")
    assert resumo.n.tolist() == [2, 2]
