"""Ponto de entrada único: python -m pipeline --config config.yaml"""

from __future__ import annotations

import argparse
import logging
import sys

from pipeline import commits, funil, metadados, releases, selecao, workflow_runs
from pipeline.config import Config, ErroConfiguracao, carregar_config, carregar_dotenv, ler_token
from pipeline.github_client import GitHubClient
from pipeline.paralelo import mapear
from pipeline.selecao import ClienteGitHub

log = logging.getLogger("pipeline")

ARQUIVO_ENV = ".env"  # na pasta de execução; ignorado pelo git


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline", description="Mineração de métricas DORA")
    parser.add_argument("--config", default="config.yaml", help="caminho do config.yaml")
    parser.add_argument(
        "--funil-completo", action="store_true",
        help="avalia todos os candidatos no funil (custo máximo; a amostra não muda)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        config = carregar_config(args.config)
        if carregar_dotenv(ARQUIVO_ENV):
            log.info("variáveis lidas de %s", ARQUIVO_ENV)
        token = ler_token()
    except ErroConfiguracao as e:
        log.error("%s", e)
        return 2

    for pasta in (config.dir_cache, config.dir_processados, config.dir_saida):
        pasta.mkdir(parents=True, exist_ok=True)

    log.info(
        "janela %s (%.1f semanas), amostra=%d, semente=%d",
        config.janela.filtro_created(), config.janela.semanas,
        config.tamanho_amostra, config.semente,
    )

    # no máximo `workers` requisições em voo, mesmo com tarefas da antecipação do funil
    # ainda terminando enquanto a etapa seguinte começa
    cliente = GitHubClient(token, config.dir_cache, max_simultaneas=config.workers)
    try:
        executar(cliente, config, avaliar_todos=args.funil_completo)
    except KeyboardInterrupt:
        log.warning(
            "interrompido: as respostas já baixadas estão em %s; rode o mesmo comando "
            "para continuar de onde parou", config.dir_cache,
        )
        return 130
    finally:
        # threads ainda ativas (antecipação do funil, Ctrl+C) acordam e param sem nova chamada
        cancelar = getattr(cliente, "cancelar", None)
        if cancelar is not None:
            cancelar()
        log.info(
            "requisições à rede nesta execução: %d (respostas do cache: %d)",
            getattr(cliente, "requisicoes_rede", 0), getattr(cliente, "acertos_cache", 0),
        )
    return 0


def executar(cliente: ClienteGitHub, config: Config, avaliar_todos: bool = False) -> None:
    """Seleção (#3) → funil (#5) → metadados (#4) → releases/tags (#7) → commits (#8) → runs (#9).

    Só a amostra do funil é enriquecida e tem commits, tags e runs gravados. Rodar de novo
    reaproveita o cache em disco do cliente (#10). A busca é sequencial (30 req/min); o
    funil e as coletas da amostra usam `config.workers` threads, com resultados na ordem
    da amostra (os arquivos não dependem do número de workers).
    """
    candidatos = selecao.buscar_candidatos(cliente, config.faixas_estrelas)
    selecao.salvar_candidatos(candidatos, config.dir_saida)

    releases_de = funil.ReleasesColetadas(cliente)
    runs_de = workflow_runs.RunsColetados(cliente, config.janela, limiar=config.min_runs)
    resultado = funil.executar_funil(
        candidatos, config,
        usa_actions=lambda r: funil.usa_github_actions(cliente, r["full_name"]),
        releases_de=releases_de, runs_de=runs_de, avaliar_todos=avaliar_todos,
        teto_runs=runs_de.teto,
    )
    funil.salvar_funil(resultado.etapas, config.dir_saida)

    workers = config.workers
    amostra = metadados.enriquecer_metadados(cliente, resultado.amostra, config.janela, workers)
    metadados.salvar_repos(amostra, config.dir_saida)
    nomes = [r["full_name"] for r in amostra]

    releases_por_repo = releases_de.da_amostra(amostra)
    releases.salvar_releases(releases_por_repo, config.dir_processados)
    tags = mapear(lambda nome: releases.coletar_tags(cliente, nome), nomes, workers)
    releases.salvar_tags(dict(zip(nomes, tags)), config.dir_processados)

    # um repositório por vez, com os compares dele em paralelo: um repositório com
    # centenas de releases não vira uma cauda longa sequencial
    resultados_commits = {
        nome: commits.coletar_commits_entre_releases(
            cliente, nome, releases_por_repo[nome], config.janela, workers=workers)
        for nome in nomes
    }
    commits.salvar_commits(
        {nome: r.commits_por_release for nome, r in resultados_commits.items()},
        config.dir_processados,
    )
    commits.salvar_releases_sem_compare(resultados_commits, config.dir_processados)

    workflow_runs.salvar_runs(runs_de.da_amostra(amostra, workers), config.dir_processados)
    # cópia: threads da antecipação do funil ainda podem anotar repositórios fora da amostra
    saturados = dict(runs_de.saturados)
    saturados_amostra = {nome: saturados.get(nome, ()) for nome in nomes}
    workflow_runs.salvar_meses_saturados(saturados_amostra, config.dir_processados)
    com_teto = sorted(nome for nome, periodos in saturados_amostra.items() if periodos)
    if com_teto:
        log.warning(
            "%d repositórios da amostra com meses no teto de 1.000 runs: %s",
            len(com_teto), ", ".join(com_teto),
        )


if __name__ == "__main__":
    sys.exit(main())
