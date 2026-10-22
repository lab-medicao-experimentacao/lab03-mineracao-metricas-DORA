"""Testes da análise de sensibilidade da RQ 07 (#49) com um dataset sintético calculado à mão."""

import csv
import io

import pandas as pd
import pytest

from analises import rq07_sensibilidade as rq07
from pipeline.config import Combinacao, ErroConfiguracao

C1 = Combinacao("C1", "release", "a", "a")
C2 = Combinacao("C2", "release_prerelease", "b", "b")
C3 = Combinacao("C3", "tag", "b", "a")
COMBINACOES = (C1, C2, C3)

COLUNAS = ("full_name", "frequencia_semana", "frequencia_prerelease_semana", "frequencia_tag_semana",
           "lead_time_release_horas", "lead_time_commit_horas", "cfr_ci", "cfr_entrega",
           "recuperacao_mediana_horas")
LINHAS = [
    # r1: C1 = (Low, High, Low, High) → Medium; C2 = (Low, Elite, Elite, High) → High;
    #     C3 = (High, Elite, Low, High) → High
    ["org/r1", "0.1", "0.1", "2", "100", "10", "0.5", "0.1", "2"],
    # r2: Elite em tudo, em qualquer combinação
    ["org/r2", "10", "10", "10", "10", "10", "0.05", "0.05", "0.5"],
    # r3: sem CFR (b) nem recuperação → C2 só tem 2 métricas e fica sem categoria geral
    ["org/r3", "0.5", "0.5", "0.5", "200", "200", "0.2", "", ""],
]


def dataset_texto(linhas=LINHAS, colunas=COLUNAS) -> pd.DataFrame:
    return pd.DataFrame(linhas, columns=list(colunas), dtype=str)


@pytest.fixture
def dados():
    return rq07.validar(dataset_texto())


@pytest.fixture
def tabelas(dados):
    return rq07.calcular(dados, COMBINACOES)


def test_classificacao_de_cada_combinacao(dados):
    c1 = rq07.classificar_combinacao(dados, C1)
    assert c1.loc[0].to_dict() == {
        "frequencia": "Low", "lead_time": "High", "cfr": "Low", "recuperacao": "High", "geral": "Medium"}
    assert rq07.classificar_combinacao(dados, C2)["geral"].tolist() == ["High", "Elite", None]
    assert rq07.classificar_combinacao(dados, C3)["geral"].tolist() == ["High", "Elite", "Medium"]


def test_unidade_de_deploy_muda_so_a_frequencia(dados):
    c1 = rq07.classificar_combinacao(dados, C1)
    c3 = rq07.classificar_combinacao(dados, C3)
    assert c1["frequencia"].tolist() == ["Low", "Elite", "Medium"]
    assert c3["frequencia"].tolist() == ["High", "Elite", "Medium"]  # r1 tem 2 tags/semana
    assert c1["cfr"].tolist() == c3["cfr"].tolist()                  # as duas usam o CFR (a)


def test_tabela_de_pares(tabelas):
    pares = tabelas["sensibilidade_pares"].set_index("par")
    c1c2 = pares.loc["C1xC2"]
    assert (c1c2["n_total"], c1c2["n_comparados"], c1c2["n_excluidos"]) == (3, 2, 1)  # r3 sem categoria em C2
    assert (c1c2["n_mudaram"], c1c2["prop_mudaram"]) == (1, 0.5)
    assert (c1c2["n_melhoraram"], c1c2["n_pioraram"], c1c2["n_adjacentes"], c1c2["n_saltos"]) == (1, 0, 1, 0)
    c1c3 = pares.loc["C1xC3"]
    assert (c1c3["n_comparados"], c1c3["n_mudaram"]) == (3, 1)
    assert c1c3["prop_mudaram"] == pytest.approx(1 / 3)
    c2c3 = pares.loc["C2xC3"]
    assert (c2c3["n_comparados"], c2c3["n_mudaram"], c2c3["prop_mudaram"]) == (2, 0, 0.0)
    assert c2c3["kappa_ponderado"] == pytest.approx(1.0)
    assert c2c3["interpretacao"] == "quase perfeita"


def test_kappa_indefinido_e_registrado_como_indefinido():
    # duas combinações iguais em que todos os repositórios caem na mesma categoria
    dados = rq07.validar(dataset_texto([["org/a", "10", "10", "10", "10", "10", "0.05", "0.05", "0.5"],
                                        ["org/b", "10", "10", "10", "10", "10", "0.05", "0.05", "0.5"]]))
    pares = rq07.calcular(dados, COMBINACOES)["sensibilidade_pares"]
    assert pares["kappa_ponderado"].isna().all()
    assert set(pares["interpretacao"]) == {"indefinido"}


def test_sensibilidade_por_metrica_nao_inclui_a_recuperacao(tabelas):
    por_metrica = tabelas["sensibilidade_metricas"]
    assert set(por_metrica["metrica"]) == {"frequencia", "lead_time", "cfr"}
    linha = por_metrica[(por_metrica["par"] == "C1xC2") & (por_metrica["metrica"] == "cfr")].iloc[0]
    assert (linha["n_comparados"], linha["n_mudaram"]) == (2, 1)  # r1 Low → Elite; r3 sem CFR (b)


def test_matriz_de_transicao_inclui_sem_classificacao(tabelas):
    matriz = tabelas["matrizes_transicao"]
    sub = matriz[matriz["par"] == "C1xC2"].set_index(["de", "para"])["n"]
    assert len(sub) == 25
    assert sub[("Medium", "High")] == 1
    assert sub[("Elite", "Elite")] == 1
    assert sub[("Medium", "sem_classificacao")] == 1
    assert sub.sum() == 3


