import csv
import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pipeline.config import Config, Janela
from pipeline.funil import (
    COLUNAS_FUNIL,
    ETAPA_ACESSIVEL,
    ETAPA_ACTIONS,
    ETAPA_AMOSTRA,
    ETAPA_AVALIADOS,
    ETAPA_CADASTRAL,
    ETAPA_CANDIDATOS,
    EtapaFunil,
    ReleasesColetadas,
    contar_releases_validas,
    contar_runs_validos,
    executar_funil,
    motivo_exclusao_cadastral,
    ordem_aleatoria,
    salvar_funil,
    usa_github_actions,
)
from pipeline.github_client import ErroHTTP, Response
from pipeline.releases import salvar_releases

INICIO = datetime(2025, 10, 1, tzinfo=timezone.utc)
FIM = datetime(2026, 10, 1, tzinfo=timezone.utc)  # exclusivo
JANELA = Janela(inicio=INICIO, fim=FIM)
DENTRO = INICIO + timedelta(days=30)

CONFIG = Config(
    janela=JANELA,
    faixas_estrelas=(),
    excluir_forks=True,
    excluir_arquivados=True,
    min_releases=5,
    min_runs=50,
    tamanho_amostra=100,
    semente=42,
    dir_cache=Path("cache"),
    dir_processados=Path("processed"),
    dir_saida=Path("output"),
)


def config(**campos) -> Config:
    return replace(CONFIG, **campos)


def repo(nome: str, fork: bool = False, archived: bool = False, branch: str = "main") -> dict:
    return {
        "full_name": nome, "default_branch": branch, "stars": 1000, "language": "Python",
        "created_at": INICIO - timedelta(days=900), "fork": fork, "archived": archived,
    }


def release(publicada: datetime | None = DENTRO, draft: bool = False, prerelease: bool = False) -> dict:
    return {"tag_name": "v1", "published_at": publicada, "draft": draft, "prerelease": prerelease}


def run(**campos) -> dict:
    base = {
        "id": 1, "workflow_id": 10, "event": "push", "head_branch": "main",
        "conclusion": "success", "created_at": DENTRO,
        "run_started_at": DENTRO, "updated_at": DENTRO,
    }
    return base | campos


@dataclass
class Perfil:
    """O que os coletores devolvem para um repositório."""

    actions: bool = True
    releases: list[dict] = field(default_factory=lambda: [release()] * 5)
    runs: list[dict] = field(default_factory=lambda: [run()] * 50)


class Fontes:
    """Coletores falsos das etapas 3–5; registram quem foi consultado (custo de API)."""

    def __init__(self, perfis: dict[str, Perfil] | None = None, padrao: Perfil | None = None):
        self.perfis = perfis or {}
        self.padrao = padrao or Perfil()
        self.actions: list[str] = []
        self.releases: list[str] = []
        self.runs: list[str] = []

    def _perfil(self, r: dict) -> Perfil:
        return self.perfis.get(r["full_name"], self.padrao)

    def usa_actions(self, r: dict) -> bool:
        self.actions.append(r["full_name"])
        return self._perfil(r).actions

    def releases_de(self, r: dict) -> list[dict]:
        self.releases.append(r["full_name"])
        return self._perfil(r).releases

    def runs_de(self, r: dict) -> list[dict]:
        self.runs.append(r["full_name"])
        return self._perfil(r).runs


def rodar(candidatos, fontes: Fontes, cfg: Config = CONFIG, **kwargs):
    return executar_funil(
        candidatos, cfg, fontes.usa_actions, fontes.releases_de, fontes.runs_de, **kwargs
    )


def por_etapa(resultado) -> dict[str, EtapaFunil]:
    return {e.etapa: e for e in resultado.etapas}


def assert_cadeia_consistente(resultado):
    """Cada etapa parte do que restou da anterior: restantes[i] = restantes[i-1] − descartados[i]."""
    etapas = resultado.etapas
    assert etapas[0].n_descartados == 0
    for anterior, atual in zip(etapas, etapas[1:]):
        assert atual.n_restantes == anterior.n_restantes - atual.n_descartados, atual
    assert etapas[-1].n_restantes == len(resultado.amostra)


