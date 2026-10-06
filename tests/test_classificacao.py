import pytest

from metricas.classificacao import (
    UMA_POR_MES_EM_SEMANAS,
    classificacao_geral,
    classificar_metrica,
    classificar_repositorio,
)

# Tabela de referência (seção 5, RQ 07 do enunciado). Unidades do projeto:
# frequência em releases/semana, lead time e recuperação em horas, CFR como fração 0–1.


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (10.0, "Elite"),
        (7.0, "Elite"),                       # limite: ≥ 7/semana
        (6.99, "High"),
        (1.0, "High"),                        # limite: ≥ 1/semana
        (0.99, "Medium"),
        (UMA_POR_MES_EM_SEMANAS, "Medium"),   # limite: ≥ 1/mês
        (UMA_POR_MES_EM_SEMANAS - 1e-9, "Low"),
        (0.0, "Low"),
    ],
)
def test_frequencia(valor, esperado):
    assert classificar_metrica("frequencia", valor) == esperado


def test_uma_por_mes_equivale_a_12_releases_em_um_ano_medio():
    assert UMA_POR_MES_EM_SEMANAS == pytest.approx(12 * 7 / 365.25)


@pytest.mark.parametrize(
    "horas, esperado",
    [
        (0.0, "Elite"),
        (23.99, "Elite"),
        (24.0, "High"),          # 1 dia
        (167.99, "High"),
        (168.0, "Medium"),       # 1 semana
        (719.99, "Medium"),
        (720.0, "Low"),          # 30 dias
        (13 * 24.0, "Medium"),   # exemplo da RQ 02: 13 dias
    ],
)
def test_lead_time(horas, esperado):
    assert classificar_metrica("lead_time", horas) == esperado


@pytest.mark.parametrize(
    "cfr, esperado",
    [
        (0.0, "Elite"),
        (3 / 20, "Elite"),   # limite: ≤ 15%
        (0.1501, "High"),
        (3 / 10, "High"),    # limite: ≤ 30%
        (0.3001, "Medium"),
        (9 / 20, "Medium"),  # limite: ≤ 45%
        (0.4501, "Low"),
        (1.0, "Low"),
    ],
)
def test_cfr(cfr, esperado):
    assert classificar_metrica("cfr", cfr) == esperado


@pytest.mark.parametrize(
    "horas, esperado",
    [
        (0.5, "Elite"),
        (1.0, "High"),           # 1 hora
        (80 / 60, "High"),       # exemplo da RQ 04: 1h20
        (23.99, "High"),
        (24.0, "Medium"),        # 1 dia
        (167.99, "Medium"),
        (168.0, "Low"),          # 1 semana
    ],
)
def test_recuperacao(horas, esperado):
    assert classificar_metrica("recuperacao", horas) == esperado


def test_valor_ausente_nao_tem_categoria():
    assert classificar_metrica("lead_time", None) is None


@pytest.mark.parametrize("nome", ["frequencia", "lead_time", "cfr", "recuperacao"])
def test_nan_e_tratado_como_valor_ausente(nome):
    # pandas representa valor ausente como NaN ao ler CSV (S03)
    assert classificar_metrica(nome, float("nan")) is None


@pytest.mark.parametrize("nome", ["frequencia", "lead_time", "cfr", "recuperacao"])
def test_valor_infinito_gera_erro(nome):
    with pytest.raises(ValueError):
        classificar_metrica(nome, float("inf"))


def test_classificar_repositorio_com_nan_nao_vira_low():
    nan = float("nan")
    resultado = classificar_repositorio(nan, nan, nan, nan)
    assert set(resultado.values()) == {None}


def test_metrica_desconhecida_gera_erro():
    with pytest.raises(ValueError):
        classificar_metrica("mttr", 1.0)


@pytest.mark.parametrize("nome", ["frequencia", "lead_time", "cfr", "recuperacao"])
def test_valor_negativo_gera_erro(nome):
    with pytest.raises(ValueError):
        classificar_metrica(nome, -1.0)


def test_cfr_acima_de_100_porcento_gera_erro():
    with pytest.raises(ValueError):
        classificar_metrica("cfr", 1.01)


@pytest.mark.parametrize(
    "categorias, esperado",
    [
        (["Elite", "High", "High", "Low"], "High"),     # exemplo do enunciado: (4, 3, 3, 1) → 3
        (["Elite", "Elite", "Elite", "Elite"], "Elite"),
        (["Low", "Low", "Low", "Low"], "Low"),
        (["Elite", "High", "Medium", "Low"], "Medium"),  # mediana 2,5 → arredonda p/ baixo → 2
        (["Elite", "Elite", "High", "High"], "High"),    # mediana 3,5 → 3
        (["Elite", "Low", "Low", "Low"], "Low"),
    ],
)
def test_classificacao_geral_pela_mediana_arredondada_para_baixo(categorias, esperado):
    assert classificacao_geral(categorias) == esperado


def test_classificacao_geral_ignora_metricas_sem_valor():
    assert classificacao_geral(["Elite", None, "High", None]) == "High"  # mediana 3,5 → 3


def test_classificacao_geral_trata_nan_como_metrica_sem_valor():
    # categoria vazia num CSV lido pelo pandas vira NaN (S03, RQ 07)
    nan = float("nan")
    assert classificacao_geral(["Elite", "High", "High", nan]) == "High"


def test_classificacao_geral_sem_nenhuma_metrica():
    assert classificacao_geral([None, None, None, None]) is None


def test_classificacao_geral_categoria_invalida_gera_erro():
    with pytest.raises(ValueError):
        classificacao_geral(["Elite", "Excelente"])


def test_classificar_repositorio_retorna_categorias_e_geral():
    resultado = classificar_repositorio(
        frequencia=7.5,      # Elite
        lead_time=48.0,      # High
        cfr=0.20,            # High
        recuperacao=200.0,   # Low
    )
    assert resultado == {
        "frequencia": "Elite",
        "lead_time": "High",
        "cfr": "High",
        "recuperacao": "Low",
        "geral": "High",
    }
