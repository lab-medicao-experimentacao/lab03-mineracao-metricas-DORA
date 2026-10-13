import pytest

from metricas.concordancia import (
    concordancia_observada,
    consenso,
    interpretar_kappa,
    kappa_fleiss,
    normalizar_rotulo,
    tipo_divergencia,
)

SIM_NAO = ("sim", "nao")
SIM_NAO_INCERTO = ("sim", "nao", "incerto")

# Exemplo calculado à mão: 5 itens, 3 avaliadores (A, B, C), 2 categorias.
EXEMPLO = [
    ("sim", "sim", "sim"),  # n_sim=3, n_nao=0 -> P_1 = (9 + 0 - 3) / (3*2) = 1
    ("sim", "sim", "nao"),  # n_sim=2, n_nao=1 -> P_2 = (4 + 1 - 3) / 6    = 1/3
    ("nao", "nao", "nao"),  # n_sim=0, n_nao=3 -> P_3 = (0 + 9 - 3) / 6    = 1
    ("sim", "nao", "nao"),  # n_sim=1, n_nao=2 -> P_4 = (1 + 4 - 3) / 6    = 1/3
    ("sim", "sim", "sim"),  # n_sim=3, n_nao=0 -> P_5 = 1
]
# Total de rótulos = N * n = 5 * 3 = 15; sim = 9, nao = 6.
# p_sim = 9/15 = 0.6 ; p_nao = 6/15 = 0.4
# P̄  = (1 + 1/3 + 1 + 1/3 + 1) / 5 = 11/15 ≈ 0.7333
# P̄e = 0.6² + 0.4² = 0.36 + 0.16 = 0.52
# κ  = (P̄ - P̄e) / (1 - P̄e) = (11/15 - 0.52) / 0.48 = (16/75) / (12/25) = 4/9 ≈ 0.4444
KAPPA_EXEMPLO = 4 / 9


# --- normalizar_rotulo ---------------------------------------------------------


def test_normalizar_remove_espacos_e_minusculiza():
    assert normalizar_rotulo("  Sim \n") == "sim"
    assert normalizar_rotulo("BIBLIOTECA/FRAMEWORK") == "biblioteca/framework"


def test_normalizar_none_vira_string_vazia():
    assert normalizar_rotulo(None) == ""


def test_normalizar_nao_valida():
    assert normalizar_rotulo(" qualquer coisa ") == "qualquer coisa"


# --- kappa_fleiss ---------------------------------------------------------------


def test_kappa_exemplo_calculado_a_mao():
    assert kappa_fleiss(EXEMPLO, SIM_NAO) == pytest.approx(KAPPA_EXEMPLO)


def test_kappa_categoria_valida_nunca_usada_nao_altera_resultado():
    # p_incerto = 0 não contribui para P̄e nem para P_i.
    assert kappa_fleiss(EXEMPLO, SIM_NAO_INCERTO) == pytest.approx(KAPPA_EXEMPLO)


def test_kappa_ordem_das_categorias_nao_importa():
    assert kappa_fleiss(EXEMPLO, ("incerto", "nao", "sim")) == pytest.approx(KAPPA_EXEMPLO)


def test_kappa_um_com_concordancia_total_em_duas_categorias():
    itens = [("sim", "sim", "sim"), ("nao", "nao", "nao"), ("sim", "sim", "sim")]
    assert kappa_fleiss(itens, SIM_NAO) == pytest.approx(1.0)


def test_kappa_negativo_em_discordancia_sistematica():
    # Todo item é 2x1: P_i = 1/3; p_sim = p_nao = 0.5 -> P̄e = 0.5; κ = (1/3 - 0.5)/0.5 = -1/3
    itens = [("sim", "sim", "nao"), ("nao", "nao", "sim")] * 3
    kappa = kappa_fleiss(itens, SIM_NAO)
    assert kappa < 0
    assert kappa == pytest.approx(-1 / 3)


