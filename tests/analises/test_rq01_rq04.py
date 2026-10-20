"""Testes do script das RQ 01 a RQ 04 (#48) com um dataset sintético calculado à mão."""

import csv
import io
import socket
import textwrap

import pandas as pd
import pytest

from analises import rq01_rq04 as rq

# r1: 4 métricas, todas Elite. r2: 4 métricas (High, High, Medium, High) -> High.
# r3: 3 métricas (Medium, Medium, Low) -> Medium. r4: 3 métricas (Low, Elite, Low) -> Low.
# r5: 2 métricas (Low, Low) -> geral nula. Lead time: r1 b<a, r2 b=a, r3 e r4 b>a (r4 com a=0),
# r5 sem (b).
DATASET = textwrap.dedent("""\
    full_name,frequencia_semana,lead_time_a_horas,lead_time_b_horas,cfr_a,cfr_b,cfr_b_n_avaliadas,cfr_b_n_falharam,cfr_b_n_censuradas,recuperacao_horas,recuperacao_n_episodios,recuperacao_prop_censurados,coluna_extra
    org/r1,10,12,6,0.10,0.05,20,1,2,0.5,4,0.25,x
    org/r2,2,48,48,0.40,0.40,10,4,0,10,2,0,x
    org/r3,0.5,200,300,0.50,,0,0,0,,0,,x
    org/r4,0.1,0,5,,0.2,5,1,1,200,1,1.0,x
    org/r5,0,1000,,,,,,,,,,x
""")


@pytest.fixture
def dados():
    bruto = pd.read_csv(io.StringIO(DATASET), dtype=str, keep_default_na=False)
    return rq.validar(bruto)


@pytest.fixture
def tabelas(dados):
    return rq.calcular(dados)


def _linha(tabela, **filtro):
    selecao = tabela
    for coluna, valor in filtro.items():
        selecao = selecao[selecao[coluna] == valor]
    assert len(selecao) == 1, filtro
    return selecao.iloc[0]


# --- descritiva -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("metrica", "variante", "unidade", "esperado"),
    [
        # n, ausentes, mediana, q1, q3, iqr, min, max (quantis pelo método linear)
        ("frequencia", "", "releases/semana", (5, 0, 0.5, 0.1, 2.0, 1.9, 0.0, 10.0)),
        ("lead_time", "a", "horas", (5, 0, 48.0, 12.0, 200.0, 188.0, 0.0, 1000.0)),
        ("lead_time", "b", "horas", (4, 1, 27.0, 5.75, 111.0, 105.25, 5.0, 300.0)),
        ("cfr", "a", "fração", (3, 2, 0.40, 0.25, 0.45, 0.20, 0.10, 0.50)),
        ("cfr", "b", "fração", (3, 2, 0.20, 0.125, 0.30, 0.175, 0.05, 0.40)),
        ("recuperacao", "", "horas", (3, 2, 10.0, 5.25, 105.0, 99.75, 0.5, 200.0)),
    ],
)
def test_descritiva_por_linha(tabelas, metrica, variante, unidade, esperado):
    linha = _linha(tabelas["descritiva"], metrica=metrica, variante=variante)
    assert linha["unidade"] == unidade
    assert (linha["n"], linha["n_ausentes"]) == esperado[:2]
    obtido = [linha[c] for c in ("mediana", "q1", "q3", "iqr", "minimo", "maximo")]
    assert obtido == pytest.approx(list(esperado[2:]))


def test_descritiva_ordem_e_rqs(tabelas):
    descritiva = tabelas["descritiva"]
    assert list(descritiva.columns) == list(rq.COLUNAS_DESCRITIVA)
    assert descritiva["rq"].tolist() == ["RQ01", "RQ02", "RQ02", "RQ03", "RQ03", "RQ04"]


# --- comparação lead time ---------------------------------------------------------------


def test_comparacao_lead_time(tabelas):
    linha = tabelas["comparacao_lead_time"].iloc[0]
    # pares r1..r4 (r5 sem b); razões só com a > 0: 0,5; 1,0; 1,5 (r4 tem a = 0)
    assert (linha["n_pares"], linha["n_b_menor"], linha["n_iguais"], linha["n_b_maior"]) == (4, 1, 1, 2)
    assert linha["prop_b_menor"] == pytest.approx(0.25)
    assert linha["mediana_razao_b_a"] == pytest.approx(1.0)