def test_distribuicao_por_combinacao_soma_o_total(tabelas):
    distribuicao = tabelas["distribuicao_combinacoes"]
    assert (distribuicao.groupby("combinacao")["n"].sum() == 3).all()
    c2 = distribuicao[distribuicao["combinacao"] == "C2"].set_index("categoria")["n"]
    assert (c2["Elite"], c2["High"], c2["sem_classificacao"]) == (1, 1, 1)


def test_resumo_markdown_traz_as_tabelas_e_o_tratamento_de_exclusoes(tabelas):
    texto = rq07.gerar_resumo_md(tabelas)
    assert "## Mudança de categoria geral e kappa ponderado, por par" in texto
    assert "| C1xC2 | 2 | 1 | 1 (50,00 %) |" in texto
    assert "## Matriz de transição C1 → C2" in texto
    assert "Sem classificação" in texto  # C2 deixa r3 sem categoria


def test_figuras_sao_geradas(tabelas):
    figuras = rq07.gerar_figuras(tabelas)
    assert set(figuras) == {"transicao_pares.png", "distribuicao_combinacoes.png"}
    assert len(figuras["transicao_pares.png"].axes) == 3


# --- validação do dataset e das combinações -------------------------------------------------


def test_validar_converte_vazio_em_nan(dados):
    assert pd.isna(dados.loc[2, "cfr_entrega"]) and pd.isna(dados.loc[2, "recuperacao_mediana_horas"])
    assert dados.loc[0, "frequencia_tag_semana"] == 2.0


@pytest.mark.parametrize("mudanca, trecho", [
    (lambda d: d.drop(columns=["frequencia_tag_semana"]), "colunas ausentes: frequencia_tag_semana"),
    (lambda d: d.assign(cfr_ci=["0.5", "1.5", "0.1"]), "cfr_ci: fração fora de 0–1"),
    (lambda d: d.assign(lead_time_commit_horas=["10", "-1", "5"]), "lead_time_commit_horas: valor negativo"),
    (lambda d: d.assign(recuperacao_mediana_horas=["1", "abc", "5"]), "valor não numérico"),
    (lambda d: d.assign(frequencia_semana=["1", "inf", "5"]), "valor infinito"),
    (lambda d: d.assign(full_name=["org/r1", "org/r1", "org/r3"]), "full_name repetido"),
    (lambda d: d.iloc[0:0], "nenhuma linha de dados"),
])
def test_validar_rejeita_dataset_fora_do_contrato(mudanca, trecho):
    with pytest.raises(rq07.ErroDataset, match=trecho):
        rq07.validar(mudanca(dataset_texto()))


def test_pelo_menos_tres_combinacoes():
    with pytest.raises(ErroConfiguracao, match="pelo menos 3"):
        rq07.validar_combinacoes((C1, C2))


# --- disco ---------------------------------------------------------------------------------


def escrever_dataset(caminho, linhas=LINHAS):
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator="\n")
    escritor.writerow(COLUNAS)
    escritor.writerows(linhas)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(saida.getvalue(), encoding="utf-8")


def test_executar_grava_csvs_resumo_e_figuras(tmp_path):
    escrever_dataset(tmp_path / "metricas_repos.csv")
    rq07.executar(tmp_path / "metricas_repos.csv", COMBINACOES, tmp_path / "saida")
    pasta = tmp_path / "saida"
    for nome in rq07.TABELAS:
        assert (pasta / f"{nome}.csv").is_file()
    assert (pasta / "resumo.md").is_file()
    assert (pasta / "figuras" / "transicao_pares.png").stat().st_size > 0
    with (pasta / "sensibilidade_pares.csv").open(encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert [l["par"] for l in linhas] == ["C1xC2", "C1xC3", "C2xC3"]
    assert linhas[0]["prop_mudaram"] == "0.5"


def test_executar_dataset_ausente_e_erro(tmp_path):
    with pytest.raises(rq07.ErroDataset, match="não encontrado"):
        rq07.executar(tmp_path / "nao-existe.csv", COMBINACOES, tmp_path)


SENSIBILIDADE = """sensibilidade:
  combinacoes:
    C1: {unidade_deploy: release, lead_time: a, cfr: a}
    C2: {unidade_deploy: release_prerelease, lead_time: b, cfr: b}
    C3: {unidade_deploy: tag, lead_time: b, cfr: a}
caminhos:"""


def test_main_sucesso(escrever_config, tmp_path):
    config = escrever_config({"caminhos:": SENSIBILIDADE})
    escrever_dataset(tmp_path / "output" / "metricas_repos.csv")
    assert rq07.main(["--config", str(config)]) == 0
    assert (tmp_path / "output" / "analises" / "rq07" / "resumo.md").is_file()


def test_main_sem_combinacoes_no_config_devolve_2(escrever_config, tmp_path):
    escrever_dataset(tmp_path / "output" / "metricas_repos.csv")
    assert rq07.main(["--config", str(escrever_config())]) == 2


def test_main_dataset_ausente_devolve_2(escrever_config):
    assert rq07.main(["--config", str(escrever_config({"caminhos:": SENSIBILIDADE}))]) == 2


def test_frequencia_por_unidade_de_deploy(tabelas):
    f = tabelas["frequencia_por_unidade"].set_index("unidade_deploy")
    assert list(f.index) == ["release", "release_prerelease", "tag"]
    assert f.loc["release", "mediana"] == pytest.approx(0.5)   # 0,1; 0,5; 10
    assert f.loc["tag", "mediana"] == pytest.approx(2.0)       # 0,5; 2; 10
    assert (f["n"] == 3).all() and (f["n_ausentes"] == 0).all()