def nomes(repos) -> list[str]:
    return [r["full_name"] for r in repos]


# --- etapa 2: fork / arquivado (pura) ------------------------------------------------


@pytest.mark.parametrize(
    "fork, archived, excluir_forks, excluir_arquivados, esperado",
    [
        (False, False, True, True, None),
        (True, False, True, True, "fork"),
        (False, True, True, True, "arquivado"),
        (True, True, True, True, "fork"),  # conta uma vez, pelo primeiro motivo
        (True, False, False, True, None),
        (False, True, True, False, None),
        (True, True, False, False, None),
    ],
)
def test_motivo_exclusao_cadastral(fork, archived, excluir_forks, excluir_arquivados, esperado):
    r = repo("a/b", fork=fork, archived=archived)
    assert motivo_exclusao_cadastral(r, excluir_forks, excluir_arquivados) == esperado


# --- etapas 4 e 5: contagens (puras) ---------------------------------------------------


def test_conta_releases_publicadas_nos_limites_da_janela():
    releases = [
        release(INICIO),                               # entra (início inclusivo)
        release(FIM - timedelta(microseconds=1)),      # entra
        release(FIM),                                  # fora (fim exclusivo)
        release(INICIO - timedelta(microseconds=1)),   # fora
    ]
    assert contar_releases_validas(releases, JANELA) == 2


def test_nao_conta_drafts_nem_prereleases():
    releases = [release(), release(prerelease=True), release(draft=True), release(None, draft=True)]
    assert contar_releases_validas(releases, JANELA) == 1


def test_conta_runs_validos_nos_limites_da_janela():
    runs = [
        run(created_at=INICIO),
        run(created_at=FIM - timedelta(microseconds=1)),
        run(created_at=FIM),
        run(created_at=INICIO - timedelta(microseconds=1)),
    ]
    assert contar_runs_validos(runs, "main", JANELA) == 2


def test_nao_conta_runs_de_outro_evento_branch_ou_conclusao_ignorada():
    runs = [
        run(),
        run(conclusion="failure"),
        run(conclusion="timed_out"),
        run(conclusion="startup_failure"),
        run(event="schedule"),
        run(event="workflow_dispatch"),
        run(head_branch="dev"),
        run(conclusion="cancelled"),
        run(conclusion="skipped"),
        run(conclusion=None),
    ]
    assert contar_runs_validos(runs, "main", JANELA) == 4


def test_runs_usam_o_default_branch_do_repositorio():
    assert contar_runs_validos([run(head_branch="master")], "master", JANELA) == 1
    assert contar_runs_validos([run(head_branch="main")], "master", JANELA) == 0


# --- ordem aleatória ----------------------------------------------------------------------


def test_ordem_aleatoria_e_deterministica_e_independe_da_ordem_de_entrada():
    repos = [repo(f"org/r{k:02d}") for k in range(30)]
    ordem = ordem_aleatoria(repos, 42)

    assert sorted(nomes(ordem)) == sorted(nomes(repos))
    assert nomes(ordem_aleatoria(repos, 42)) == nomes(ordem)
    assert nomes(ordem_aleatoria(list(reversed(repos)), 42)) == nomes(ordem)
    assert nomes(ordem) != nomes(repos)  # embaralhou de fato
    assert nomes(ordem_aleatoria(repos, 7)) != nomes(ordem)


def test_ordem_aleatoria_nao_altera_a_lista_recebida():
    repos = [repo(f"org/r{k}") for k in range(5)]
    copia = list(repos)
    ordem_aleatoria(repos, 42)
    assert repos == copia


# --- funil completo ------------------------------------------------------------------------


def test_etapas_na_ordem_e_colunas_do_contrato():
    resultado = rodar([repo("a/x")], Fontes())
    assert [e.etapa for e in resultado.etapas] == [
        ETAPA_CANDIDATOS,
        ETAPA_CADASTRAL,
        ETAPA_AVALIADOS,
        ETAPA_ACESSIVEL,
        ETAPA_ACTIONS,
        ">= 5 releases publicadas na janela",
        ">= 50 runs válidos na janela",
        ETAPA_AMOSTRA,
    ]
    assert_cadeia_consistente(resultado)