def test_comparacao_sem_pares_fica_vazia(dados):
    dados = dados.assign(lead_time_b_horas=float("nan"))
    linha = rq.tabela_comparacao_lead_time(dados).iloc[0]
    assert linha["n_pares"] == 0
    assert linha["prop_b_menor"] is None and linha["mediana_razao_b_a"] is None


# --- classificação C1 -------------------------------------------------------------------


def test_classificacao_c1(tabelas):
    tabela = tabelas["classificacao_c1"]
    assert list(tabela.columns) == list(rq.COLUNAS_CLASSIFICACAO)
    obtido = {
        linha["full_name"]: (linha["frequencia"], linha["lead_time"], linha["cfr"],
                             linha["recuperacao"], linha["geral"], linha["n_metricas"])
        for linha in tabela.to_dict("records")
    }
    assert obtido == {
        "org/r1": ("Elite", "Elite", "Elite", "Elite", "Elite", 4),
        "org/r2": ("High", "High", "Medium", "High", "High", 4),
        "org/r3": ("Medium", "Medium", "Low", None, "Medium", 3),
        "org/r4": ("Low", "Elite", None, "Low", "Low", 3),
        "org/r5": ("Low", "Low", None, None, None, 2),
    }


def test_distribuicao_c1(tabelas):
    tabela = tabelas["distribuicao_c1"]
    esperado = {  # Elite, High, Medium, Low, sem_classificacao
        "frequencia": (1, 1, 1, 2, 0),
        "lead_time": (2, 1, 1, 1, 0),
        "cfr": (1, 0, 1, 1, 2),
        "recuperacao": (1, 1, 0, 1, 2),
        "geral": (1, 1, 1, 1, 1),
    }
    assert len(tabela) == 25
    for metrica, contagens in esperado.items():
        linhas = tabela[tabela["metrica"] == metrica]
        assert linhas["categoria"].tolist() == ["Elite", "High", "Medium", "Low", "sem_classificacao"]
        assert linhas["n"].tolist() == list(contagens)
        assert linhas["proporcao"].tolist() == pytest.approx([n / 5 for n in contagens])


def test_censura_e_cobertura(tabelas):
    valores = dict(zip(tabelas["censura_e_cobertura"]["indicador"], tabelas["censura_e_cobertura"]["valor"]))
    assert valores == {
        "total_repositorios": 5,
        "soma_cfr_b_n_avaliadas": 35,
        "soma_cfr_b_n_falharam": 6,
        "soma_cfr_b_n_censuradas": 3,
        "soma_recuperacao_n_episodios": 7,
        "mediana_recuperacao_prop_censurados": pytest.approx(0.25),  # de 0,25; 0; 1
        "repos_com_episodio_censurado": 2,
        "repos_sem_episodio": 1,
        "repos_c1_4_metricas": 2,
        "repos_c1_3_metricas": 2,
        "repos_c1_ate_2_metricas": 1,
        "repos_geral_nulo": 1,
    }
    assert set(valores) == set(rq.INDICADORES)


# --- resumo.md --------------------------------------------------------------------------


def test_formatacao():
    assert rq.formatar_numero(5) == "5"
    assert rq.formatar_numero(1234.5) == "1234,50"
    assert rq.formatar_numero(None) == "—"
    assert rq.formatar_numero(float("nan")) == "—"
    assert rq.formatar_fracao(0.25) == "0,25 (25,00 %)"
    assert rq.formatar_fracao(None) == "—"


