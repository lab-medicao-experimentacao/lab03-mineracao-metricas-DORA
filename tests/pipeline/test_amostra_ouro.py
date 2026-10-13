"""Amostra-ouro (#29): sorteio e planilhas de rotulagem, com cliente falso (sem rede)."""

import csv
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import pipeline.amostra_ouro as modulo
from pipeline.amostra_ouro import (
    AVALIADORES,
    COLUNAS_ROTULOS_RELEASES,
    COLUNAS_ROTULOS_REPOS,
    ErroAmostraOuro,
    anteriores_por_tag,
    gerar_amostra_ouro,
    linhas_releases_do_repo,
    main,
    planilhas_com_rotulos,
    sortear_releases,
    sortear_repos,
    url_compare,
    url_release,
)
from pipeline.config import AmostraOuro, Janela, carregar_config

JANELA = Janela(
    inicio=datetime(2025, 10, 1, tzinfo=timezone.utc),
    fim=datetime(2026, 10, 1, tzinfo=timezone.utc),
)
DENTRO = datetime(2025, 11, 1, tzinfo=timezone.utc)


def _release(tag, publicada, draft=False, prerelease=False):
    """Registro Release (contrato 5.2)."""
    return {"tag_name": tag, "published_at": publicada, "draft": draft, "prerelease": prerelease}


def _repos(n):
    return pd.DataFrame({
        "full_name": [f"org/r{i:03d}" for i in range(n)],
        "language": ["Python"] * n,
    })


# --- sorteio dos repositórios -----------------------------------------------------------


def test_sorteio_de_repos_e_reproduzivel_e_depende_da_semente():
    repos = _repos(100)
    a = sortear_repos(repos, 60, 42)["full_name"].tolist()
    b = sortear_repos(repos, 60, 42)["full_name"].tolist()
    c = sortear_repos(repos, 60, 7)["full_name"].tolist()
    assert a == b
    assert a != c
    assert len(a) == len(set(a)) == 60


def test_sorteio_de_repos_nao_depende_da_ordem_do_arquivo():
    repos = _repos(100)
    embaralhado = repos.sample(frac=1, random_state=123).reset_index(drop=True)
    assert sortear_repos(embaralhado, 60, 42)["full_name"].tolist() == \
        sortear_repos(repos, 60, 42)["full_name"].tolist()


def test_sorteio_de_repos_usa_pandas_sample_sobre_a_ordem_por_full_name():
    repos = _repos(100)
    esperado = repos.sort_values("full_name").sample(n=60, random_state=42)["full_name"].tolist()
    assert sortear_repos(repos, 60, 42)["full_name"].tolist() == esperado


def test_amostra_menor_que_o_tamanho_pedido_gera_erro():
    with pytest.raises(ErroAmostraOuro, match="59"):
        sortear_repos(_repos(59), 60, 42)


def test_repositorio_duplicado_na_amostra_gera_erro():
    repos = pd.concat([_repos(70), _repos(1)], ignore_index=True)
    with pytest.raises(ErroAmostraOuro, match="duplicad"):
        sortear_repos(repos, 60, 42)


# --- sorteio das releases ---------------------------------------------------------------


def _candidatas(n):
    return [_release(f"v{i}", DENTRO + timedelta(days=i)) for i in range(n)]


def test_sorteio_de_releases_e_reproduzivel_por_repositorio():
    candidatas = _candidatas(30)
    a = sortear_releases(candidatas, 5, 42, "org/a")
    assert a == sortear_releases(list(reversed(candidatas)), 5, 42, "org/a")  # ordem da entrada
    assert a != sortear_releases(candidatas, 5, 7, "org/a")                   # outra semente
    assert a != sortear_releases(candidatas, 5, 42, "org/b")                  # outro repositório
    assert len(a) == 5
    assert [r["published_at"] for r in a] == sorted(r["published_at"] for r in a)


def test_repositorio_com_menos_releases_que_o_pedido_usa_todas_e_avisa(caplog):
    candidatas = _candidatas(3)
    assert sortear_releases(candidatas, 5, 42, "org/poucas") == candidatas
    assert "org/poucas" in caplog.text and "3" in caplog.text


# --- release anterior e URLs ------------------------------------------------------------


def test_anterior_e_a_release_principal_publicada_logo_antes_mesmo_fora_da_janela():
    releases = [
        _release("v0", JANELA.inicio - timedelta(days=30)),           # fora da janela
        _release("rc", JANELA.inicio - timedelta(days=1), prerelease=True),
        _release("rascunho", None, draft=True),
        _release("v1", DENTRO),
        _release("v2", DENTRO + timedelta(days=1)),
    ]
    assert anteriores_por_tag(releases, JANELA) == {"v0": None, "v1": "v0", "v2": "v1"}