def test_sem_candidatos(caplog):
    fontes = Fontes()
    with caplog.at_level(logging.WARNING, logger="pipeline.funil"):
        resultado = rodar([], fontes)

    assert resultado.amostra == []
    assert all(e.n_restantes == 0 and e.n_descartados == 0 for e in resultado.etapas)
    assert fontes.actions == []
    assert any("0 de 100" in r.getMessage() for r in caplog.records)


def test_forks_e_arquivados_saem_sem_custo_de_api():
    candidatos = [repo("a/ok"), repo("a/fork", fork=True), repo("a/arq", archived=True),
                  repo("a/ambos", fork=True, archived=True)]
    fontes = Fontes()
    resultado = rodar(candidatos, fontes)

    etapa = por_etapa(resultado)[ETAPA_CADASTRAL]
    assert (etapa.n_restantes, etapa.n_descartados) == (1, 3)
    assert "fork: 2" in etapa.motivo and "arquivado: 1" in etapa.motivo
    assert fontes.actions == ["a/ok"]
    assert nomes(resultado.amostra) == ["a/ok"]
    assert_cadeia_consistente(resultado)


def test_filtro_cadastral_desativado_no_config():
    candidatos = [repo("a/fork", fork=True), repo("a/arq", archived=True)]
    resultado = rodar(candidatos, Fontes(), config(excluir_forks=False, excluir_arquivados=False))

    etapa = por_etapa(resultado)[ETAPA_CADASTRAL]
    assert (etapa.n_restantes, etapa.n_descartados) == (2, 0)
    assert "desativado" in etapa.motivo
    assert sorted(nomes(resultado.amostra)) == ["a/arq", "a/fork"]


def test_busca_sem_forks_registra_zero_descartados_e_avisa(caplog):
    """A Search API omite forks sem `fork:true`: a etapa existe, mas descarta 0 forks."""
    with caplog.at_level(logging.INFO, logger="pipeline.funil"):
        resultado = rodar([repo("a/x"), repo("b/y")], Fontes())

    etapa = por_etapa(resultado)[ETAPA_CADASTRAL]
    assert etapa.n_descartados == 0
    assert "fork: 0" in etapa.motivo
    assert any("fork:true" in r.getMessage() for r in caplog.records)


def test_todos_descartados_na_etapa_cadastral():
    fontes = Fontes()
    resultado = rodar([repo(f"a/r{k}", fork=True) for k in range(4)], fontes)

    assert resultado.amostra == []
    assert por_etapa(resultado)[ETAPA_CADASTRAL].n_restantes == 0
    assert fontes.actions == fontes.releases == fontes.runs == []
    assert_cadeia_consistente(resultado)


def test_sem_actions_e_descartado_antes_de_coletar_releases_e_runs():
    fontes = Fontes({"a/sem": Perfil(actions=False)})
    resultado = rodar([repo("a/sem"), repo("a/com")], fontes)

    etapa = por_etapa(resultado)[ETAPA_ACTIONS]
    assert (etapa.n_restantes, etapa.n_descartados) == (1, 1)
    assert "a/sem" not in fontes.releases and "a/sem" not in fontes.runs
    assert nomes(resultado.amostra) == ["a/com"]
    assert_cadeia_consistente(resultado)


def test_todos_sem_actions():
    fontes = Fontes(padrao=Perfil(actions=False))
    resultado = rodar([repo(f"a/r{k}") for k in range(3)], fontes)

    assert resultado.amostra == []
    assert por_etapa(resultado)[ETAPA_ACTIONS].n_descartados == 3
    assert fontes.releases == fontes.runs == []
    assert_cadeia_consistente(resultado)


def test_limite_exato_de_releases():
    fontes = Fontes({
        "a/cinco": Perfil(releases=[release()] * 5),
        "a/quatro": Perfil(releases=[release()] * 4),
    })
    resultado = rodar([repo("a/cinco"), repo("a/quatro")], fontes)

    etapa = por_etapa(resultado)[">= 5 releases publicadas na janela"]
    assert (etapa.n_restantes, etapa.n_descartados) == (1, 1)
    assert nomes(resultado.amostra) == ["a/cinco"]
    assert "a/quatro" not in fontes.runs  # etapa 5 (mais cara) não é coletada
    assert_cadeia_consistente(resultado)


