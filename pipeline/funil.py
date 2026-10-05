"""Funil de seleção e amostra do S01 (#5).

Etapas, da mais barata para a mais cara em cota de API (DIRETRIZES 6.3):

1. candidatos da busca (#3) — sem custo extra;
2. sem fork e não arquivado — campos que a busca já traz, sem custo;
3. usa GitHub Actions — 1 chamada a `/actions/workflows` (`total_count > 0`);
4. ≥ `min_releases` releases publicadas na janela — coleta de releases (#7, B), via
   `ReleasesColetadas`;
5. ≥ `min_runs` runs válidos na janela — coleta de workflow runs (#9, C), a mais cara;
6. amostra: candidatos em ordem aleatória (semente do config) até reunir `tamanho_amostra`.

As etapas 3–5 recebem os dados por funções (`usa_actions`, `releases_de`, `runs_de`, cada
uma recebe o registro Repo) para serem testadas com fixtures agora e ligadas aos coletores
de B e C depois. As definições de release publicada e de run válido vêm de `metricas/`.

**Avaliação sob demanda.** As etapas 1–2 valem para todos (custo zero). Os sobreviventes são
embaralhados *antes* de qualquer chamada e as etapas 3–5 são avaliadas candidato a candidato,
nessa ordem e com curto-circuito (só coleta runs de quem passou em releases), até a amostra
encher; os demais nunca são consultados. Como as contagens continuam significativas:

- a linha `ETAPA_AVALIADOS`, logo após a etapa 2, retira do funil quem não chegou a ser
  avaliado; as etapas 3–5 contam apenas avaliados. Assim toda linha obedece
  `n_restantes = n_restantes anterior − n_descartados` e o funil.csv fecha;
- a ordem é sorteada antes de olhar qualquer dado, então os avaliados são uma amostra
  aleatória simples dos sobreviventes da etapa 2: as *proporções* de descarte nas etapas 3–5
  estimam as da população de candidatos (com leve viés da regra de parada, que encerra no
  k-ésimo elegível). Os números absolutos dessas etapas são "dos avaliados", não "dos candidatos";
- a amostra é a mesma com ou sem avaliação completa: são os `tamanho_amostra` primeiros
  elegíveis da ordem aleatória. `avaliar_todos=True` avalia todos (funil completo, custo
  máximo) e descarta na última linha os elegíveis além da amostra;
- com a mesma semente, ampliar a amostra (100 → 300 no S02) mantém os já sorteados como
  prefixo e reavalia os mesmos candidatos, reaproveitando o cache.

Regenerar o funil sem novas chamadas é responsabilidade do cliente (#10): toda consulta passa
pelo `GitHubClient`/coletores, e a mesma semente reavalia exatamente os mesmos candidatos.

Forks: a Search API omite forks sem `fork:true` na consulta (DIRETRIZES, seção 1), então hoje
a etapa 2 descarta 0 forks — o funil registra "fork: 0" e o log avisa.
"""

from __future__ import annotations

import csv
import logging
import random
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from metricas import run_valido
from metricas.frequencia import releases_publicadas
from pipeline.config import Config, Janela
from pipeline.releases import coletar_releases
from pipeline.selecao import ClienteGitHub, corpo_json

log = logging.getLogger(__name__)

CAMINHO_WORKFLOWS = "/repos/{full_name}/actions/workflows"
ARQUIVO_FUNIL = "funil.csv"
COLUNAS_FUNIL = ("etapa", "n_restantes", "n_descartados", "motivo")  # contrato 5.4

ETAPA_CANDIDATOS = "candidatos da busca"
ETAPA_CADASTRAL = "sem fork e não arquivado"
ETAPA_AVALIADOS = "avaliados em ordem aleatória"
ETAPA_ACTIONS = "usa GitHub Actions"
ETAPA_AMOSTRA = "amostra final"

MOTIVO_FORK = "fork"
MOTIVO_ARQUIVADO = "arquivado"

UsaActions = Callable[[dict], bool]          # Repo → usa GitHub Actions?
ColetorReleases = Callable[[dict], list[dict]]  # Repo → list[Release] (contrato 5.2)
ColetorRuns = Callable[[dict], list[dict]]      # Repo → list[Run] (contrato 5.2)


@dataclass(frozen=True)
class EtapaFunil:
    """Uma linha do funil.csv (contagens em número de repositórios)."""

    etapa: str
    n_restantes: int
    n_descartados: int
    motivo: str


