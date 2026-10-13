"""Concordância entre avaliadores e consenso da amostra-ouro (seção 6 do enunciado)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa

Rotulos = tuple[str, ...]  # um rótulo por avaliador, sempre na mesma ordem (A, B, C)

# Interpretação de Landis & Koch (1977); faixas fechadas à direita.
INTERPRETACAO_INDEFINIDO = "indefinido"
INTERPRETACAO_NEGATIVO = "pobre"
FAIXAS_LANDIS_KOCH: tuple[tuple[float, str], ...] = (
    (0.20, "leve"),
    (0.40, "razoável"),
    (0.60, "moderada"),
    (0.80, "substancial"),
)
INTERPRETACAO_MAXIMA = "quase perfeita"

# Origem do rótulo de consenso.
ORIGEM_UNANIME = "unanime"
ORIGEM_MAIORIA = "maioria"
ORIGEM_PENDENTE = "pendente"

# Tipos de divergência entre três avaliadores.
AVALIADORES_DIVERGENCIA = 3
DIVERGENCIA_2X1 = "2x1"
DIVERGENCIA_1_1_1 = "1-1-1"


def normalizar_rotulo(valor: str | None) -> str:
    """Rótulo sem espaços nas pontas e em minúsculas; `None` vira `""`. Não valida."""
    return "" if valor is None else valor.strip().lower()


def kappa_fleiss(itens: Sequence[Rotulos], categorias: Sequence[str]) -> float | None:
    """Kappa de Fleiss (adimensional, ≤ 1) dos itens, via statsmodels.

    `categorias` são todas as categorias válidas da dimensão (não só as observadas).
    Retorna `None` quando o kappa é indefinido: todos os rótulos na mesma categoria
    (P̄e = 1). Levanta `ValueError` para lista vazia, número de avaliadores variável,
    menos de 2 avaliadores ou rótulo fora de `categorias`.
    """
    if not itens:
        raise ValueError("lista de itens vazia")
    avaliadores = len(itens[0])
    if any(len(rotulos) != avaliadores for rotulos in itens):
        raise ValueError("todos os itens devem ter o mesmo número de avaliadores")
    if avaliadores < 2:
        raise ValueError("kappa exige pelo menos 2 avaliadores")
    indice = {categoria: i for i, categoria in enumerate(categorias)}
    fora = {r for rotulos in itens for r in rotulos if r not in indice}
    if fora:
        raise ValueError(f"rótulos fora das categorias válidas: {sorted(fora)}")
    if len({r for rotulos in itens for r in rotulos}) == 1:
        return None
    dados = [[indice[r] for r in rotulos] for rotulos in itens]
    tabela, _ = aggregate_raters(dados, n_cat=len(categorias))
    return float(fleiss_kappa(tabela, method="fleiss"))


def concordancia_observada(itens: Sequence[Rotulos]) -> float:
    """Fração (0–1) dos itens em que todos os avaliadores deram o mesmo rótulo."""
    if not itens:
        raise ValueError("lista de itens vazia")
    unanimes = sum(1 for rotulos in itens if len(set(rotulos)) == 1)
    return unanimes / len(itens)


def interpretar_kappa(kappa: float | None) -> str:
    """Faixa de Landis & Koch (1977) do kappa; `"indefinido"` para `None`."""
    if kappa is None:
        return INTERPRETACAO_INDEFINIDO
    if kappa < 0:
        return INTERPRETACAO_NEGATIVO
    for limite, interpretacao in FAIXAS_LANDIS_KOCH:
        if kappa <= limite:
            return interpretacao
    return INTERPRETACAO_MAXIMA


def tipo_divergencia(rotulos: Rotulos) -> str | None:
    """`None` se unânime, `"1-1-1"` se todos diferentes, senão `"2x1"` (3 avaliadores)."""
    if len(rotulos) != AVALIADORES_DIVERGENCIA:
        raise ValueError(f"tipo de divergência definido para {AVALIADORES_DIVERGENCIA} avaliadores")
    distintos = len(set(rotulos))
    if distintos == 1:
        return None
    if distintos == len(rotulos):
        return DIVERGENCIA_1_1_1
    return DIVERGENCIA_2X1


def consenso(rotulos: Rotulos) -> tuple[str | None, str]:
    """Rótulo de consenso e sua origem: unânime, maioria estrita ou pendente (sem maioria)."""
    rotulo, votos = Counter(rotulos).most_common(1)[0]
    if votos == len(rotulos):
        return rotulo, ORIGEM_UNANIME
    if 2 * votos > len(rotulos):
        return rotulo, ORIGEM_MAIORIA
    return None, ORIGEM_PENDENTE