def test_limite_exato_de_runs():
    fontes = Fontes({
        "a/cinquenta": Perfil(runs=[run()] * 50),
        "a/quarenta_e_nove": Perfil(runs=[run()] * 49),
    })
    resultado = rodar([repo("a/cinquenta"), repo("a/quarenta_e_nove")], fontes)

    etapa = por_etapa(resultado)[">= 50 runs válidos na janela"]
    assert (etapa.n_restantes, etapa.n_descartados) == (1, 1)
    assert nomes(resultado.amostra) == ["a/cinquenta"]
    assert_cadeia_consistente(resultado)


def test_limites_vem_do_config():
    fontes = Fontes(padrao=Perfil(releases=[release()] * 2, runs=[run()] * 3))
    resultado = rodar([repo("a/x")], fontes, config(min_releases=2, min_runs=3))

    assert nomes(resultado.amostra) == ["a/x"]
    assert [e.etapa for e in resultado.etapas][5:7] == [
        ">= 2 releases publicadas na janela", ">= 3 runs válidos na janela",
    ]


def test_releases_que_nao_contam_derrubam_o_limite():
    """5 releases, mas uma é pré-release, outra draft e outra fora da janela → 2 válidas."""
    releases = [release(), release(), release(prerelease=True), release(draft=True), release(FIM)]
    resultado = rodar([repo("a/x")], Fontes(padrao=Perfil(releases=releases)))
    assert resultado.amostra == []


def test_releases_no_limite_da_janela():
    no_limite = [release(INICIO)] * 4 + [release(FIM - timedelta(microseconds=1))]
    fora = [release(INICIO)] * 4 + [release(FIM)]
    fontes = Fontes({"a/no_limite": Perfil(releases=no_limite), "a/fora": Perfil(releases=fora)})
    resultado = rodar([repo("a/no_limite"), repo("a/fora")], fontes)
    assert nomes(resultado.amostra) == ["a/no_limite"]


@pytest.mark.parametrize(
    "invalido",
    [
        run(event="schedule"),
        run(event="pull_request"),
        run(head_branch="dev"),
        run(conclusion="cancelled"),
        run(conclusion=None),
        run(created_at=FIM),
        run(created_at=INICIO - timedelta(microseconds=1)),
    ],
)
def test_run_que_nao_conta_derruba_o_limite(invalido):
    resultado = rodar([repo("a/x")], Fontes(padrao=Perfil(runs=[run()] * 49 + [invalido])))
    assert resultado.amostra == []


def test_runs_no_limite_da_janela_contam():
    runs = [run(created_at=INICIO)] * 49 + [run(created_at=FIM - timedelta(microseconds=1))]
    resultado = rodar([repo("a/x")], Fontes(padrao=Perfil(runs=runs)))
    assert nomes(resultado.amostra) == ["a/x"]


def test_runs_comparados_com_o_default_branch_de_cada_repo():
    runs_master = [run(head_branch="master")] * 50
    fontes = Fontes(padrao=Perfil(runs=runs_master))
    resultado = rodar([repo("a/master", branch="master"), repo("a/main", branch="main")], fontes)
    assert nomes(resultado.amostra) == ["a/master"]


def test_menos_elegiveis_que_a_amostra_devolve_o_que_existe(caplog):
    fontes = Fontes({"a/r1": Perfil(actions=False), "a/r2": Perfil(releases=[])})
    candidatos = [repo(f"a/r{k}") for k in range(5)]
    with caplog.at_level(logging.WARNING, logger="pipeline.funil"):
        resultado = rodar(candidatos, fontes, config(tamanho_amostra=10))

    assert sorted(nomes(resultado.amostra)) == ["a/r0", "a/r3", "a/r4"]
    assert resultado.n_avaliados == 5
    assert por_etapa(resultado)[ETAPA_AVALIADOS].n_descartados == 0
    assert any("3 de 10" in r.getMessage() for r in caplog.records)
    assert_cadeia_consistente(resultado)


# --- avaliação sob demanda (lazy) ----------------------------------------------------------


