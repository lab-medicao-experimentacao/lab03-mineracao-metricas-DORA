"""Coleta de workflow runs do default branch, fatiada por mês (#9).

`GET /repos/{o}/{r}/actions/runs` com filtros devolve no máximo 1.000 resultados
por consulta. A janela é dividida em meses civis (UTC) e cada mês vira uma
consulta; se algum mês chegar ao teto, há runs que a API não entregou e o mês é
registrado e avisado (nunca ignorado em silêncio).

O filtro `event=push` e `branch=<default_branch>` é aplicado pela API. Runs com
`conclusion` ignorada (cancelled etc.) são coletados e gravados com a classe
`ignorado`; quem conta os válidos é `metricas.run_valido`.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from metricas import EVENTO_RUN_VALIDO, classe_conclusao
from pipeline.config import Janela
from pipeline.selecao import ClienteGitHub

log = logging.getLogger(__name__)

CAMINHO_RUNS = "/repos/{full_name}/actions/runs"
TETO_RUNS = 1000  # limite da API por consulta com filtros (não é parâmetro do estudo)
POR_PAGINA = 100  # máximo aceito pela API
ARQUIVO_RUNS = "runs.csv"
ARQUIVO_SATURADOS = "runs_meses_saturados.csv"
COLUNAS_RUNS = (
    "full_name", "id", "workflow_id", "event", "head_branch", "conclusion", "classe",
    "created_at", "run_started_at", "updated_at",
)


@dataclass(frozen=True)
class ResultadoRuns:
    """Runs da janela e os meses cuja consulta bateu o teto de 1.000 resultados."""

    runs: list[dict]
    meses_saturados: tuple[str, ...]  # filtros `created` ('AAAA-MM-DD..AAAA-MM-DD')


# --- transformação (pura) -------------------------------------------------------


def fatias_mensais(janela: Janela) -> list[tuple[date, date]]:
    """Divide a janela em meses civis UTC: lista de (primeiro_dia, ultimo_dia), inclusivos.

    O primeiro e o último mês ficam parciais se a janela não começar/terminar
    nos limites de um mês. As fatias cobrem a janela inteira, sem lacunas nem
    sobreposição.
    """
    ultimo_dia = (janela.fim - timedelta(days=1)).date()
    atual = janela.inicio.date()
    fatias = []
    while atual <= ultimo_dia:
        primeiro_do_proximo_mes = (atual.replace(day=1) + timedelta(days=32)).replace(day=1)
        fim_fatia = min(primeiro_do_proximo_mes - timedelta(days=1), ultimo_dia)
        fatias.append((atual, fim_fatia))
        atual = fim_fatia + timedelta(days=1)
    return fatias


def filtro_created(fatia: tuple[date, date]) -> str:
    """Valor do parâmetro `created` da API para uma fatia (AAAA-MM-DD..AAAA-MM-DD)."""
    return f"{fatia[0].isoformat()}..{fatia[1].isoformat()}"


def converter_run(item: dict) -> dict:
    """Converte um run da API para o contrato Run (datas em UTC).

    `run_started_at` ausente cai para `created_at`.
    """
    criado = _data_utc(item["created_at"])
    return {
        "id": int(item["id"]),
        "workflow_id": int(item["workflow_id"]),
        "event": item["event"],
        "head_branch": item["head_branch"],
        "conclusion": item.get("conclusion"),
        "created_at": criado,
        "run_started_at": _data_utc(item["run_started_at"]) if item.get("run_started_at") else criado,
        "updated_at": _data_utc(item["updated_at"]),
    }


def _data_utc(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(timezone.utc)


# --- coleta (rede, via cliente) -------------------------------------------------


def coletar_runs(
    cliente: ClienteGitHub, full_name: str, default_branch: str, janela: Janela
) -> ResultadoRuns:
    """Runs de push no default branch criados na janela, uma consulta por mês.

    Um mês que devolve 1.000 runs (o teto da API) é avisado e listado em
    `meses_saturados`: os runs além do teto não foram entregues pela API.
    """
    por_id: dict[int, dict] = {}
    saturados: list[str] = []
    for fatia in fatias_mensais(janela):
        periodo = filtro_created(fatia)
        itens = cliente.get_paginated(
            CAMINHO_RUNS.format(full_name=full_name),
            {
                "branch": default_branch,
                "event": EVENTO_RUN_VALIDO,
                "created": periodo,
                "per_page": POR_PAGINA,
            },
            item_key="workflow_runs",
        )
        if len(itens) >= TETO_RUNS:
            saturados.append(periodo)
            log.warning(
                "%s: %s retornou %d runs (teto da API): podem faltar runs neste mês",
                full_name, periodo, len(itens),
            )
        for item in itens:
            por_id[int(item["id"])] = converter_run(item)
    runs = sorted(por_id.values(), key=lambda r: (r["created_at"], r["id"]))
    log.info("%s: %d runs coletados em %d meses", full_name, len(runs), len(fatias_mensais(janela)))
    return ResultadoRuns(runs, tuple(saturados))


class RunsColetados:
    """Coletor da etapa 5 do funil (`runs_de` de `executar_funil`), ligado a `coletar_runs`.

    Não guarda os runs em memória (um repositório muito ativo chega a 12 mil runs):
    registra só os meses saturados por repositório. `da_amostra` recoleta a amostra
    final, o que não gera novas chamadas enquanto o cliente usar o cache em disco.
    """

    def __init__(self, cliente: ClienteGitHub, janela: Janela):
        self._cliente = cliente
        self._janela = janela
        self.saturados: dict[str, tuple[str, ...]] = {}

    def __call__(self, repo: dict) -> list[dict]:
        resultado = coletar_runs(
            self._cliente, repo["full_name"], repo["default_branch"], self._janela
        )
        if resultado.meses_saturados:
            self.saturados[repo["full_name"]] = resultado.meses_saturados
        return resultado.runs

    def da_amostra(self, amostra: Iterable[dict]) -> dict[str, list[dict]]:
        """Runs de cada repositório da amostra, na ordem da amostra."""
        return {r["full_name"]: self(r) for r in amostra}


# --- disco ----------------------------------------------------------------------


def salvar_runs(runs_por_repo: Mapping[str, Iterable[dict]], dir_processados: Path) -> Path:
    """Salva os runs em ``runs.csv``, com a coluna `classe` (sucesso, falha ou ignorado)."""
    caminho = Path(dir_processados) / ARQUIVO_RUNS
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_RUNS)
        escritor.writeheader()
        for full_name, runs in runs_por_repo.items():
            for run in runs:
                escritor.writerow({
                    "full_name": full_name,
                    **run,
                    "conclusion": run["conclusion"] or "",
                    "classe": classe_conclusao(run["conclusion"]),
                    "created_at": run["created_at"].isoformat(),
                    "run_started_at": run["run_started_at"].isoformat(),
                    "updated_at": run["updated_at"].isoformat(),
                })
    return caminho


def salvar_meses_saturados(
    saturados_por_repo: Mapping[str, Iterable[str]], dir_processados: Path
) -> Path:
    """Salva em ``runs_meses_saturados.csv`` (`full_name`, `periodo`) os meses no teto de 1.000.

    Arquivo só com cabeçalho = nenhum mês da amostra bateu o teto (o enunciado pede
    para conferir isso).
    """
    caminho = Path(dir_processados) / ARQUIVO_SATURADOS
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=("full_name", "periodo"))
        escritor.writeheader()
        for full_name, periodos in saturados_por_repo.items():
            for periodo in periodos:
                escritor.writerow({"full_name": full_name, "periodo": periodo})
    return caminho
