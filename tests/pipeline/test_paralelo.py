"""Execução concorrente com resultados na ordem de entrada (sem rede)."""

import random
import threading
import time

import pytest

from pipeline.paralelo import em_ordem, mapear


def lento(x: int) -> int:
    time.sleep(random.uniform(0, 0.01))
    return x * x


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_mapear_devolve_na_ordem_de_entrada(workers):
    assert mapear(lento, range(40), workers) == [x * x for x in range(40)]


def test_mapear_vazio():
    assert mapear(lento, [], 4) == []


@pytest.mark.parametrize("workers", [1, 4])
def test_mapear_levanta_o_primeiro_erro_na_ordem(workers):
    def falha(x):
        if x in (3, 7):
            time.sleep(0.02 if x == 3 else 0)  # o 7 termina antes, mas o 3 vem antes na ordem
            raise ValueError(f"erro {x}")
        return x

    with pytest.raises(ValueError, match="erro 3"):
        mapear(falha, range(10), workers)


def test_com_varios_workers_as_tarefas_rodam_ao_mesmo_tempo():
    barreira = threading.Barrier(4, timeout=5)  # só passa se 4 tarefas estiverem ativas juntas

    def espera_as_outras(x):
        barreira.wait()
        return x

    assert mapear(espera_as_outras, range(8), 4) == list(range(8))


def test_um_worker_e_sequencial_e_preguicoso():
    avaliados = []

    def avaliar(x):
        avaliados.append(x)
        return x

    for item, valor, erro in em_ordem(avaliar, range(100), workers=1):
        if item == 4:
            break
    assert avaliados == [0, 1, 2, 3, 4]  # nada além do consumido, como no laço antigo


def test_em_ordem_entrega_erros_como_valor_na_posicao_certa():
    def talvez(x):
        if x % 3 == 0:
            raise KeyError(x)
        return -x

    for workers in (1, 3):
        saida = list(em_ordem(talvez, range(7), workers))
        assert [item for item, _, _ in saida] == list(range(7))
        assert [type(erro).__name__ if erro else valor for _, valor, erro in saida] == [
            "KeyError", -1, -2, "KeyError", -4, -5, "KeyError",
        ]


def test_antecipacao_limita_o_que_comeca_alem_do_consumido():
    iniciados = []
    trava = threading.Lock()

    def avaliar(x):
        with trava:
            iniciados.append(x)
        return x

    gerador = em_ordem(avaliar, range(1000), workers=4, antecipacao=8)
    for item, _, _ in gerador:
        if item == 9:
            break
    gerador.close()
    time.sleep(0.05)
    assert max(iniciados) < 9 + 8 + 1  # no máximo 8 adiante do último consumido


def test_fechar_no_meio_nao_espera_tarefas_longas():
    liberar = threading.Event()

    def demorada(x):
        if x > 0:
            liberar.wait(10)
        return x

    inicio = time.monotonic()
    gerador = em_ordem(demorada, range(6), workers=3)
    assert next(gerador)[0] == 0
    gerador.close()
    assert time.monotonic() - inicio < 2  # não ficou preso esperando as outras
    liberar.set()