def test_resumo_md_contem_as_tabelas(tabelas):
    texto = rq.gerar_resumo_md(tabelas)
    for titulo in ("## Estatística descritiva", "## Lead time: variante (b) × variante (a)",
                   "## Distribuição das categorias DORA (C1)", "## Censura e cobertura",
                   "## Classificação DORA por repositório (C1)"):
        assert titulo in texto
    assert "| RQ02 | lead_time | b | horas | 4 | 1 | 27,00 | 5,75 | 111,00 | 105,25 | 5,00 | 300,00 |" in texto
    assert "| RQ03 | cfr | a | fração | 3 | 2 | 0,40 (40,00 %) |" in texto
    assert "| 4 | 1 | 1 | 2 | 0,25 (25,00 %) | 1,00 |" in texto
    assert "| Sem classificação | 0 (0,00 %) | 0 (0,00 %) | 2 (40,00 %) | 2 (40,00 %) | 1 (20,00 %) |" in texto
    assert "| Mediana da proporção de episódios censurados | 0,25 (25,00 %) |" in texto
    assert "| org/r5 | Low | Low | — | — | — | 2 |" in texto


# --- figuras ----------------------------------------------------------------------------


def test_valores_para_figura_exclui_nao_positivos_so_no_log():
    serie = pd.Series([0.0, 2.0, float("nan"), 5.0])
    valores, excluidos = rq.valores_para_figura(serie, escala_log=True)
    assert valores.tolist() == [2.0, 5.0] and excluidos == 1
    valores, excluidos = rq.valores_para_figura(serie, escala_log=False)
    assert valores.tolist() == [0.0, 2.0, 5.0] and excluidos == 0


def test_titulos_informam_excluidos(dados, tabelas):
    figuras = rq.gerar_figuras(dados, tabelas)
    assert set(figuras) == {"rq01_frequencia.png", "rq02_lead_time.png", "rq03_cfr.png",
                            "rq04_recuperacao.png", "c1_distribuicao.png"}
    titulo_rq01 = figuras["rq01_frequencia.png"].axes[0].get_title()
    assert "n = 4" in titulo_rq01 and "excluídos da figura: 1" in titulo_rq01
    titulo_rq02 = figuras["rq02_lead_time.png"].axes[0].get_title()
    assert "excluídos da figura: 1 (a), 0 (b)" in titulo_rq02
    assert figuras["rq03_cfr.png"].axes[0].get_yscale() == "linear"
    assert figuras["rq04_recuperacao.png"].axes[0].get_yscale() == "log"


def test_figuras_sem_dados_nao_quebram(dados):
    vazio = dados.assign(**{c: float("nan") for c in dados.columns if c != "full_name"})
    tabelas = rq.calcular(vazio)
    figuras = rq.gerar_figuras(vazio, tabelas)
    assert "n = 0" in figuras["rq02_lead_time.png"].axes[0].get_title()
    assert tabelas["comparacao_lead_time"].iloc[0]["n_pares"] == 0


# --- main e E/S -------------------------------------------------------------------------


def _preparar(escrever_config, tmp_path, conteudo=DATASET):
    config = escrever_config()
    saida = tmp_path / "output"
    saida.mkdir(parents=True, exist_ok=True)
    (saida / rq.ARQUIVO_DATASET).write_text(conteudo, encoding="utf-8")
    return config, saida


@pytest.fixture
def sem_rede(monkeypatch):
    def bloqueado(*args, **kwargs):
        raise AssertionError("acesso à rede durante a análise")

    monkeypatch.setattr(socket, "socket", bloqueado)
    monkeypatch.setattr(socket, "create_connection", bloqueado)