def test_anterior_desempata_publicacoes_simultaneas_pela_tag_como_no_lead_time():
    releases = [_release("b", DENTRO), _release("a", DENTRO)]
    assert anteriores_por_tag(releases, JANELA) == {"a": None, "b": "a"}


def test_urls_escapam_caracteres_especiais_da_tag():
    tag = "@scope/pkg@1.0.0 beta#1"
    assert url_release("org/repo", tag) == \
        "https://github.com/org/repo/releases/tag/%40scope%2Fpkg%401.0.0%20beta%231"
    assert url_compare("org/repo", "v1/x", "v2") == "https://github.com/org/repo/compare/v1%2Fx...v2"
    assert url_compare("org/repo", None, "v2") == ""


def test_linhas_do_repo_so_sorteiam_deploys_da_janela():
    principais = [_release(f"v{i}", DENTRO + timedelta(days=i)) for i in range(6)]
    fora = [
        _release("antiga", JANELA.inicio - timedelta(seconds=1)),
        _release("depois", JANELA.fim),
        _release("rc", DENTRO, prerelease=True),
        _release("rascunho", DENTRO, draft=True),
        _release("sem-data", None, draft=True),
    ]
    for semente in range(30):
        linhas = linhas_releases_do_repo("org/repo", principais + fora, JANELA, 5, semente)
        assert len(linhas) == 5
        assert {l["tag_name"] for l in linhas} <= {f"v{i}" for i in range(6)}


def test_linha_de_release_sem_anterior_tem_compare_vazio():
    linhas = linhas_releases_do_repo("org/repo", [_release("v1", DENTRO)], JANELA, 5, 42)
    assert linhas == [{
        "full_name": "org/repo",
        "tag_name": "v1",
        "published_at": "2025-11-01T00:00:00+00:00",
        "url_release": "https://github.com/org/repo/releases/tag/v1",
        "tag_anterior": "",
        "url_compare": "",
    }]


def test_linha_de_release_aponta_compare_para_a_anterior_fora_da_janela():
    releases = [_release("v0", JANELA.inicio - timedelta(days=1)), _release("v1", DENTRO)]
    (linha,) = linhas_releases_do_repo("org/repo", releases, JANELA, 5, 42)
    assert linha["tag_anterior"] == "v0"
    assert linha["url_compare"] == "https://github.com/org/repo/compare/v0...v1"


# --- planilhas e proteção dos rótulos ---------------------------------------------------


