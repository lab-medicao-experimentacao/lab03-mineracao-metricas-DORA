"""Change failure rate (RQ 03): proxies de CI (a) e de entrega (b)."""
from __future__ import annotations

from bisect import bisect_right
import re
from collections.abc import Iterable
from datetime import datetime, timedelta

from metricas import classe_conclusao


PRAZO_CORRECAO = timedelta(days=7)
_NUMERO = r"(0|[1-9][0-9]*)"
_SEMVER = re.compile(
    rf"v?{_NUMERO}\.{_NUMERO}\.{_NUMERO}"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
_MENSAGEM_CORRETIVA = re.compile(r"\b(?:revert|hotfix|fix)\b", re.IGNORECASE)


def release_corretiva(release: dict, anterior: dict | None, commits: list[dict]) -> bool:
    """Identifica uma release corretiva (booleano); heurística inicial da #28.

    Apenas releases principais publicadas. Detecta aumento de patch mantendo
    major/minor em tags SemVer estáveis (prefixo v e build opcionais), OU uma
    palavra inteira fix/revert/hotfix, sem distinção de caixa, nas mensagens.
    Tags de outros formatos dependem apenas das mensagens disponíveis.
    Sem antecessora, só as mensagens podem indicar correção.
    """
    if release["draft"] or release["prerelease"] or release["published_at"] is None:
        return False
    if any(_MENSAGEM_CORRETIVA.search(c["message"]) for c in commits):
        return True
    atual = _SEMVER.fullmatch(release["tag_name"])
    previa = _SEMVER.fullmatch(anterior["tag_name"]) if anterior is not None else None
    if atual is None or previa is None:
        return False
    versao = tuple(map(int, atual.groups()))
    base = tuple(map(int, previa.groups()))
    return versao[:2] == base[:2] and versao[2] > base[2]


def cfr_entrega(
    releases: list[dict], commits_por_release: dict[str, list[dict]], fim_janela: datetime,
) -> dict:
    """CFR de entrega (fração 0–1 ou None) e contagens de avaliação/censura.

    Recebe releases já restritas ao início da janela (contrato #28); filtra drafts,
    pré-releases, datas ausentes e publicações em/depois de fim_janela (exclusivo).
    Ordena por publicação e tag; a antecessora usada na heurística é a release
    principal imediatamente anterior nessa ordem. Uma release falhou se existe
    qualquer corretiva estritamente posterior, em até 7 dias (inclusive).
    Publicações em [fim_janela - 7 dias, fim_janela) são sempre censuradas,
    inclusive quando já se observa correção. Sem avaliáveis, cfr = None.
    Não altera os dados recebidos nem consulta rede/disco.
    """
    publicadas = sorted(
        (r for r in releases if not r["draft"] and not r["prerelease"]
         and r["published_at"] is not None and r["published_at"] < fim_janela),
        key=lambda r: (r["published_at"], r["tag_name"]),
    )
    datas_corretivas = []
    anterior = None
    for release in publicadas:
        if release_corretiva(release, anterior, commits_por_release.get(release["tag_name"], [])):
            datas_corretivas.append(release["published_at"])
        anterior = release

    n_avaliadas = n_falharam = n_censuradas = 0
    for release in publicadas:
        data = release["published_at"]
        if data >= fim_janela - PRAZO_CORRECAO:
            n_censuradas += 1
            continue
        n_avaliadas += 1
        indice = bisect_right(datas_corretivas, data)
        if (indice < len(datas_corretivas)
                and datas_corretivas[indice] - data <= PRAZO_CORRECAO):
            n_falharam += 1
    return {
        "cfr": n_falharam / n_avaliadas if n_avaliadas else None,
        "n_avaliadas": n_avaliadas,
        "n_falharam": n_falharam,
        "n_censuradas": n_censuradas,
    }


def cfr_ci(runs: Iterable[dict]) -> float | None:
    """Fração (0–1) de workflow runs com falha: falhas ÷ (falhas + sucessos).

    Classifica pelo `conclusion` (seção 3 do enunciado): `success` é sucesso;
    `failure`, `timed_out` e `startup_failure` são falhas; qualquer outro valor
    (cancelled, skipped, neutral, action_required, stale, None) é ignorado e não
    entra no numerador nem no denominador.

    Espera runs já restritos ao default branch, a `event = push` e à janela
    (ver `metricas.run_valido`). Retorna None quando não há nenhum run com
    sucesso ou falha (nunca 0 por padrão).
    """
    falhas = sucessos = 0
    for run in runs:
        classe = classe_conclusao(run["conclusion"])
        if classe == "falha":
            falhas += 1
        elif classe == "sucesso":
            sucessos += 1
    total = falhas + sucessos
    if total == 0:
        return None
    return falhas / total