def test_main_grava_todas_as_saidas_sem_rede(escrever_config, tmp_path, sem_rede):
    config, saida = _preparar(escrever_config, tmp_path)
    assert rq.main(["--config", str(config)]) == 0

    pasta = saida / "analises" / "rq01_rq04"
    for nome, colunas in rq.TABELAS.items():
        caminho = pasta / f"{nome}.csv"
        assert caminho.read_bytes().startswith(b"\xef\xbb\xbf")  # UTF-8 com BOM
        with caminho.open(encoding="utf-8-sig", newline="") as f:
            assert tuple(next(csv.reader(f))) == colunas
    with (pasta / "classificacao_c1.csv").open(encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert linhas[4] == {"full_name": "org/r5", "frequencia": "Low", "lead_time": "Low", "cfr": "",
                         "recuperacao": "", "geral": "", "n_metricas": "2"}
    descritiva = pd.read_csv(pasta / "descritiva.csv", encoding="utf-8-sig")
    assert descritiva.loc[2, "q1"] == pytest.approx(5.75)

    assert "## Censura e cobertura" in (pasta / "resumo.md").read_text(encoding="utf-8")
    for nome in ("rq01_frequencia.png", "rq02_lead_time.png", "rq03_cfr.png",
                 "rq04_recuperacao.png", "c1_distribuicao.png"):
        figura = pasta / "figuras" / nome
        assert figura.is_file() and figura.stat().st_size > 0


def test_main_aceita_dataset_explicito(escrever_config, tmp_path):
    config = escrever_config()
    outro = tmp_path / "meu_dataset.csv"
    outro.write_text(DATASET, encoding="utf-8")
    assert rq.main(["--config", str(config), "--dataset", str(outro)]) == 0
    assert (tmp_path / "output" / "analises" / "rq01_rq04" / "descritiva.csv").is_file()


def test_dataset_ausente_retorna_2(escrever_config, caplog):
    config = escrever_config()
    assert rq.main(["--config", str(config)]) == 2
    assert "arquivo não encontrado" in caplog.text and "#35" in caplog.text


def test_config_invalido_retorna_2(tmp_path):
    assert rq.main(["--config", str(tmp_path / "nao_existe.yaml")]) == 2


def test_coluna_faltando_retorna_2_e_cita_a_coluna(escrever_config, tmp_path, caplog):
    sem_coluna = pd.read_csv(io.StringIO(DATASET), dtype=str).drop(columns="cfr_b")
    config, saida = _preparar(escrever_config, tmp_path, sem_coluna.to_csv(index=False))
    assert rq.main(["--config", str(config)]) == 2
    assert "coluna obrigatória ausente: cfr_b" in caplog.text
    assert not (saida / "analises").exists()


def _alterar(coluna: str, valor: str) -> str:
    tabela = pd.read_csv(io.StringIO(DATASET), dtype=str, keep_default_na=False)
    tabela.loc[0, coluna] = valor
    return tabela.to_csv(index=False)


@pytest.mark.parametrize(
    ("coluna", "valor", "mensagem"),
    [
        ("cfr_a", "1.5", "coluna cfr_a: fração fora de 0–1 em linha 2 = '1.5'"),
        ("recuperacao_prop_censurados", "2", "coluna recuperacao_prop_censurados: fração fora de 0–1"),
        ("lead_time_a_horas", "-3", "coluna lead_time_a_horas: valor negativo em linha 2 = '-3'"),
        ("cfr_b_n_falharam", "-1", "coluna cfr_b_n_falharam: valor negativo"),
        ("frequencia_semana", "abc", "coluna frequencia_semana: valor não numérico em linha 2 = 'abc'"),
        ("recuperacao_horas", "inf", "coluna recuperacao_horas: valor não numérico"),
    ],
)
def test_valor_invalido_retorna_2(escrever_config, tmp_path, caplog, coluna, valor, mensagem):
    config, saida = _preparar(escrever_config, tmp_path, _alterar(coluna, valor))
    assert rq.main(["--config", str(config)]) == 2
    assert mensagem in caplog.text
    assert not (saida / "analises").exists()


def test_validar_lista_todos_os_problemas():
    bruto = pd.read_csv(io.StringIO(DATASET), dtype=str, keep_default_na=False)
    bruto.loc[0, "cfr_b"] = "1.2"
    bruto.loc[1, "full_name"] = "org/r1"
    bruto.loc[2, "full_name"] = " "
    with pytest.raises(rq.ErroDataset) as erro:
        rq.validar(bruto)
    texto = str(erro.value)
    assert "cfr_b: fração fora de 0–1" in texto
    assert "repositório repetido: org/r1" in texto
    assert "full_name: vazia em linha 4" in texto


def test_dataset_sem_linhas_e_erro():
    cabecalho = DATASET.splitlines()[0]
    bruto = pd.read_csv(io.StringIO(cabecalho + "\n"), dtype=str, keep_default_na=False)
    with pytest.raises(rq.ErroDataset, match="nenhuma linha"):
        rq.validar(bruto)