def test_para_de_avaliar_ao_completar_a_amostra():
    candidatos = [repo(f"org/r{k:02d}") for k in range(40)]
    fontes = Fontes()
    resultado = rodar(candidatos, fontes, config(tamanho_amostra=10))

    ordem = nomes(ordem_aleatoria(candidatos, 42))
    assert nomes(resultado.amostra) == ordem[:10]
    assert fontes.actions == ordem[:10]  # nenhuma chamada além do necessário
    assert resultado.n_avaliados == 10

    avaliados = por_etapa(resultado)[ETAPA_AVALIADOS]
    assert (avaliados.n_restantes, avaliados.n_descartados) == (10, 30)
    assert por_etapa(resultado)[ETAPA_AMOSTRA].n_descartados == 0
    assert_cadeia_consistente(resultado)


def test_inelegiveis_avaliados_entram_na_contagem_das_etapas():
    candidatos = [repo(f"org/r{k:02d}") for k in range(40)]
    ordem = nomes(ordem_aleatoria(candidatos, 42))
    # os 3 primeiros da ordem aleatória são inelegíveis, um por etapa
    fontes = Fontes({
        ordem[0]: Perfil(actions=False),
        ordem[1]: Perfil(releases=[release()] * 4),
        ordem[2]: Perfil(runs=[run()] * 49),
    })
    resultado = rodar(candidatos, fontes, config(tamanho_amostra=5))
    etapas = por_etapa(resultado)

    assert nomes(resultado.amostra) == ordem[3:8]
    assert resultado.n_avaliados == 8
    assert etapas[ETAPA_AVALIADOS].n_descartados == 32
    assert etapas[ETAPA_ACTIONS].n_descartados == 1
    assert etapas[">= 5 releases publicadas na janela"].n_descartados == 1
    assert etapas[">= 50 runs válidos na janela"].n_descartados == 1
    assert_cadeia_consistente(resultado)


def test_amostra_e_deterministica_para_a_mesma_semente():
    candidatos = [repo(f"org/r{k:02d}") for k in range(40)]
    a = rodar(candidatos, Fontes(), config(tamanho_amostra=10))
    b = rodar(list(reversed(candidatos)), Fontes(), config(tamanho_amostra=10))
    c = rodar(candidatos, Fontes(), config(tamanho_amostra=10, semente=7))

    assert nomes(a.amostra) == nomes(b.amostra)
    assert nomes(a.amostra) != nomes(c.amostra)


def test_amostra_maior_preserva_a_menor_como_prefixo():
    """Mesma semente: ampliar a amostra (100 → 300 no S02) mantém os já sorteados."""
    candidatos = [repo(f"org/r{k:02d}") for k in range(40)]
    fontes = Fontes({f"org/r{k:02d}": Perfil(actions=False) for k in range(0, 40, 3)})
    pequena = rodar(candidatos, fontes, config(tamanho_amostra=5))
    grande = rodar(candidatos, Fontes(fontes.perfis), config(tamanho_amostra=15))
    assert nomes(grande.amostra)[:5] == nomes(pequena.amostra)


def test_avaliar_todos_gera_o_funil_completo_e_a_mesma_amostra():
    candidatos = [repo(f"org/r{k:02d}") for k in range(40)]
    perfis = {f"org/r{k:02d}": Perfil(actions=False) for k in range(0, 40, 4)}
    sob_demanda = rodar(candidatos, Fontes(perfis), config(tamanho_amostra=10))
    fontes = Fontes(perfis)
    completo = rodar(candidatos, fontes, config(tamanho_amostra=10), avaliar_todos=True)
    etapas = por_etapa(completo)

    assert nomes(completo.amostra) == nomes(sob_demanda.amostra)
    assert completo.n_avaliados == 40 and len(fontes.actions) == 40
    assert etapas[ETAPA_AVALIADOS].n_descartados == 0
    assert etapas[ETAPA_ACTIONS].n_descartados == 10
    assert (etapas[ETAPA_AMOSTRA].n_restantes, etapas[ETAPA_AMOSTRA].n_descartados) == (10, 20)
    assert_cadeia_consistente(completo)


# --- etapa 3: GitHub Actions (rede, via cliente) ----------------------------------------------


