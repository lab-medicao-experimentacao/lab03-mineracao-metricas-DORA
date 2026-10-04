"""Ponto de entrada único: python -m pipeline --config config.yaml"""

from __future__ import annotations

import argparse
import logging
import sys

from pipeline.config import ErroConfiguracao, carregar_config, ler_token

log = logging.getLogger("pipeline")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline", description="Mineração de métricas DORA")
    parser.add_argument("--config", default="config.yaml", help="caminho do config.yaml")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        config = carregar_config(args.config)
        ler_token()
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

    # Etapas do pipeline, conectadas conforme as Issues forem integradas:
    #   seleção (#3) → metadados (#4) → releases (#7) → commits (#8)
    #   → workflow runs (#9) → funil e amostra (#5)
    # TODO(#2, #5): ligar a seleção quando o GitHubClient (#2) existir:
    #   repos = selecao.buscar_candidatos(cliente, config.faixas_estrelas)
    #   selecao.salvar_candidatos(repos, config.dir_saida)
    log.info("nenhuma etapa de coleta integrada ainda")
    return 0


if __name__ == "__main__":
    sys.exit(main())
