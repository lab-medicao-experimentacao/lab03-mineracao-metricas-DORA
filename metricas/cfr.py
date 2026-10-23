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
_MENSAGEM_CORRETIVA = re.compile(r"\b(?:revert(?:s|ed)?|hotfix|bugfix|fix(?:es|ed)?)\b", re.IGNORECASE)
_MANUTENCAO = re.compile(
    r"^(?:merge\b|(?:chore|build|ci|docs?|test|style)(?:\([^)]*\))?!?:|"
    r"bump\b|(?:update|upgrade) (?:dependency|dependencies|translations?|readme)\b|"
    r"(?:release|released|prepare release|next development version|automatic translations|"
    r"version bump|increment version|set version|version|cutting new release)\b|"
    r"update (?:changelog|docs?|ci|release)\b|"
    r"`?v?\d+\.\d+\.\d+\b)", re.IGNORECASE,
)
_CORRECAO_MANUTENCAO = re.compile(
    r"\b(?:typos?|spelling|readme|docs?|documentation|translations?)\b|"
    r"^(?:fix|bugfix)\((?:deps|deps-dev|ci|build|docs?|test)\):", re.IGNORECASE,
)
_FUNCIONALIDADE = re.compile(
    r"\b(?:feat|features?|add(?:s|ed)?|introduc(?:e|es|ed)|new|support)\b", re.IGNORECASE,
)
_TAG_COM_PACOTE = re.compile(
    rf"(?P<prefixo>.*[/@-])(?P<versao>v?{_NUMERO}\.{_NUMERO}\.{_NUMERO}"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?)"
)


def _versao_tag(tag: str) -> tuple[str, tuple[int, ...]] | None:
    """Separa namespace e SemVer; só compara tags do mesmo namespace."""
    simples = _SEMVER.fullmatch(tag)
    if simples:
        return "", tuple(map(int, simples.groups()))
    composta = _TAG_COM_PACOTE.fullmatch(tag)
    if composta:
        versao = _SEMVER.fullmatch(composta["versao"])
        return composta["prefixo"], tuple(map(int, versao.groups()))
    return None


def release_corretiva(release: dict, anterior: dict | None, commits: list[dict]) -> bool:
    """Identifica uma release corretiva (booleano); refinamento v3 da #34.

    Apenas releases principais publicadas. Usa o título de cada commit;
    merges e manutenção explícita (documentação, dependências, CI, testes,
    publicação e tradução) não votam. Exige maioria estrita de títulos com
    fix/fixes/fixed, bugfix, hotfix ou revert/reverts/reverted nas mudanças
    restantes quando há funcionalidades explícitas (feat/add/new/support).
    Sem funcionalidades explícitas, basta um título corretivo ou aumento de
    patch SemVer no mesmo namespace, inclusive tags com prefixo de pacote.
    Sem commits, usa apenas patch; só manutenção não é correção.
    Não consulta rótulos, repositórios específicos, rede ou disco.
    """
    if release["draft"] or release["prerelease"] or release["published_at"] is None:
        return False
    atual = _versao_tag(release["tag_name"])
    previa = _versao_tag(anterior["tag_name"]) if anterior is not None else None
    patch = bool(atual and previa and atual[0] == previa[0]
                 and atual[1][:2] == previa[1][:2] and atual[1][2] > previa[1][2])
    if commits:
        titulos = [c["message"].strip().splitlines()[0] if c["message"].strip() else ""
                   for c in commits]
        informativos = [t for t in titulos if t and not _MANUTENCAO.search(t)
                        and not _CORRECAO_MANUTENCAO.search(t)]
        n_correcoes = sum(bool(_MENSAGEM_CORRETIVA.search(t)) for t in informativos)
        tem_funcionalidade = any(_FUNCIONALIDADE.search(t) and not _MENSAGEM_CORRETIVA.search(t)
                                for t in informativos)
        if tem_funcionalidade:
            return n_correcoes > len(informativos) / 2
        return bool(informativos) and (n_correcoes > 0 or patch)
    return patch


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