@dataclass
class Resposta:
    json: dict
    headers: dict = field(default_factory=dict)


class ClienteWorkflows:
    def __init__(self, total_count: int):
        self.total_count = total_count
        self.chamadas: list[tuple[str, dict | None]] = []

    def get(self, path: str, params: dict | None = None) -> Resposta:
        self.chamadas.append((path, params))
        return Resposta({"total_count": self.total_count, "workflows": []})

    def get_paginated(self, path, params=None, item_key=None):  # pragma: no cover
        raise AssertionError("a etapa 3 só precisa de total_count")


@pytest.mark.parametrize("total, esperado", [(0, False), (1, True), (12, True)])
def test_usa_github_actions_le_total_count(total, esperado):
    cliente = ClienteWorkflows(total)
    assert usa_github_actions(cliente, "dono/repo") is esperado
    path, params = cliente.chamadas[0]
    assert path == "/repos/dono/repo/actions/workflows"
    assert params["per_page"] == 1  # só o total interessa: 1 chamada por repositório


def test_usa_github_actions_aceita_json_como_metodo():
    class RespostaRequests:
        headers: dict = {}

        def json(self):
            return {"total_count": 2, "workflows": []}

    class ClienteRequests(ClienteWorkflows):
        def get(self, path, params=None):
            super().get(path, params)
            return RespostaRequests()

    assert usa_github_actions(ClienteRequests(0), "dono/repo") is True


# --- etapa 4 ligada à coleta de releases (#7) ------------------------------------------------


def release_api(tag: str, publicada: str | None, draft: bool = False, prerelease: bool = False) -> dict:
    """Release como a API devolve (datas ISO 8601 em texto)."""
    return {"tag_name": tag, "published_at": publicada, "draft": draft, "prerelease": prerelease}


class ClienteReleases:
    """Cliente falso de `/repos/{full_name}/releases`; registra os repositórios consultados."""

    def __init__(self, releases_por_repo: dict[str, list[dict]]):
        self.releases_por_repo = releases_por_repo
        self.consultados: list[str] = []

    def get(self, path, params=None):
        raise AssertionError(f"chamada inesperada: {path}")

    def get_paginated(self, path, params=None, item_key=None):
        nome = path.removeprefix("/repos/").removesuffix("/releases")
        self.consultados.append(nome)
        return self.releases_por_repo[nome]


def cinco_releases_na_janela() -> list[dict]:
    return [release_api(f"v{i}", f"2025-11-0{i}T12:00:00Z") for i in range(1, 6)]


def test_releases_coletadas_alimentam_a_etapa_4_com_o_formato_da_api():
    cliente = ClienteReleases({
        "a/ok": cinco_releases_na_janela(),
        # 4 na janela + 1 antes do início, 1 draft e 1 pré-release: não passa
        "a/poucas": [
            release_api("v0", "2025-09-30T23:59:59Z"),
            *cinco_releases_na_janela()[:4],
            release_api("rascunho", None, draft=True),
            release_api("v5-rc", "2025-11-06T00:00:00Z", prerelease=True),
        ],
    })
    fontes = Fontes()
    coletor = ReleasesColetadas(cliente)

    resultado = executar_funil(
        [repo("a/ok"), repo("a/poucas")], CONFIG, fontes.usa_actions, coletor, fontes.runs_de
    )

    assert nomes(resultado.amostra) == ["a/ok"]
    assert por_etapa(resultado)[">= 5 releases publicadas na janela"].n_descartados == 1
    assert fontes.runs == ["a/ok"]


def test_releases_coletadas_consultam_cada_repositorio_uma_vez():
    cliente = ClienteReleases({"a/ok": cinco_releases_na_janela()})
    coletor = ReleasesColetadas(cliente)

    primeira = coletor(repo("a/ok"))
    segunda = coletor(repo("a/ok"))

    assert segunda is primeira
    assert cliente.consultados == ["a/ok"]
    assert primeira[0]["published_at"] == datetime(2025, 11, 1, 12, tzinfo=timezone.utc)