def test_kappa_degenerado_tudo_numa_categoria_e_none():
    itens = [("sim", "sim", "sim")] * 4
    assert kappa_fleiss(itens, SIM_NAO_INCERTO) is None


def test_kappa_devolve_float():
    assert isinstance(kappa_fleiss(EXEMPLO, SIM_NAO), float)


def test_kappa_funciona_com_dois_avaliadores():
    # P_i ∈ {1, 0}; P̄ = 2/4 = 0.5; p_sim = p_nao = 0.5 -> P̄e = 0.5; κ = 0
    itens = [("sim", "sim"), ("nao", "nao"), ("sim", "nao"), ("nao", "sim")]
    assert kappa_fleiss(itens, SIM_NAO) == pytest.approx(0.0)


def test_kappa_lista_vazia_gera_erro():
    with pytest.raises(ValueError):
        kappa_fleiss([], SIM_NAO)


def test_kappa_numero_de_avaliadores_diferente_gera_erro():
    with pytest.raises(ValueError):
        kappa_fleiss([("sim", "sim", "sim"), ("sim", "nao")], SIM_NAO)


def test_kappa_menos_de_dois_avaliadores_gera_erro():
    with pytest.raises(ValueError):
        kappa_fleiss([("sim",), ("nao",)], SIM_NAO)


def test_kappa_rotulo_fora_das_categorias_gera_erro():
    with pytest.raises(ValueError):
        kappa_fleiss([("sim", "sim", "talvez")], SIM_NAO)


# --- concordancia_observada -------------------------------------------------------


def test_concordancia_observada_fracao_de_itens_unanimes():
    assert concordancia_observada(EXEMPLO) == pytest.approx(3 / 5)


def test_concordancia_observada_extremos():
    assert concordancia_observada([("sim", "sim", "sim")]) == 1.0
    assert concordancia_observada([("sim", "nao", "sim")]) == 0.0


def test_concordancia_observada_vazia_gera_erro():
    with pytest.raises(ValueError):
        concordancia_observada([])


# --- interpretar_kappa ------------------------------------------------------------


@pytest.mark.parametrize(
    ("kappa", "esperado"),
    [
        (None, "indefinido"),
        (-0.01, "pobre"),
        (0, "leve"),
        (0.20, "leve"),
        (0.2000001, "razoável"),
        (0.40, "razoável"),
        (0.60, "moderada"),
        (0.80, "substancial"),
        (0.8000001, "quase perfeita"),
        (1, "quase perfeita"),
    ],
)
def test_interpretar_kappa_nos_limites(kappa, esperado):
    assert interpretar_kappa(kappa) == esperado


# --- tipo_divergencia e consenso ------------------------------------------------


def test_tipo_divergencia_unanime_e_none():
    assert tipo_divergencia(("sim", "sim", "sim")) is None


@pytest.mark.parametrize(
    "rotulos",
    [("nao", "sim", "sim"), ("sim", "nao", "sim"), ("sim", "sim", "nao")],
)
def test_tipo_divergencia_2x1_em_cada_posicao(rotulos):
    assert tipo_divergencia(rotulos) == "2x1"


def test_tipo_divergencia_1_1_1():
    assert tipo_divergencia(("sim", "nao", "incerto")) == "1-1-1"


def test_tipo_divergencia_exige_tres_avaliadores():
    with pytest.raises(ValueError):
        tipo_divergencia(("sim", "nao"))


def test_consenso_unanime():
    assert consenso(("sim", "sim", "sim")) == ("sim", "unanime")


@pytest.mark.parametrize(
    "rotulos",
    [("nao", "sim", "sim"), ("sim", "nao", "sim"), ("sim", "sim", "nao")],
)
def test_consenso_maioria_em_cada_posicao_do_divergente(rotulos):
    assert consenso(rotulos) == ("sim", "maioria")


def test_consenso_1_1_1_fica_pendente():
    assert consenso(("sim", "nao", "incerto")) == (None, "pendente")
