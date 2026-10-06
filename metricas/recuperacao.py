"""Tempo de recuperação após falha de CI (RQ 04)."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from statistics import median

from metricas import classe_conclusao


def episodios_recuperacao(runs: Iterable[dict], fim_janela: datetime) -> list[dict]:
    """Episódios de falha de cada workflow, ordenados por início.

    Cada workflow (`workflow_id`) é percorrido em ordem cronológica de `created_at`
    (desempate por `id`). Runs ignorados (cancelled, skipped etc.) não começam nem
    encerram episódio. Um episódio começa na primeira falha depois de um sucesso e
    termina no próximo sucesso do mesmo workflow; falhas anteriores ao primeiro
    sucesso observado não abrem episódio, porque não se sabe quando a falha começou.

    Cada item tem `inicio` (`run_started_at` da primeira falha), `fim`
    (`updated_at` do sucesso), `horas` (fim − início, em horas) e `censurado=False`.
    Episódio sem sucesso posterior até `fim_janela` é censurado: `fim = fim_janela`
    e `horas` é o tempo decorrido até lá (limite inferior do tempo real).

    A API redefine `run_started_at` a cada re-run; se ele ficar depois do
    `fim` do episódio (duração negativa), o início passa a ser o `created_at` da
    falha, que não muda no re-run.

    Espera runs já restritos ao default branch, a `event = push` e à janela
    (ver `metricas.run_valido`).
    """
    por_workflow: dict[int, list[dict]] = defaultdict(list)
    for run in runs:
        if classe_conclusao(run["conclusion"]) != "ignorado":
            por_workflow[run["workflow_id"]].append(run)

    episodios: list[dict] = []
    for execucoes in por_workflow.values():
        execucoes.sort(key=lambda r: (r["created_at"], r["id"]))
        visto_sucesso = False
        falha: dict | None = None  # primeira falha do episódio aberto
        for run in execucoes:
            if classe_conclusao(run["conclusion"]) == "sucesso":
                if falha is not None:
                    episodios.append(_episodio(falha, run["updated_at"], censurado=False))
                    falha = None
                visto_sucesso = True
            elif visto_sucesso and falha is None:
                falha = run
        if falha is not None:
            episodios.append(_episodio(falha, fim_janela, censurado=True))

    episodios.sort(key=lambda e: e["inicio"])
    return episodios


def tempo_recuperacao(runs: Iterable[dict], fim_janela: datetime) -> dict:
    """Resumo do repositório: `mediana_horas`, `n_episodios` e `prop_censurados` (0–1).

    A mediana inclui os episódios censurados com o tempo decorrido até `fim_janela`
    (nunca são descartados; descartá-los faria o repositório parecer mais rápido).
    Sem episódios, `mediana_horas` e `prop_censurados` são None e `n_episodios` é 0.
    """
    episodios = episodios_recuperacao(runs, fim_janela)
    if not episodios:
        return {"mediana_horas": None, "n_episodios": 0, "prop_censurados": None}
    censurados = sum(e["censurado"] for e in episodios)
    return {
        "mediana_horas": median(e["horas"] for e in episodios),
        "n_episodios": len(episodios),
        "prop_censurados": censurados / len(episodios),
    }


def _episodio(falha: dict, fim: datetime, censurado: bool) -> dict:
    inicio = falha["run_started_at"]
    if inicio > fim:  # run reexecutado depois do fim do episódio
        inicio = falha["created_at"]
    return {
        "inicio": inicio,
        "fim": fim,
        "horas": (fim - inicio) / timedelta(hours=1),
        "censurado": censurado,
    }