def _escrever(caminho, colunas, linhas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(linhas)


def test_planilha_vazia_ou_ausente_nao_tem_rotulos(tmp_path):
    _escrever(tmp_path / "rotulos_A_repos.csv", COLUNAS_ROTULOS_REPOS,
              [{"full_name": "org/a"}])
    assert planilhas_com_rotulos(tmp_path) == []


def test_planilha_com_rotulo_preenchido_e_detectada(tmp_path):
    _escrever(tmp_path / "rotulos_B_releases.csv", COLUNAS_ROTULOS_RELEASES,
              [{"full_name": "org/a", "tag_name": "v1", "corretiva": " sim "}])
    assert planilhas_com_rotulos(tmp_path) == [tmp_path / "rotulos_B_releases.csv"]


def test_observacao_preenchida_tambem_protege_a_planilha(tmp_path):
    _escrever(tmp_path / "rotulos_C_repos.csv", COLUNAS_ROTULOS_REPOS,
              [{"full_name": "org/a", "observacoes": "README confuso"}])
    assert planilhas_com_rotulos(tmp_path) == [tmp_path / "rotulos_C_repos.csv"]


def test_planilha_em_formato_desconhecido_e_tratada_como_preenchida(tmp_path):
    """Ex.: salva pelo Excel com ';' — melhor recusar do que apagar trabalho manual."""
    caminho = tmp_path / "rotulos_A_releases.csv"
    caminho.write_text("full_name;tag_name;corretiva\norg/a;v1;sim\n", encoding="utf-8")
    assert planilhas_com_rotulos(tmp_path) == [caminho]


# --- orquestração com cliente falso -----------------------------------------------------


class ClienteFalso:
    """Responde /repos/{full_name}/releases com releases no formato da API."""

    def __init__(self, releases_por_repo):
        self.releases_por_repo = releases_por_repo
        self.chamadas = []

    def get_paginated(self, path, params=None, item_key=None):
        self.chamadas.append(path)
        nome = path.removeprefix("/repos/").removesuffix("/releases")
        return self.releases_por_repo[nome]


def _item_api(tag, publicada, draft=False, prerelease=False):
    return {"tag_name": tag, "published_at": publicada.isoformat().replace("+00:00", "Z"),
            "draft": draft, "prerelease": prerelease}


def _historico_api(n_janela=8):
    itens = [_item_api("v0.0.0", JANELA.inicio - timedelta(days=10))]
    itens += [_item_api(f"v1.{i}.0", DENTRO + timedelta(days=7 * i)) for i in range(n_janela)]
    itens.append(_item_api("v2.0.0-rc1", DENTRO, prerelease=True))
    itens.append({"tag_name": "rascunho", "published_at": None, "draft": True, "prerelease": False})
    return itens


@pytest.fixture
def ambiente(escrever_config, tmp_path):
    """config de teste (tamanho 4 de 6 repositórios) + repos.csv + cliente falso."""
    config = carregar_config(escrever_config())
    config = replace(config, amostra_ouro=AmostraOuro(tamanho=4, releases_por_repo=5, semente=42))
    nomes = [f"org/r{i}" for i in range(6)]
    config.dir_saida.mkdir(parents=True)
    pd.DataFrame({
        "full_name": nomes, "default_branch": "main", "stars": 1500,
        "language": ["Python", "", "Go", "Rust", "C", "Java"],
    }).to_csv(config.dir_saida / "repos.csv", index=False)
    historicos = {nome: _historico_api() for nome in nomes}
    historicos["org/r1"] = _historico_api(n_janela=3)  # menos que 5 na janela
    return config, ClienteFalso(historicos)


def _ler(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_gerar_grava_sorteio_e_planilhas_dos_tres_avaliadores(ambiente):
    config, cliente = ambiente
    pasta = gerar_amostra_ouro(cliente, config)

    sorteados = _ler(pasta / "sorteio_repos.csv")
    assert len(sorteados) == 4
    nomes = [l["full_name"] for l in sorteados]
    assert sorted(cliente.chamadas) == sorted(f"/repos/{n}/releases" for n in nomes)
    assert sorteados[0]["url_repo"] == f"https://github.com/{nomes[0]}"
    assert sorteados[0]["url_releases"] == f"https://github.com/{nomes[0]}/releases"

    releases = _ler(pasta / "sorteio_releases.csv")
    por_repo = {n: [l for l in releases if l["full_name"] == n] for n in nomes}
    for nome, linhas in por_repo.items():
        assert len(linhas) == (3 if nome == "org/r1" else 5)
        assert all(l["tag_name"].startswith("v1.") for l in linhas)  # só deploys da janela
    assert [l["full_name"] for l in releases] == [n for n in nomes for _ in por_repo[n]]  # ordem do sorteio

    for avaliador in AVALIADORES:
        rot_repos = _ler(pasta / f"rotulos_{avaliador}_repos.csv")
        rot_releases = _ler(pasta / f"rotulos_{avaliador}_releases.csv")
        assert list(rot_repos[0]) == list(COLUNAS_ROTULOS_REPOS)
        assert list(rot_releases[0]) == list(COLUNAS_ROTULOS_RELEASES)
        assert [l["full_name"] for l in rot_repos] == nomes
        assert [(l["full_name"], l["tag_name"]) for l in rot_releases] == \
            [(l["full_name"], l["tag_name"]) for l in releases]
        assert all(l["tipo_projeto"] == l["entregas_reais"] == l["observacoes"] == "" for l in rot_repos)
        assert all(l["corretiva"] == l["observacoes"] == "" for l in rot_releases)
    leiame = (pasta / "LEIAME.md").read_text(encoding="utf-8")
    assert "biblioteca/framework" in leiame and "incerto" in leiame


def test_planilhas_nao_tem_nenhuma_coluna_de_heuristica(ambiente):
    config, cliente = ambiente
    pasta = gerar_amostra_ouro(cliente, config)
    proibidas = ("heuristic", "patch", "semver", "fix", "hotfix", "major", "minor")
    for caminho in pasta.glob("*.csv"):
        cabecalho = next(csv.reader(caminho.open(encoding="utf-8-sig", newline="")))
        assert not [c for c in cabecalho if any(p in c.lower() for p in proibidas)], caminho.name
    assert set(COLUNAS_ROTULOS_RELEASES) == {
        "full_name", "tag_name", "published_at", "url_release", "tag_anterior", "url_compare",
        "corretiva", "observacoes",
    }


def test_gerar_duas_vezes_produz_os_mesmos_arquivos(ambiente):
    config, cliente = ambiente
    pasta = gerar_amostra_ouro(cliente, config)
    antes = {p.name: p.read_bytes() for p in pasta.iterdir()}
    gerar_amostra_ouro(cliente, config)
    assert {p.name: p.read_bytes() for p in pasta.iterdir()} == antes


def test_nao_sobrescreve_rotulos_preenchidos_sem_forcar(ambiente):
    config, cliente = ambiente
    pasta = gerar_amostra_ouro(cliente, config)
    caminho = pasta / "rotulos_B_releases.csv"
    linhas = _ler(caminho)
    linhas[0]["corretiva"] = "sim"
    _escrever(caminho, COLUNAS_ROTULOS_RELEASES, linhas)
    preenchida = caminho.read_bytes()
    cliente.chamadas.clear()

    with pytest.raises(ErroAmostraOuro, match="rotulos_B_releases.csv"):
        gerar_amostra_ouro(cliente, config)
    assert caminho.read_bytes() == preenchida
    assert cliente.chamadas == []  # aborta antes de gastar cota

    gerar_amostra_ouro(cliente, config, forcar=True)
    assert _ler(caminho)[0]["corretiva"] == ""


def test_gerar_sem_repos_csv_gera_erro_claro(ambiente):
    config, cliente = ambiente
    (config.dir_saida / "repos.csv").unlink()
    with pytest.raises(ErroAmostraOuro, match="repos.csv"):
        gerar_amostra_ouro(cliente, config)


def test_gerar_com_amostra_menor_que_o_tamanho_gera_erro(ambiente):
    config, cliente = ambiente
    config = replace(config, amostra_ouro=AmostraOuro(tamanho=60, releases_por_repo=5, semente=42))
    with pytest.raises(ErroAmostraOuro, match="60"):
        gerar_amostra_ouro(cliente, config)


def test_gerar_com_tamanho_padrao_sorteia_60_repos_e_5_releases(escrever_config, tmp_path):
    config = carregar_config(escrever_config())
    nomes = [f"org/r{i:03d}" for i in range(100)]
    config.dir_saida.mkdir(parents=True)
    pd.DataFrame({"full_name": nomes, "language": "Python"}).to_csv(
        config.dir_saida / "repos.csv", index=False)
    cliente = ClienteFalso({nome: _historico_api(n_janela=12) for nome in nomes})

    pasta = gerar_amostra_ouro(cliente, config)

    repos = _ler(pasta / "sorteio_repos.csv")
    releases = _ler(pasta / "sorteio_releases.csv")
    assert len(repos) == 60
    assert pd.Series([l["full_name"] for l in releases]).value_counts().eq(5).all()
    assert len(releases) == 300


# --- ponto de entrada -------------------------------------------------------------------


@pytest.fixture
def pasta_sem_env(tmp_path, monkeypatch):
    """Roda numa pasta vazia: um .env real do repositório nunca é lido."""
    monkeypatch.chdir(tmp_path)


def test_main_falha_sem_token(escrever_config, monkeypatch, pasta_sem_env):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main(["--config", str(escrever_config())]) == 2


def test_main_repassa_forcar_e_usa_o_cliente_com_cache(escrever_config, monkeypatch, pasta_sem_env):
    monkeypatch.setenv("GITHUB_TOKEN", "token-de-teste")
    recebidos = []

    class Cliente:
        def __init__(self, token, cache, **opcoes):
            recebidos.append(("cliente", token, opcoes))

        def cancelar(self):
            recebidos.append("cancelar")

    monkeypatch.setattr(modulo, "GitHubClient", Cliente)
    monkeypatch.setattr(modulo, "gerar_amostra_ouro",
                        lambda cliente, config, forcar=False: recebidos.append(("gerar", forcar)))
    assert main(["--config", str(escrever_config()), "--forcar"]) == 0
    assert recebidos == [("cliente", "token-de-teste", {"max_simultaneas": 4}), ("gerar", True), "cancelar"]


def test_main_devolve_erro_quando_ha_rotulos(escrever_config, monkeypatch, pasta_sem_env, caplog):
    monkeypatch.setenv("GITHUB_TOKEN", "token-de-teste")
    monkeypatch.setattr(modulo, "GitHubClient", lambda token, cache, **opcoes: object())

    def recusa(cliente, config, forcar=False):
        raise ErroAmostraOuro("rotulos_A_repos.csv já tem rótulos")

    monkeypatch.setattr(modulo, "gerar_amostra_ouro", recusa)
    assert main(["--config", str(escrever_config())]) == 1
    assert "rotulos_A_repos.csv" in caplog.text
