"""Paralelismo leve da coleta (#10): poucas threads, resultados sempre na ordem de entrada.

A coleta é limitada pela latência da API (~0,6 s por chamada), não pela CPU, então threads
bastam. O `GitHubClient` é seguro para threads e coordena cota, pausas e ritmo entre elas.
Com `workers=1` nada de thread é criado: o laço é o sequencial de antes, preguiçoso (avalia
um item só quando o anterior foi consumido). Como os resultados saem na ordem dos itens, a
amostra e os CSVs não dependem do número de workers.
"""

from __future__ import annotations

import concurrent.futures
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

INTERVALO_VERIFICACAO_S = 0.5  # o Ctrl+C só chega à thread principal entre esperas curtas


def em_ordem(
    funcao: Callable[[T], R], itens: Iterable[T], workers: int, antecipacao: int | None = None,
) -> Iterator[tuple[T, R | None, Exception | None]]:
    """Aplica `funcao` a cada item com até `workers` threads; entrega `(item, valor, erro)` na ordem.

    O erro de um item (Exception) vem como valor, na posição do item, para quem consome
    decidir. `antecipacao` limita quantos itens além do último consumido podem ter começado
    (None = todos de uma vez): quem para cedo (o funil ao completar a amostra) não dispara
    trabalho demais. Fechar o gerador cancela o que não começou e não espera o que está
    rodando (o cliente com cache torna esse trabalho aproveitável numa próxima execução).
    """
    if antecipacao is not None and antecipacao < 1:
        raise ValueError("antecipacao deve ser >= 1 (ou None)")
    if workers <= 1:
        for item in itens:
            try:
                valor = funcao(item)
            except Exception as erro:
                yield item, None, erro
            else:
                yield item, valor, None
        return

    limite = antecipacao if antecipacao is not None else float("inf")
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="coleta")
    pendentes: deque[tuple[T, Future]] = deque()
    restantes = iter(itens)

    def abastecer() -> None:
        while len(pendentes) < limite:
            try:
                item = next(restantes)
            except StopIteration:
                return
            pendentes.append((item, executor.submit(funcao, item)))

    try:
        abastecer()
        while pendentes:
            item, futuro = pendentes.popleft()
            while not futuro.done():
                concurrent.futures.wait([futuro], timeout=INTERVALO_VERIFICACAO_S)
            erro = futuro.exception()
            abastecer()  # mantém as threads ocupadas enquanto o consumidor processa
            yield item, (None if erro is not None else futuro.result()), erro
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def mapear(funcao: Callable[[T], R], itens: Iterable[T], workers: int) -> list[R]:
    """`[funcao(i) for i in itens]` com até `workers` threads; levanta o 1º erro na ordem."""
    resultados = []
    for _, valor, erro in em_ordem(funcao, itens, workers):
        if erro is not None:
            raise erro
        resultados.append(valor)
    return resultados