@dataclass(frozen=True)
class ResultadoFunil:
    amostra: list[dict]       # registros Repo, na ordem do sorteio
    etapas: list[EtapaFunil]  # linhas do funil, em ordem de execução
    n_avaliados: int          # candidatos que passaram pelas etapas 3–5


# --- critérios (puros) ------------------------------------------------------------


def motivo_exclusao_cadastral(repo: dict, excluir_forks: bool, excluir_arquivados: bool) -> str | None:
    """Motivo de descarte na etapa 2 ('fork' ou 'arquivado'), ou None se o repo passa.

    Um repo fork e arquivado é contado uma única vez, como fork.
    """
    if excluir_forks and repo["fork"]:
        return MOTIVO_FORK
    if excluir_arquivados and repo["archived"]:
        return MOTIVO_ARQUIVADO
    return None


def contar_releases_validas(releases: Iterable[dict], janela: Janela) -> int:
    """Número de releases que contam como deploy (não draft, não pré-release) na janela."""
    return len(releases_publicadas(releases, janela.inicio, janela.fim))


def contar_runs_validos(runs: Iterable[dict], default_branch: str, janela: Janela) -> int:
    """Número de runs válidos (push, default branch, sucesso/falha) criados na janela."""
    return sum(1 for r in runs if run_valido(r, default_branch, janela.inicio, janela.fim))


def ordem_aleatoria(repos: Iterable[dict], semente: int) -> list[dict]:
    """Nova lista embaralhada com `random.Random(semente)`.

    Ordena por `full_name` antes de embaralhar, para o sorteio não depender da ordem de entrada.
    """
    ordem = sorted(repos, key=lambda r: r["full_name"])
    random.Random(semente).shuffle(ordem)
    return ordem


# --- funil (as etapas 3–5 consultam a API pelas funções recebidas) ------------------


def executar_funil(
    candidatos: Iterable[dict],
    config: Config,
    usa_actions: UsaActions,
    releases_de: ColetorReleases,
    runs_de: ColetorRuns,
    avaliar_todos: bool = False,
) -> ResultadoFunil:
    """Aplica as etapas 1–6 e devolve a amostra e as linhas do funil.

    Por padrão para de avaliar ao reunir `config.tamanho_amostra` elegíveis (ver docstring
    do módulo). Com menos elegíveis que o tamanho pedido, avisa e devolve os que existem.
    """
    candidatos = list(candidatos)
    janela = config.janela

    excluidos: Counter[str] = Counter()
    cadastrais = []
    for repo in candidatos:
        motivo = motivo_exclusao_cadastral(repo, config.excluir_forks, config.excluir_arquivados)
        if motivo is None:
            cadastrais.append(repo)
        else:
            excluidos[motivo] += 1
    if config.excluir_forks and candidatos and not any(r["fork"] for r in candidatos):
        log.info("nenhum fork entre os candidatos: a Search API omite forks sem `fork:true` na consulta")

    elegiveis: list[dict] = []
    sem_actions = poucas_releases = poucos_runs = avaliados = 0
    for repo in ordem_aleatoria(cadastrais, config.semente):
        if not avaliar_todos and len(elegiveis) >= config.tamanho_amostra:
            break
        avaliados += 1
        nome = repo["full_name"]
        if not usa_actions(repo):
            sem_actions += 1
            log.debug("%s: sem GitHub Actions", nome)
            continue
        n_releases = contar_releases_validas(releases_de(repo), janela)
        if n_releases < config.min_releases:
            poucas_releases += 1
            log.debug("%s: %d releases na janela", nome, n_releases)
            continue
        n_runs = contar_runs_validos(runs_de(repo), repo["default_branch"], janela)
        if n_runs < config.min_runs:
            poucos_runs += 1
            log.debug("%s: %d runs válidos na janela", nome, n_runs)
            continue
        elegiveis.append(repo)
        log.info("%s elegível (%d/%d)", nome, len(elegiveis), config.tamanho_amostra)

    amostra = elegiveis[: config.tamanho_amostra]
    etapas = _montar_etapas(
        config, len(candidatos), excluidos, len(cadastrais), avaliados,
        sem_actions, poucas_releases, poucos_runs, len(elegiveis), len(amostra),
    )

    log.info("%d avaliados de %d candidatos após a etapa 2", avaliados, len(cadastrais))
    if len(amostra) < config.tamanho_amostra:
        log.warning(
            "amostra incompleta: %d de %d elegíveis (todos os %d candidatos foram avaliados)",
            len(amostra), config.tamanho_amostra, len(cadastrais),
        )
    return ResultadoFunil(amostra=amostra, etapas=etapas, n_avaliados=avaliados)