def test_releases_coletadas_da_amostra_seguem_a_ordem_da_amostra(tmp_path):
    cliente = ClienteReleases({
        "a/x": cinco_releases_na_janela(),
        "a/y": cinco_releases_na_janela()[:2],
        "a/z": cinco_releases_na_janela()[:1],
    })
    coletor = ReleasesColetadas(cliente)
    for nome in ("a/x", "a/y", "a/z"):
        coletor(repo(nome))

    por_repo = coletor.da_amostra([repo("a/z"), repo("a/x")])

    assert list(por_repo) == ["a/z", "a/x"]
    assert [len(r) for r in por_repo.values()] == [1, 5]
    caminho = salvar_releases(por_repo, tmp_path)
    with caminho.open(encoding="utf-8", newline="") as f:
        assert [l["full_name"] for l in csv.DictReader(f)] == ["a/z"] + ["a/x"] * 5


def test_releases_coletadas_da_amostra_exige_repositorio_ja_coletado():
    coletor = ReleasesColetadas(ClienteReleases({}))

    with pytest.raises(KeyError, match="a/nunca"):
        coletor.da_amostra([repo("a/nunca")])


# --- disco ------------------------------------------------------------------------------------


def test_salvar_funil_escreve_as_colunas_do_contrato(tmp_path):
    resultado = rodar([repo("a/x"), repo("a/fork", fork=True)], Fontes())
    caminho = salvar_funil(resultado.etapas, tmp_path / "output")

    assert caminho == tmp_path / "output" / "funil.csv"
    with caminho.open(encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert list(linhas[0]) == list(COLUNAS_FUNIL) == ["etapa", "n_restantes", "n_descartados", "motivo"]
    assert [l["etapa"] for l in linhas] == [e.etapa for e in resultado.etapas]
    assert linhas[1]["n_restantes"] == "1" and linhas[1]["n_descartados"] == "1"


def test_salvar_funil_vazio_escreve_so_cabecalho(tmp_path):
    caminho = salvar_funil([], tmp_path)
    assert caminho.read_text(encoding="utf-8").strip() == ",".join(COLUNAS_FUNIL)


# --- erros definitivos da API não derrubam o funil --------------------------------------


class FontesComErro(Fontes):
    """Levanta ErroHTTP(status) na etapa indicada para os repositórios em `com_erro`."""

    def __init__(self, com_erro: dict[str, tuple[str, int]], **kwargs):
        super().__init__(**kwargs)
        self.com_erro = com_erro

    def _talvez_erro(self, r, etapa):
        if self.com_erro.get(r["full_name"], (None,))[0] == etapa:
            status = self.com_erro[r["full_name"]][1]
            raise ErroHTTP(Response({"message": "erro"}, status_code=status), f"GET {etapa}")

    def usa_actions(self, r):
        self._talvez_erro(r, "actions")
        return super().usa_actions(r)

    def releases_de(self, r):
        self._talvez_erro(r, "releases")
        return super().releases_de(r)

    def runs_de(self, r):
        self._talvez_erro(r, "runs")
        return super().runs_de(r)


@pytest.mark.parametrize("etapa, status", [("actions", 404), ("releases", 451), ("runs", 403), ("runs", 409)])
def test_erro_definitivo_da_api_descarta_o_repo_com_motivo(etapa, status, caplog):
    fontes = FontesComErro({"a/quebrado": (etapa, status)})
    with caplog.at_level(logging.WARNING, logger="pipeline.funil"):
        resultado = rodar([repo("a/ok"), repo("a/quebrado")], fontes)

    assert nomes(resultado.amostra) == ["a/ok"]
    linha = por_etapa(resultado)[ETAPA_ACESSIVEL]
    assert linha.n_descartados == 1
    assert f"{status}: 1" in linha.motivo
    assert_cadeia_consistente(resultado)
    assert "a/quebrado" in caplog.text


@pytest.mark.parametrize("status", [401, 500])
def test_erro_nao_definitivo_interrompe_o_funil(status):
    fontes = FontesComErro({"a/x": ("actions", status)})
    with pytest.raises(ErroHTTP):
        rodar([repo("a/x")], fontes)


def test_sem_erros_a_etapa_de_acesso_descarta_zero():
    linha = por_etapa(rodar([repo("a/x")], Fontes()))[ETAPA_ACESSIVEL]
    assert linha.n_descartados == 0
