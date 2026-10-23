"""Avaliação offline com arquivos exclusivamente sintéticos em tmp_path."""

import csv
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from pipeline import validacao_heuristica as modulo
from pipeline.amostra_ouro import (
    AVALIADORES, COLUNAS_ROTULOS_RELEASES, COLUNAS_ROTULOS_REPOS,
    COLUNAS_SORTEIO_RELEASES, COLUNAS_SORTEIO_REPOS, gravar_csv,
)
from pipeline.config import carregar_config
from pipeline.consenso import gerar_consenso
from pipeline.releases import COLUNAS_RELEASES
from pipeline.commits import COLUNAS_COMMITS


def ler(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


@pytest.fixture
def ambiente(escrever_config):
    config = carregar_config(escrever_config())
    pasta = config.dir_saida / "amostra_ouro"
    pasta.mkdir(parents=True)
    repos = [{"full_name": "org/exemplo", "tipo_projeto": "ferramenta CLI", "entregas_reais": "sim"}]
    releases = [{"full_name": "org/exemplo", "tag_name": tag, "corretiva": rotulo}
                for tag, rotulo in [("v1.0.1", "sim"), ("v1.1.0", "não"), ("v1.1.1", "sim")]]
    gravar_csv(pasta / "sorteio_repos.csv", COLUNAS_SORTEIO_REPOS,
               [{k: v for k, v in r.items() if k in COLUNAS_SORTEIO_REPOS} for r in repos])
    gravar_csv(pasta / "sorteio_releases.csv", COLUNAS_SORTEIO_RELEASES,
               [{k: v for k, v in r.items() if k in COLUNAS_SORTEIO_RELEASES} for r in releases])
    for avaliador in AVALIADORES:
        gravar_csv(pasta / f"rotulos_{avaliador}_repos.csv", COLUNAS_ROTULOS_REPOS, repos)
        gravar_csv(pasta / f"rotulos_{avaliador}_releases.csv", COLUNAS_ROTULOS_RELEASES, releases)
    gerar_consenso(pasta)
    config.dir_processados.mkdir(parents=True)
    historico = [
        {"full_name": "org/exemplo", "tag_name": tag, "published_at": data,
         "draft": False, "prerelease": False}
        for tag, data in [("v1.0.0", "2025-09-30T12:00:00Z"),
                          ("v1.0.1", "2025-10-01T12:00:00Z"),
                          ("v1.1.0", "2025-11-01T12:00:00Z"),
                          ("v1.1.1", "2025-11-02T12:00:00Z")]]
    gravar_csv(config.dir_processados / "releases.csv", COLUNAS_RELEASES, historico)
    gravar_csv(config.dir_processados / "commits.csv", COLUNAS_COMMITS, [
        {"full_name": "org/exemplo", "tag_name": "v1.1.0", "sha": "abc",
         "author_date": "2025-10-31T12:00:00Z", "message": "feat: novo comando\n\nDetalhes"},
    ])
    return config


def avaliar(config, versao="v1", descricao="Versão inicial"):
    return modulo.gerar_avaliacao(config, versao, descricao)


def fotos(pasta):
    return {str(p.relative_to(pasta)): p.read_bytes() for p in pasta.rglob("*") if p.is_file()}


def test_avalia_apenas_sorteadas_e_preserva_antecessora_fora_da_janela(ambiente):
    antes = fotos(ambiente.dir_saida / "amostra_ouro")
    resultado = avaliar(ambiente)
    assert resultado["n_itens"] == 3
    assert resultado["vp"] == 2
    assert resultado["vn"] == 1
    assert resultado["f1"] == 1.0
    assert resultado["situacao"] == "atingiu_meta"
    assert resultado["n_sem_commits"] == 2
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    linhas = ler(pasta / "v1" / "comparacao.csv")
    assert [r["corretiva_prevista"] for r in linhas] == ["sim", "não", "sim"]
    assert len(ler(pasta / "historico.csv")) == 1
    assert json.loads((pasta / "v1" / "resultado.json").read_text()) == resultado
    assert antes == fotos(ambiente.dir_saida / "amostra_ouro")


def test_mesma_versao_e_entrada_sao_idempotentes(ambiente):
    assert avaliar(ambiente) == avaliar(ambiente)
    antes = fotos(ambiente.dir_saida / modulo.PASTA_VALIDACAO)
    avaliar(ambiente)
    assert fotos(ambiente.dir_saida / modulo.PASTA_VALIDACAO) == antes


def test_nova_versao_preserva_resultados_anteriores(ambiente):
    avaliar(ambiente)
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    antes = fotos(pasta / "v1")
    avaliar(ambiente, "v2", "Segundo experimento")
    assert fotos(pasta / "v1") == antes
    assert [r["versao"] for r in ler(pasta / "historico.csv")] == ["v1", "v2"]


@pytest.mark.parametrize("alteracao", ["descricao", "dados", "codigo"])
def test_mesma_versao_nao_sobrescreve_experimento(ambiente, monkeypatch, alteracao):
    avaliar(ambiente)
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    antes = fotos(pasta)
    if alteracao == "dados":
        caminho = ambiente.dir_processados / "commits.csv"
        linhas = ler(caminho)
        linhas[0]["message"] = "fix: novo defeito"
        gravar_csv(caminho, COLUNAS_COMMITS, linhas)
    if alteracao == "codigo":
        monkeypatch.setattr(modulo.sklearn, "__version__", "outra-versao")
    with pytest.raises(modulo.ErroValidacao, match="versão já registrada"):
        avaliar(ambiente, descricao="Mudou" if alteracao == "descricao" else "Versão inicial")
    assert fotos(pasta) == antes


@pytest.mark.parametrize("arquivo", [
    "consenso_repos.csv", "consenso_releases.csv", "rotulos_A_repos.csv",
    "rotulos_B_releases.csv", "rotulos_C_releases.csv", "sorteio_releases.csv",
])
def test_entradas_ausentes_impedem_heuristica_e_gravacao(ambiente, monkeypatch, arquivo):
    (ambiente.dir_saida / "amostra_ouro" / arquivo).unlink()
    def proibida(*args):
        pytest.fail("heurística executada antes de validar as entradas")
    monkeypatch.setattr(modulo.cfr, "release_corretiva", proibida)
    with pytest.raises(modulo.ErroValidacao):
        avaliar(ambiente)
    assert not (ambiente.dir_saida / modulo.PASTA_VALIDACAO).exists()


@pytest.mark.parametrize("arquivo, campo, valor", [
    ("rotulos_B_releases.csv", "corretiva", ""),
    ("rotulos_C_repos.csv", "tipo_projeto", "inválido"),
    ("consenso_releases.csv", "corretiva", "não"),
    ("consenso_releases.csv", "origem_corretiva", "pendente"),
    ("consenso_repos.csv", "tipo_projeto", ""),
])
def test_rotulagem_incompleta_e_consenso_desatualizado_sao_recusados(ambiente, arquivo, campo, valor):
    caminho = ambiente.dir_saida / "amostra_ouro" / arquivo
    linhas = ler(caminho)
    linhas[0][campo] = valor
    gravar_csv(caminho, tuple(linhas[0]), linhas)
    with pytest.raises(modulo.ErroValidacao):
        avaliar(ambiente)
    assert not (ambiente.dir_saida / modulo.PASTA_VALIDACAO).exists()


@pytest.mark.parametrize("alteracao", ["duplicada", "extra", "faltando"])
def test_exige_mesmos_itens_do_sorteio(ambiente, alteracao):
    caminho = ambiente.dir_saida / "amostra_ouro" / "consenso_releases.csv"
    linhas = ler(caminho)
    if alteracao == "faltando":
        linhas.pop()
    else:
        linhas.append({**linhas[0], "tag_name": "extra"} if alteracao == "extra" else linhas[0])
    gravar_csv(caminho, tuple(linhas[0]), linhas)
    with pytest.raises(modulo.ErroValidacao, match="itens diferentes"):
        avaliar(ambiente)


@pytest.mark.parametrize("campo, valor", [
    ("draft", "sim"), ("published_at", "inválida"),
    ("published_at", "2025-09-30T12:00:00"),
])
def test_dados_coletados_invalidos(ambiente, campo, valor):
    caminho = ambiente.dir_processados / "releases.csv"
    linhas = ler(caminho)
    linhas[0][campo] = valor
    gravar_csv(caminho, COLUNAS_RELEASES, linhas)
    with pytest.raises(modulo.ErroValidacao, match="inválido"):
        avaliar(ambiente)


@pytest.mark.parametrize("campo, valor", [
    ("draft", True), ("prerelease", True), ("published_at", ""),
    ("published_at", "2026-10-01T00:00:00Z"),
])
def test_release_rotulada_precisa_ser_deploy_da_janela(ambiente, campo, valor):
    caminho = ambiente.dir_processados / "releases.csv"
    linhas = ler(caminho)
    linhas[1][campo] = valor
    gravar_csv(caminho, COLUNAS_RELEASES, linhas)
    with pytest.raises(modulo.ErroValidacao, match="ausente ou fora da janela"):
        avaliar(ambiente)


def test_sem_commits_ainda_avalia_e_contabiliza_limitacao(ambiente):
    gravar_csv(ambiente.dir_processados / "commits.csv", COLUNAS_COMMITS, [])
    resultado = avaliar(ambiente)
    assert resultado["n_sem_commits"] == 3
    assert resultado["n_itens"] == 3


def test_commits_lidos_em_fluxo_preservam_mensagens_multilinha(ambiente, monkeypatch):
    caminho = ambiente.dir_processados / "commits.csv"
    linhas = ler(caminho)
    linhas[0]["message"] = 'fix: comando, com "aspas"\n\nDetalhes da correção'
    linhas.append({**linhas[0], "full_name": "org/fora-do-sorteio"})
    gravar_csv(caminho, COLUNAS_COMMITS, linhas)
    original = Path.read_text

    def leitura_inteira_proibida(self, *args, **kwargs):
        if self == caminho:
            pytest.fail("commits.csv não deve ser carregado inteiro na memória")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", leitura_inteira_proibida)
    resultado = avaliar(ambiente)
    assert resultado["fp"] == 1
    assert resultado["n_itens"] == 3
    rotulos = modulo._consenso_completo(ambiente.dir_saida / "amostra_ouro")
    _, commits = modulo._entradas(ambiente, rotulos)
    assert set(commits) == {"org/exemplo"}
    assert commits["org/exemplo"]["v1.1.0"][0]["message"] == linhas[0]["message"]


@pytest.mark.parametrize("conteudo", ["a,b\n1\n", "a,b\n1,2,3\n"])
def test_leitura_em_fluxo_recusa_linhas_com_campos_incorretos(tmp_path, conteudo):
    caminho = tmp_path / "commits.csv"
    caminho.write_text(conteudo, encoding="utf-8")
    with pytest.raises(modulo.ErroValidacao, match="quantidade incorreta"):
        list(modulo._linhas_tabela(caminho, ("a", "b")))


def test_releases_coletadas_duplicadas(ambiente):
    caminho = ambiente.dir_processados / "releases.csv"
    linhas = ler(caminho)
    gravar_csv(caminho, COLUNAS_RELEASES, linhas + linhas[:1])
    with pytest.raises(modulo.ErroValidacao, match="tag repetida"):
        avaliar(ambiente)


@pytest.mark.parametrize("versao, descricao", [("../v1", "ok"), ("", "ok"), ("v1", " ")])
def test_identificador_e_descricao_invalidos(ambiente, versao, descricao):
    with pytest.raises(modulo.ErroValidacao, match="informe versão"):
        avaliar(ambiente, versao, descricao)


def test_cli_f1_abaixo_da_meta_registra_e_devolve_tres(ambiente, escrever_config, monkeypatch):
    monkeypatch.setattr(modulo.cfr, "release_corretiva", lambda *args: False)
    assert modulo.main(["--config", str(escrever_config()), "--versao", "v1",
                        "--descricao", "Experimento sintético"]) == 3
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    assert ler(pasta / "historico.csv")[0]["situacao"] == "refinar"


def test_cli_sucesso(ambiente, escrever_config):
    assert modulo.main(["--config", str(escrever_config()), "--versao", "v1",
                        "--descricao", "Experimento sintético"]) == 0


def test_cli_config_invalida(tmp_path):
    assert modulo.main(["--config", str(tmp_path / "ausente.yaml"), "--versao", "v1",
                        "--descricao", "Teste"]) == 2


def test_cli_entrada_ausente(escrever_config):
    assert modulo.main(["--config", str(escrever_config()), "--versao", "v1",
                        "--descricao", "Teste"]) == 1


def test_cli_sem_positivos_nao_declara_validacao_bem_sucedida(ambiente, escrever_config):
    pasta = ambiente.dir_saida / "amostra_ouro"
    for avaliador in AVALIADORES:
        caminho = pasta / f"rotulos_{avaliador}_releases.csv"
        linhas = ler(caminho)
        for linha in linhas:
            linha["corretiva"] = "não"
        gravar_csv(caminho, COLUNAS_ROTULOS_RELEASES, linhas)
    gerar_consenso(pasta)
    assert modulo.main(["--config", str(escrever_config()), "--versao", "v1",
                        "--descricao", "Sem positivos sintéticos"]) == 4
    resultado = ler(ambiente.dir_saida / modulo.PASTA_VALIDACAO / "historico.csv")[0]
    assert resultado["situacao"] == "sem_positivos"


@pytest.mark.parametrize("arquivo", ["releases.csv", "commits.csv"])
def test_csv_ausente_impede_gravacao(ambiente, arquivo):
    (ambiente.dir_processados / arquivo).unlink()
    with pytest.raises(modulo.ErroValidacao, match="não foi possível ler"):
        avaliar(ambiente)
    assert not (ambiente.dir_saida / modulo.PASTA_VALIDACAO).exists()


@pytest.mark.parametrize("conteudo", [
    "full_name,tag_name\norg/exemplo,v1\n",
    "full_name,tag_name,published_at,draft,prerelease\n",
    "full_name,tag_name,published_at,draft,prerelease\norg/exemplo,v1\n",
    "full_name,tag_name,published_at,draft,prerelease\nx,v1,,False,False,extra\n",
])
def test_csv_com_cabecalho_ou_linhas_invalidas(ambiente, conteudo):
    (ambiente.dir_processados / "releases.csv").write_text(conteudo, encoding="utf-8")
    with pytest.raises(modulo.ErroValidacao):
        avaliar(ambiente)


def test_aceita_csv_utf8_com_ponto_e_virgula(ambiente):
    caminho = ambiente.dir_saida / "amostra_ouro" / "consenso_releases.csv"
    linhas = ler(caminho)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=linhas[0].keys(), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
    assert avaliar(ambiente)["n_itens"] == 3


@pytest.mark.parametrize("conteudo", ["não-json", "{}", "42"])
def test_historico_danificado_nao_e_sobrescrito(ambiente, conteudo):
    avaliar(ambiente)
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    caminho = pasta / "v1" / "resultado.json"
    caminho.write_text(conteudo, encoding="utf-8")
    antes = fotos(pasta)
    with pytest.raises(modulo.ErroValidacao, match="histórico inválido"):
        avaliar(ambiente, "v2")
    assert fotos(pasta) == antes


def test_pasta_preexistente_sem_resultado_nao_e_ocupada(ambiente):
    destino = ambiente.dir_saida / modulo.PASTA_VALIDACAO / "v1"
    destino.mkdir(parents=True)
    with pytest.raises(modulo.ErroValidacao, match="sem resultado válido"):
        avaliar(ambiente)
    assert list(destino.iterdir()) == []


def test_historico_pode_ser_reconstruido_sem_duplicar_versoes(ambiente):
    avaliar(ambiente)
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    (pasta / "historico.csv").unlink()
    avaliar(ambiente)
    assert len(ler(pasta / "historico.csv")) == 1


def test_ignora_registros_nao_principais_e_repos_fora_do_sorteio(ambiente):
    caminho = ambiente.dir_processados / "releases.csv"
    linhas = ler(caminho)
    extras = [
        {**linhas[0], "tag_name": "draft", "draft": True, "published_at": ""},
        {**linhas[0], "tag_name": "rc", "prerelease": True},
        {**linhas[0], "tag_name": "futura", "published_at": "2026-10-01T00:00:00Z"},
        {**linhas[0], "full_name": "org/fora"},
    ]
    gravar_csv(caminho, COLUNAS_RELEASES, linhas + extras)
    commits = ambiente.dir_processados / "commits.csv"
    gravar_csv(commits, COLUNAS_COMMITS, ler(commits) + [
        {"full_name": "org/fora", "tag_name": "v1", "message": "fix: outro projeto"}])
    assert avaliar(ambiente)["n_itens"] == 3


def test_consenso_por_maioria_e_aceito(ambiente):
    caminho = ambiente.dir_saida / "amostra_ouro" / "rotulos_A_releases.csv"
    linhas = ler(caminho)
    linhas[0]["corretiva"] = "não"
    gravar_csv(caminho, COLUNAS_ROTULOS_RELEASES, linhas)
    gerar_consenso(caminho.parent)
    assert avaliar(ambiente)["f1"] == 1.0


def test_comparacao_anterior_alterada_nao_e_sobrescrita(ambiente):
    avaliar(ambiente)
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    caminho = pasta / "v1" / "comparacao.csv"
    linhas = ler(caminho)
    linhas[0]["acertou"] = "False"
    gravar_csv(caminho, modulo.COLUNAS_COMPARACAO, linhas)
    antes = fotos(pasta)
    with pytest.raises(modulo.ErroValidacao, match="comparação da versão registrada foi alterada"):
        avaliar(ambiente)
    assert fotos(pasta) == antes


def test_tags_iguais_em_repos_diferentes_nao_misturam_previsoes(ambiente):
    pasta = ambiente.dir_saida / "amostra_ouro"
    for caminho in pasta.glob("*.csv"):
        if not caminho.name.startswith(("sorteio_", "rotulos_")):
            continue
        linhas = ler(caminho)
        novas = [{**linha, "full_name": "org/outro"} for linha in linhas]
        if caminho.name.endswith("_releases.csv") and caminho.name.startswith("rotulos_"):
            novas[1]["corretiva"] = "sim"
        gravar_csv(caminho, tuple(linhas[0]), linhas + novas)
    gerar_consenso(pasta)
    caminho = ambiente.dir_processados / "releases.csv"
    linhas = ler(caminho)
    gravar_csv(caminho, COLUNAS_RELEASES, linhas + [{**r, "full_name": "org/outro"} for r in linhas])
    caminho = ambiente.dir_processados / "commits.csv"
    linhas = ler(caminho)
    gravar_csv(caminho, COLUNAS_COMMITS, linhas + [
        {**linhas[0], "full_name": "org/outro", "message": "fix: crash"}])
    resultado = avaliar(ambiente)
    assert resultado["n_itens"] == 6
    assert resultado["vp"] == 5
    assert resultado["vn"] == 1
    assert resultado["f1"] == 1.0


def test_registra_codigo_exato_e_relatorio_para_o_artigo(ambiente):
    registro = avaliar(ambiente)
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    codigo = json.loads((pasta / "v1" / "codigo.json").read_text())
    assert modulo._hash_json(codigo) == registro["codigo_sha256"]
    assert codigo["cfr"] == Path(modulo.cfr.__file__).read_text()
    relatorio = (pasta / "relatorio.md").read_text()
    assert "| v1 | Versão inicial | 3 | 1.0000 | 1.0000 | 1.0000 | 0.70 | Meta atingida |" in relatorio
    assert "3 releases de 1 repositório" in relatorio
    assert registro["dados_sha256"] in relatorio
    assert "otimistas" in relatorio
    assert "./v1/comparacao.csv" in relatorio


def test_refinamento_preserva_tentativa_abaixo_da_meta_no_relatorio(ambiente, monkeypatch):
    original = modulo.cfr.release_corretiva
    monkeypatch.setattr(modulo.cfr, "release_corretiva", lambda *args: False)
    primeira = avaliar(ambiente, "v1", "Tentativa sintética com erro")
    assert primeira["situacao"] == "refinar"
    monkeypatch.setattr(modulo.cfr, "release_corretiva", original)
    segunda = avaliar(ambiente, "v2", "Segunda tentativa sintética")
    assert segunda["situacao"] == "atingiu_meta"
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    historico = ler(pasta / "historico.csv")
    assert [linha["situacao"] for linha in historico] == ["refinar", "atingiu_meta"]
    relatorio = (pasta / "relatorio.md").read_text()
    assert "Refinamento necessário" in relatorio
    assert "Meta atingida" in relatorio
    assert "**As versões usaram entradas diferentes.**" not in relatorio


def test_relatorio_identifica_mudanca_de_dados(ambiente):
    avaliar(ambiente)
    caminho = ambiente.dir_processados / "commits.csv"
    linhas = ler(caminho)
    linhas[0]["message"] = "feat: outra descrição"
    gravar_csv(caminho, COLUNAS_COMMITS, linhas)
    avaliar(ambiente, "v2", "Dados atualizados")
    relatorio = (ambiente.dir_saida / modulo.PASTA_VALIDACAO / "relatorio.md").read_text()
    assert "**As versões usaram entradas diferentes.**" in relatorio


@pytest.mark.parametrize("conteudo", ["{}", "não-json"])
def test_codigo_historico_alterado_nao_e_sobrescrito(ambiente, conteudo):
    avaliar(ambiente)
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    (pasta / "v1" / "codigo.json").write_text(conteudo, encoding="utf-8")
    antes = fotos(pasta)
    with pytest.raises(modulo.ErroValidacao, match="código da versão registrada"):
        avaliar(ambiente)
    assert fotos(pasta) == antes


def test_descricao_com_quebra_e_barra_nao_quebra_tabela(ambiente):
    avaliar(ambiente, descricao="Tentativa | inicial\ncom detalhes")
    relatorio = (ambiente.dir_saida / modulo.PASTA_VALIDACAO / "relatorio.md").read_text()
    assert r"Tentativa \| inicial com detalhes" in relatorio


def test_comando_completo_em_outro_processo_sem_token(ambiente, escrever_config):
    ambiente_processo = {**os.environ, "GITHUB_TOKEN": ""}
    processo = subprocess.run(
        [sys.executable, "-m", "pipeline.validacao_heuristica", "--config", str(escrever_config()),
         "--versao", "v1", "--descricao", "Execução sintética completa"],
        env=ambiente_processo, capture_output=True, text=True, timeout=30,
    )
    assert processo.returncode == 0, processo.stderr
    pasta = ambiente.dir_saida / modulo.PASTA_VALIDACAO
    assert (pasta / "historico.csv").is_file()
    assert (pasta / "relatorio.md").is_file()
    assert len(ler(pasta / "v1" / "comparacao.csv")) == 3