def _montar_etapas(
    config: Config,
    n_candidatos: int,
    excluidos: Counter[str],
    n_cadastrais: int,
    n_avaliados: int,
    sem_actions: int,
    poucas_releases: int,
    poucos_runs: int,
    n_elegiveis: int,
    n_amostra: int,
) -> list[EtapaFunil]:
    if config.excluir_forks or config.excluir_arquivados:
        partes = []
        if config.excluir_forks:
            partes.append(f"{MOTIVO_FORK}: {excluidos[MOTIVO_FORK]}")
        if config.excluir_arquivados:
            partes.append(f"{MOTIVO_ARQUIVADO}: {excluidos[MOTIVO_ARQUIVADO]}")
        motivo_cadastral = "; ".join(partes)
    else:
        motivo_cadastral = "filtro desativado em config.yaml"

    descartes = [
        (ETAPA_CANDIDATOS, 0, "resultado da busca por faixas de estrelas"),
        (ETAPA_CADASTRAL, n_candidatos - n_cadastrais, motivo_cadastral),
        (ETAPA_AVALIADOS, n_cadastrais - n_avaliados,
         f"não avaliados: amostra de {config.tamanho_amostra} completada antes "
         f"(semente {config.semente}); as etapas seguintes contam só os avaliados"),
        (ETAPA_ACTIONS, sem_actions, "sem workflows (actions/workflows com total_count = 0)"),
        (f">= {config.min_releases} releases publicadas na janela", poucas_releases,
         f"menos de {config.min_releases} releases não draft e não pré-release na janela"),
        (f">= {config.min_runs} runs válidos na janela", poucos_runs,
         f"menos de {config.min_runs} runs de push no default branch com sucesso/falha na janela"),
        (ETAPA_AMOSTRA, n_elegiveis - n_amostra,
         f"elegíveis além dos {config.tamanho_amostra} primeiros da ordem aleatória"),
    ]

    etapas = []
    restantes = n_candidatos
    for etapa, descartados, motivo in descartes:
        restantes -= descartados
        etapas.append(EtapaFunil(etapa, restantes, descartados, motivo))
    return etapas


# --- coleta (rede, via cliente) -------------------------------------------------------


def usa_github_actions(cliente: ClienteGitHub, full_name: str) -> bool:
    """Etapa 3: True se `GET /repos/{full_name}/actions/workflows` tem `total_count > 0`.

    Pede `per_page=1`: só o total interessa, então custa 1 chamada por repositório.
    """
    resposta = cliente.get(CAMINHO_WORKFLOWS.format(full_name=full_name), {"per_page": 1})
    return int(corpo_json(resposta)["total_count"]) > 0


class ReleasesColetadas:
    """Coletor da etapa 4 ligado a `coletar_releases` (#7); guarda as releases por repositório.

    Passe a instância como `releases_de` de `executar_funil`. As releases dos repositórios da
    amostra já ficam em memória, então `da_amostra` alimenta `salvar_releases` sem consultar a
    API de novo. Cada repositório é consultado no máximo uma vez.
    """

    def __init__(self, cliente: ClienteGitHub):
        self._cliente = cliente
        self.por_repo: dict[str, list[dict]] = {}

    def __call__(self, repo: dict) -> list[dict]:
        nome = repo["full_name"]
        if nome not in self.por_repo:
            self.por_repo[nome] = coletar_releases(self._cliente, nome)
        return self.por_repo[nome]

    def da_amostra(self, amostra: Iterable[dict]) -> dict[str, list[dict]]:
        """Releases de cada repositório da amostra, na ordem da amostra (KeyError se não coletado)."""
        return {r["full_name"]: self.por_repo[r["full_name"]] for r in amostra}


# --- disco ------------------------------------------------------------------------------


def salvar_funil(etapas: Iterable[EtapaFunil], dir_saida: Path) -> Path:
    """Escreve `funil.csv` (colunas do contrato 5.4) em dir_saida; devolve o caminho."""
    dir_saida = Path(dir_saida)
    dir_saida.mkdir(parents=True, exist_ok=True)
    caminho = dir_saida / ARQUIVO_FUNIL
    with caminho.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_FUNIL)
        escritor.writeheader()
        for etapa in etapas:
            escritor.writerow(asdict(etapa))
    log.info("funil salvo em %s", caminho)
    return caminho
