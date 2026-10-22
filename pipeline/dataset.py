"""Dataset final por repositório (#35): aplica `metricas/` à amostra e grava o CSV consolidado.

Entrada (tudo offline, sem token nem rede): ``output/repos.csv`` e os CSVs de
``data/processed/`` (``releases``, ``commits``, ``runs``, ``releases_sem_compare`` e
``runs_meses_saturados``) e ``tags``. Se existir ``output/amostra_ouro/consenso_repos.csv`` (#33), o
tipo do projeto e o consenso de entregas reais dos repositórios da amostra-ouro entram nas
colunas ``tipo_projeto`` e ``entregas_reais``; os demais ficam vazios.

Saída: ``output/metricas_repos.csv``, uma linha por repositório de ``repos.csv`` (mesma ordem),
com as colunas de ``COLUNAS_DATASET`` documentadas em ``output/dicionario_dados.md``.

Uso: ``python -m pipeline.dataset --config config.yaml``

O ``commits.csv`` é lido em fluxo, um repositório por vez (o arquivo passa de 1 GB): o
pipeline o grava com as linhas de cada repositório contíguas, e uma repetição é um erro.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from metricas import run_valido
from metricas.cfr import cfr_ci, cfr_entrega
from metricas.classificacao import classificar_repositorio
from metricas.frequencia import deployment_frequency, releases_publicadas
from metricas.lead_time import lead_time_por_commit, lead_time_por_release
from metricas.recuperacao import tempo_recuperacao
from pipeline.config import Config, ErroConfiguracao, Janela, carregar_config
from pipeline.consenso import ARQUIVO_CONSENSO_REPOS, ler_csv

log = logging.getLogger("pipeline.dataset")

ARQUIVO_DATASET = "metricas_repos.csv"
PASTA_AMOSTRA_OURO = "amostra_ouro"
MOTIVO_SEM_ANTERIOR = "sem_anterior"
MOTIVO_COMPARE_404 = "compare_404"
INTERVALO_PROGRESSO = 100  # a cada quantos repositórios logar o progresso
_ULTIMA_DATA = datetime.max.replace(tzinfo=timezone.utc)  # releases sem data vão para o fim

COLUNAS_METADADOS = (
    "full_name", "default_branch", "language", "stars", "contributors", "created_at",
    "idade_dias", "tipo_projeto", "entregas_reais",
)
COLUNAS_METRICAS = (
    # RQ 01 (e variantes de unidade de deploy da RQ 07: release + pré-release e tag)
    "n_releases", "n_prereleases", "frequencia_semana",
    "frequencia_prerelease_semana", "n_tags", "frequencia_tag_semana",
    # RQ 02
    "lead_time_release_horas", "lead_time_commit_horas",
    "n_releases_lead_time", "n_commits_lead_time",
    "n_releases_sem_anterior", "n_releases_compare_404", "n_releases_compare_outros",
    # RQ 03 (a)
    "cfr_ci", "n_runs_validos", "n_runs_sucesso", "n_runs_falha", "n_runs_ignorados",
    "n_meses_runs_saturados",
    # RQ 03 (b)
    "cfr_entrega", "n_releases_avaliadas", "n_releases_falharam", "n_releases_censuradas",
    # RQ 04
    "recuperacao_mediana_horas", "n_episodios_recuperacao", "prop_episodios_censurados",
    # classificação DORA da combinação de referência (frequência, lead time (a), CFR (a), recuperação)
    "classe_frequencia", "classe_lead_time", "classe_cfr", "classe_recuperacao", "classe_geral",
)
COLUNAS_DATASET = (*COLUNAS_METADADOS, *COLUNAS_METRICAS)

CABECALHOS = {
    "repos.csv": ("full_name", "default_branch", "stars", "language", "created_at",
                  "contributors", "idade_dias"),
    "releases.csv": ("full_name", "tag_name", "published_at", "draft", "prerelease"),
    "tags.csv": ("full_name", "tag_name", "commit_sha", "commit_date"),
    "commits.csv": ("full_name", "tag_name", "sha", "author_date", "message"),
    "runs.csv": ("full_name", "id", "workflow_id", "event", "head_branch", "conclusion",
                 "classe", "created_at", "run_started_at", "updated_at"),
    "releases_sem_compare.csv": ("full_name", "tag_name", "motivo"),
    "runs_meses_saturados.csv": ("full_name", "periodo"),
}


class ErroDataset(ValueError):
    """Arquivo de entrada ausente, com cabeçalho inesperado ou inconsistente."""


# --- leitura -------------------------------------------------------------------------


def _data(valor: str) -> datetime:
    data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if data.tzinfo is None:
        raise ValueError(f"data sem fuso horário: {valor!r}")
    return data.astimezone(timezone.utc)


def _booleano(valor: str) -> bool:
    if valor not in ("True", "False"):
        raise ValueError(f"booleano deve ser True ou False, recebido {valor!r}")
    return valor == "True"


def _abrir(caminho: Path):
    """Abre um CSV de entrada e valida o cabeçalho; devolve (arquivo, leitor, índices)."""
    esperado = CABECALHOS[caminho.name]
    try:
        arquivo = caminho.open(encoding="utf-8-sig", newline="")
    except OSError as erro:
        raise ErroDataset(f"não foi possível ler {caminho}: {erro}") from erro
    leitor = csv.reader(arquivo)
    cabecalho = next(leitor, [])
    if not set(esperado) <= set(cabecalho):
        arquivo.close()
        raise ErroDataset(f"{caminho.name}: cabeçalho inválido; esperado: {', '.join(esperado)}")
    return arquivo, leitor, {nome: i for i, nome in enumerate(cabecalho)}


def _linhas(caminho: Path) -> Iterator[dict[str, str]]:
    arquivo, leitor, indices = _abrir(caminho)
    with arquivo:
        for numero, linha in enumerate(leitor, start=2):
            if len(linha) != len(indices):
                raise ErroDataset(f"{caminho.name}, linha {numero}: quantidade incorreta de campos")
            yield {nome: linha[i] for nome, i in indices.items()}


def ler_repos(caminho: Path) -> list[dict[str, str]]:
    repos = list(_linhas(caminho))
    nomes = [r["full_name"] for r in repos]
    if not repos or len(set(nomes)) != len(nomes):
        raise ErroDataset("repos.csv: vazio ou com repositório repetido")
    return repos


def ler_releases(caminho: Path) -> dict[str, list[dict]]:
    """Releases por repositório (contrato Release), ordenadas por (publicação, tag)."""
    por_repo: dict[str, list[dict]] = defaultdict(list)
    for linha in _linhas(caminho):
        try:
            publicada = _data(linha["published_at"]) if linha["published_at"] else None
            por_repo[linha["full_name"]].append({
                "tag_name": linha["tag_name"], "published_at": publicada,
                "draft": _booleano(linha["draft"]), "prerelease": _booleano(linha["prerelease"]),
            })
        except ValueError as erro:
            raise ErroDataset(f"releases.csv: {erro}") from erro
    for lista in por_repo.values():
        lista.sort(key=lambda r: (r["published_at"] or _ULTIMA_DATA, r["tag_name"]))
    return dict(por_repo)


def ler_tags(caminho: Path) -> dict[str, list[datetime]]:
    """Datas de autoria dos commits apontados pelas tags, por repositório (tag sem data é ignorada)."""
    por_repo: dict[str, list[datetime]] = defaultdict(list)
    for linha in _linhas(caminho):
        if not linha["commit_date"]:
            continue
        try:
            por_repo[linha["full_name"]].append(_data(linha["commit_date"]))
        except ValueError as erro:
            raise ErroDataset(f"tags.csv: {erro}") from erro
    return dict(por_repo)


def ler_runs(caminho: Path) -> dict[str, list[dict]]:
    """Runs por repositório (contrato Run), na ordem do arquivo."""
    por_repo: dict[str, list[dict]] = defaultdict(list)
    for linha in _linhas(caminho):
        try:
            criado = _data(linha["created_at"])
            por_repo[linha["full_name"]].append({
                "id": int(linha["id"]), "workflow_id": int(linha["workflow_id"]),
                "event": linha["event"], "head_branch": linha["head_branch"],
                "conclusion": linha["conclusion"] or None, "created_at": criado,
                "run_started_at": _data(linha["run_started_at"]) if linha["run_started_at"] else criado,
                "updated_at": _data(linha["updated_at"]), "classe": linha["classe"],
            })
        except ValueError as erro:
            raise ErroDataset(f"runs.csv: {erro}") from erro
    return dict(por_repo)


def ler_commits_por_repo(caminho: Path) -> Iterator[tuple[str, dict[str, list[dict]]]]:
    """Commits por tag de destino, um repositório por vez (arquivo grande, lido em fluxo)."""
    csv.field_size_limit(sys.maxsize)
    arquivo, leitor, i = _abrir(caminho)
    vistos: set[str] = set()
    atual: str | None = None
    commits: dict[str, list[dict]] = {}
    with arquivo:
        for numero, linha in enumerate(leitor, start=2):
            if len(linha) != len(i):
                raise ErroDataset(f"commits.csv, linha {numero}: quantidade incorreta de campos")
            nome = linha[i["full_name"]]
            if nome != atual:
                if atual is not None:
                    yield atual, commits
                if nome in vistos:
                    raise ErroDataset(f"commits.csv: linhas de {nome} não são contíguas")
                vistos.add(nome)
                atual, commits = nome, {}
            try:
                autoria = _data(linha[i["author_date"]])
            except ValueError as erro:
                raise ErroDataset(f"commits.csv, linha {numero}: {erro}") from erro
            commits.setdefault(linha[i["tag_name"]], []).append(
                {"sha": linha[i["sha"]], "author_date": autoria, "message": linha[i["message"]]})
    if atual is not None:
        yield atual, commits


def ler_sem_compare(caminho: Path) -> dict[str, Counter]:
    """Contagem de releases ignoradas por motivo, por repositório."""
    contagens: dict[str, Counter] = defaultdict(Counter)
    for linha in _linhas(caminho):
        contagens[linha["full_name"]][linha["motivo"]] += 1
    return dict(contagens)


def ler_meses_saturados(caminho: Path) -> Counter:
    return Counter(linha["full_name"] for linha in _linhas(caminho))


def ler_consenso_repos(pasta: Path) -> dict[str, dict[str, str]]:
    """Consenso da amostra-ouro (`consenso_repos.csv`); vazio se o arquivo ainda não existe."""
    caminho = pasta / ARQUIVO_CONSENSO_REPOS
    if not caminho.is_file():
        log.warning("%s não encontrado: tipo_projeto e entregas_reais ficam vazios", caminho)
        return {}
    return {linha["full_name"]: linha for linha in ler_csv(caminho)}


# --- cálculo (puro) -----------------------------------------------------------------


def calcular_repositorio(
    repo: dict, releases: list[dict], commits_por_release: dict[str, list[dict]],
    runs: list[dict], sem_compare: Counter, n_meses_saturados: int, janela: Janela,
    consenso: dict[str, str] | None = None, datas_tags: list[datetime] | None = None,
) -> dict:
    """Linha do dataset de um repositório (todas as variantes obrigatórias; sem rede nem disco).

    `repo` traz os campos de `repos.csv` (texto); `releases` é o histórico completo (a release
    anterior à janela só serve de referência); `runs` traz também os runs ignorados;
    `datas_tags` são as datas dos commits apontados pelas tags (variante de deploy da RQ 07).
    """
    inicio, fim = janela.inicio, janela.fim
    principais = releases_publicadas(releases, inicio, fim)
    pre_releases = [r for r in releases_publicadas(releases, inicio, fim, incluir_prerelease=True)
                    if r["prerelease"]]
    com_commits = [r for r in principais if commits_por_release.get(r["tag_name"])]

    validos = [r for r in runs if run_valido(r, repo["default_branch"], inicio, fim)]
    classes = Counter(r["classe"] for r in validos)
    entrega = cfr_entrega(
        [r for r in releases if r["published_at"] is not None and r["published_at"] >= inicio],
        commits_por_release, fim)
    recuperacao = tempo_recuperacao(validos, fim)

    frequencia = deployment_frequency(releases, inicio, fim)
    tags_na_janela = [d for d in (datas_tags or []) if janela.contem(d)]
    lead_release = lead_time_por_release(commits_por_release, principais)
    lead_commit = lead_time_por_commit(commits_por_release, principais)
    cfr_a = cfr_ci(validos)
    classes_dora = classificar_repositorio(
        frequencia, lead_release, cfr_a, recuperacao["mediana_horas"])
    rotulos = consenso or {}

    return {
        "full_name": repo["full_name"], "default_branch": repo["default_branch"],
        "language": repo["language"], "stars": repo["stars"],
        "contributors": repo["contributors"], "created_at": repo["created_at"],
        "idade_dias": repo["idade_dias"],
        "tipo_projeto": rotulos.get("tipo_projeto", ""),
        "entregas_reais": rotulos.get("entregas_reais", ""),
        "n_releases": len(principais), "n_prereleases": len(pre_releases),
        "frequencia_semana": frequencia,
        "frequencia_prerelease_semana": deployment_frequency(
            releases, inicio, fim, incluir_prerelease=True),
        "n_tags": len(tags_na_janela),
        "frequencia_tag_semana": len(tags_na_janela) / janela.semanas,
        "lead_time_release_horas": lead_release, "lead_time_commit_horas": lead_commit,
        "n_releases_lead_time": len(com_commits),
        "n_commits_lead_time": sum(len(commits_por_release[r["tag_name"]]) for r in com_commits),
        "n_releases_sem_anterior": sem_compare[MOTIVO_SEM_ANTERIOR],
        "n_releases_compare_404": sem_compare[MOTIVO_COMPARE_404],
        "n_releases_compare_outros": sum(
            n for motivo, n in sem_compare.items()
            if motivo not in (MOTIVO_SEM_ANTERIOR, MOTIVO_COMPARE_404)),
        "cfr_ci": cfr_a, "n_runs_validos": len(validos),
        "n_runs_sucesso": classes["sucesso"], "n_runs_falha": classes["falha"],
        "n_runs_ignorados": sum(1 for r in runs if r["classe"] == "ignorado"),
        "n_meses_runs_saturados": n_meses_saturados,
        "cfr_entrega": entrega["cfr"], "n_releases_avaliadas": entrega["n_avaliadas"],
        "n_releases_falharam": entrega["n_falharam"],
        "n_releases_censuradas": entrega["n_censuradas"],
        "recuperacao_mediana_horas": recuperacao["mediana_horas"],
        "n_episodios_recuperacao": recuperacao["n_episodios"],
        "prop_episodios_censurados": recuperacao["prop_censurados"],
        "classe_frequencia": classes_dora["frequencia"],
        "classe_lead_time": classes_dora["lead_time"],
        "classe_cfr": classes_dora["cfr"],
        "classe_recuperacao": classes_dora["recuperacao"],
        "classe_geral": classes_dora["geral"],
    }


# --- disco ------------------------------------------------------------------------------


def gerar_dataset(config: Config) -> Path:
    """Lê as entradas, calcula uma linha por repositório de `repos.csv` e grava o CSV final."""
    processados, saida = config.dir_processados, config.dir_saida
    repos = ler_repos(saida / "repos.csv")
    nomes = {r["full_name"] for r in repos}
    releases = ler_releases(processados / "releases.csv")
    runs = ler_runs(processados / "runs.csv")
    tags = ler_tags(processados / "tags.csv")
    sem_compare = ler_sem_compare(processados / "releases_sem_compare.csv")
    saturados = ler_meses_saturados(processados / "runs_meses_saturados.csv")
    consenso = ler_consenso_repos(saida / PASTA_AMOSTRA_OURO)

    sem_dados = sorted(n for n in nomes if n not in releases or n not in runs)
    if sem_dados:
        raise ErroDataset(
            f"{len(sem_dados)} repositórios de repos.csv sem releases ou runs em data/processed "
            f"(rode a coleta): {', '.join(sem_dados[:5])}")

    linhas: dict[str, dict] = {}
    repo_de = {r["full_name"]: r for r in repos}

    def calcular(nome: str, commits: dict[str, list[dict]]) -> None:
        linhas[nome] = calcular_repositorio(
            repo_de[nome], releases[nome], commits, runs.get(nome, []),
            sem_compare.get(nome, Counter()), saturados.get(nome, 0), config.janela,
            consenso.get(nome), tags.get(nome, []))

    for nome, commits in ler_commits_por_repo(processados / "commits.csv"):
        if nome in nomes:
            calcular(nome, commits)
            if len(linhas) % INTERVALO_PROGRESSO == 0:
                log.info("%d/%d repositórios", len(linhas), len(repos))
    for nome in nomes - linhas.keys():  # repositório sem nenhum commit coletado
        calcular(nome, {})

    saida.mkdir(parents=True, exist_ok=True)
    caminho = saida / ARQUIVO_DATASET
    with caminho.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_DATASET, restval="")
        escritor.writeheader()
        for repo in repos:
            escritor.writerow({k: "" if v is None else v for k, v in linhas[repo["full_name"]].items()})
    log.info("dataset salvo em %s (%d repositórios)", caminho, len(repos))
    return caminho


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pipeline.dataset", description="Dataset final de métricas DORA por repositório")
    parser.add_argument("--config", default="config.yaml", help="caminho do config.yaml")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        gerar_dataset(carregar_config(args.config))
    except (ErroConfiguracao, ErroDataset) as erro:
        log.error("%s", erro)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
