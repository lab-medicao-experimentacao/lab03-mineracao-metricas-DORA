"""Amostra-ouro (#33): concordância, divergências, desempates e consenso a partir das planilhas."""

import csv
import logging

import pytest

from metricas.concordancia import kappa_fleiss
from pipeline.amostra_ouro import (
    AVALIADORES,
    COLUNAS_ROTULOS_RELEASES,
    COLUNAS_ROTULOS_REPOS,
    COLUNAS_SORTEIO_RELEASES,
    COLUNAS_SORTEIO_REPOS,
    VALORES_ROTULOS_REPOS,
    arquivo_rotulos,
)
from pipeline.consenso import (
    ARQUIVO_CONCORDANCIA,
    ARQUIVO_CONSENSO_RELEASES,
    ARQUIVO_CONSENSO_REPOS,
    ARQUIVO_DESEMPATES,
    ARQUIVO_DIVERGENCIAS,
    COLUNAS_DESEMPATES,
    ErroConsenso,
    _numero,
    gerar_consenso,
    ler_csv,
    main,
)

REPOS = ["org/a", "org/b", "org/c", "org/d"]
RELEASES = [("org/a", "v1"), ("org/a", "v2"), ("org/b", "1.0")]
PADRAO_REPOS = {"tipo_projeto": "biblioteca/framework", "entregas_reais": "sim"}
PADRAO_RELEASES = {"corretiva": "não"}
SAIDAS = (ARQUIVO_CONCORDANCIA, ARQUIVO_DIVERGENCIAS, ARQUIVO_DESEMPATES,
          ARQUIVO_CONSENSO_REPOS, ARQUIVO_CONSENSO_RELEASES)


def _escrever(caminho, colunas, linhas, sep=",", codificacao="utf-8-sig"):
    with caminho.open("w", encoding=codificacao, newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=colunas, delimiter=sep, restval="")
        escritor.writeheader()
        escritor.writerows(linhas)


def _linhas_repos(**rotulos):
    return [{"full_name": n, "url_repo": f"https://github.com/{n}", **PADRAO_REPOS, **rotulos}
            for n in REPOS]


def _linhas_releases(**rotulos):
    return [{"full_name": n, "tag_name": t, **PADRAO_RELEASES, **rotulos} for n, t in RELEASES]


@pytest.fixture
def pasta(tmp_path):
    """Sorteio + 6 planilhas unânimes em tmp_path/output/amostra_ouro (saída do config de teste)."""
    pasta = tmp_path / "output" / "amostra_ouro"
    pasta.mkdir(parents=True)
    _escrever(pasta / "sorteio_repos.csv", COLUNAS_SORTEIO_REPOS,
              [{"full_name": n} for n in REPOS])
    _escrever(pasta / "sorteio_releases.csv", COLUNAS_SORTEIO_RELEASES,
              [{"full_name": n, "tag_name": t} for n, t in RELEASES])
    for avaliador in AVALIADORES:
        _escrever(pasta / arquivo_rotulos(avaliador, "repos"), COLUNAS_ROTULOS_REPOS, _linhas_repos())
        _escrever(pasta / arquivo_rotulos(avaliador, "releases"), COLUNAS_ROTULOS_RELEASES,
                  _linhas_releases())
    return pasta


def _rotular(pasta, avaliador, item, **rotulos):
    """Altera células de rótulo de um item (`"org/x"` ou `("org/x", "tag")`) na planilha."""
    tipo, colunas = (("releases", COLUNAS_ROTULOS_RELEASES) if isinstance(item, tuple)
                     else ("repos", COLUNAS_ROTULOS_REPOS))
    caminho = pasta / arquivo_rotulos(avaliador, tipo)
    linhas = ler_csv(caminho)
    for linha in linhas:
        chave = (linha["full_name"], linha["tag_name"]) if tipo == "releases" else linha["full_name"]
        if chave == item:
            linha.update(rotulos)
    _escrever(caminho, colunas, linhas)


def _ler(pasta, arquivo):
    return ler_csv(pasta / arquivo)


def _por_nome(linhas, campo="full_name"):
    return {linha[campo]: linha for linha in linhas}


def _bytes(pasta):
    return {arquivo: (pasta / arquivo).read_bytes() for arquivo in SAIDAS}


def _tres_vias(pasta, item="org/b"):
    """Caso 1-1-1 em tipo_projeto de `item`."""
    _rotular(pasta, "A", item, tipo_projeto="biblioteca/framework")
    _rotular(pasta, "B", item, tipo_projeto="aplicação/serviço")
    _rotular(pasta, "C", item, tipo_projeto="ferramenta CLI")


def _decidir(pasta, dimensao, full_name, tag, rotulo_final, justificativa="decidido em reunião"):
    linhas = _ler(pasta, ARQUIVO_DESEMPATES)
    for linha in linhas:
        if (linha["dimensao"], linha["full_name"], linha["tag_name"]) == (dimensao, full_name, tag):
            linha.update(rotulo_final=rotulo_final, justificativa=justificativa)
    _escrever(pasta / ARQUIVO_DESEMPATES, COLUNAS_DESEMPATES, linhas)


def _main(escrever_config):
    return main(["--config", str(escrever_config())])


# --- caminho feliz ----------------------------------------------------------------------


def test_unanime_gera_todos_os_arquivos_e_devolve_zero(pasta, escrever_config):
    assert _main(escrever_config) == 0

    repos = _ler(pasta, ARQUIVO_CONSENSO_REPOS)
    assert [r["full_name"] for r in repos] == REPOS
    assert list(repos[0]) == ["full_name", "tipo_projeto", "origem_tipo_projeto",
                              "entregas_reais", "origem_entregas_reais"]
    assert repos[0] == {"full_name": "org/a", "tipo_projeto": "biblioteca/framework",
                        "origem_tipo_projeto": "unanime", "entregas_reais": "sim",
                        "origem_entregas_reais": "unanime"}
    releases = _ler(pasta, ARQUIVO_CONSENSO_RELEASES)
    assert [(r["full_name"], r["tag_name"]) for r in releases] == RELEASES
    assert releases[0] == {"full_name": "org/a", "tag_name": "v1", "corretiva": "não",
                           "origem_corretiva": "unanime"}
    assert _ler(pasta, ARQUIVO_DIVERGENCIAS) == []
    assert _ler(pasta, ARQUIVO_DESEMPATES) == []
    assert (pasta / ARQUIVO_DESEMPATES).read_text(encoding="utf-8-sig").startswith(
        ",".join(COLUNAS_DESEMPATES))


def test_kappa_indefinido_fica_vazio_e_interpretado_como_indefinido(pasta):
    gerar_consenso(pasta)
    concordancia = _ler(pasta, ARQUIVO_CONCORDANCIA)
    assert [c["dimensao"] for c in concordancia] == ["tipo_projeto", "entregas_reais", "corretiva"]
    assert concordancia[0] == {"dimensao": "tipo_projeto", "n_itens": "4", "n_avaliadores": "3",
                               "concordancia_observada": "1.0000", "kappa_fleiss": "",
                               "interpretacao": "indefinido"}
    assert concordancia[2]["n_itens"] == "3"


def test_maioria_2x1_vira_consenso_e_divergencia(pasta):
    _rotular(pasta, "C", "org/a", entregas_reais="não")
    _rotular(pasta, "A", ("org/a", "v2"), corretiva="sim")
    _rotular(pasta, "B", ("org/a", "v2"), corretiva="sim")

    resultado = gerar_consenso(pasta)

    assert resultado.pendentes == 0
    repos = _por_nome(_ler(pasta, ARQUIVO_CONSENSO_REPOS))
    assert (repos["org/a"]["entregas_reais"], repos["org/a"]["origem_entregas_reais"]) == ("sim", "maioria")
    releases = _ler(pasta, ARQUIVO_CONSENSO_RELEASES)
    assert (releases[1]["corretiva"], releases[1]["origem_corretiva"]) == ("sim", "maioria")
    assert _ler(pasta, ARQUIVO_DIVERGENCIAS) == [
        {"dimensao": "entregas_reais", "full_name": "org/a", "tag_name": "",
         "rotulo_A": "sim", "rotulo_B": "sim", "rotulo_C": "não", "tipo": "2x1"},
        {"dimensao": "corretiva", "full_name": "org/a", "tag_name": "v2",
         "rotulo_A": "sim", "rotulo_B": "sim", "rotulo_C": "não", "tipo": "2x1"},
    ]
    assert _ler(pasta, ARQUIVO_DESEMPATES) == []
    entregas = _por_nome(_ler(pasta, ARQUIVO_CONCORDANCIA), "dimensao")["entregas_reais"]
    votos = [("sim", "sim", "não")] + [("sim",) * 3] * 3
    kappa = kappa_fleiss(votos, VALORES_ROTULOS_REPOS["entregas_reais"])
    assert entregas["kappa_fleiss"] == f"{kappa:.4f}"
    assert entregas["concordancia_observada"] == "0.7500"
    assert entregas["interpretacao"] == "pobre"


# --- desempates -------------------------------------------------------------------------


def test_1_1_1_sem_decisao_gera_arquivos_com_pendente_e_devolve_3(pasta, escrever_config, caplog):
    _tres_vias(pasta)
    with caplog.at_level(logging.WARNING):
        assert _main(escrever_config) == 3

    repos = _por_nome(_ler(pasta, ARQUIVO_CONSENSO_REPOS))
    assert (repos["org/b"]["tipo_projeto"], repos["org/b"]["origem_tipo_projeto"]) == ("", "pendente")
    assert _ler(pasta, ARQUIVO_DESEMPATES) == [
        {"dimensao": "tipo_projeto", "full_name": "org/b", "tag_name": "",
         "rotulo_A": "biblioteca/framework", "rotulo_B": "aplicação/serviço",
         "rotulo_C": "ferramenta CLI", "rotulo_final": "", "justificativa": ""},
    ]
    assert _ler(pasta, ARQUIVO_DIVERGENCIAS)[0]["tipo"] == "1-1-1"
    assert "1 caso(s) 1-1-1 sem decisão" in caplog.text
    assert ARQUIVO_DESEMPATES in caplog.text


def test_1_1_1_decidido_em_desempates_vira_reuniao_e_devolve_0(pasta, escrever_config):
    _tres_vias(pasta)
    assert _main(escrever_config) == 3
    _decidir(pasta, "tipo_projeto", "org/b", "", "  Aplicação/Serviço ", "README descreve um serviço")

    assert _main(escrever_config) == 0

    repos = _por_nome(_ler(pasta, ARQUIVO_CONSENSO_REPOS))
    assert (repos["org/b"]["tipo_projeto"], repos["org/b"]["origem_tipo_projeto"]) == \
        ("aplicação/serviço", "reuniao")
    desempate = _ler(pasta, ARQUIVO_DESEMPATES)[0]
    assert (desempate["rotulo_final"], desempate["justificativa"]) == \
        ("aplicação/serviço", "README descreve um serviço")


def test_regerar_preserva_decisoes_e_justificativas(pasta):
    _tres_vias(pasta)
    _tres_vias(pasta, "org/c")
    gerar_consenso(pasta)
    _decidir(pasta, "tipo_projeto", "org/b", "", "outro", "nenhuma categoria serve")
    _decidir(pasta, "tipo_projeto", "org/c", "", "", "falta ver o README")  # só justificativa

    resultado = gerar_consenso(pasta)
    primeira = _bytes(pasta)
    gerar_consenso(pasta)

    assert resultado.pendentes == 1
    assert _bytes(pasta) == primeira
    desempates = _por_nome(_ler(pasta, ARQUIVO_DESEMPATES))
    assert (desempates["org/b"]["rotulo_final"], desempates["org/b"]["justificativa"]) == \
        ("outro", "nenhuma categoria serve")
    assert (desempates["org/c"]["rotulo_final"], desempates["org/c"]["justificativa"]) == \
        ("", "falta ver o README")
    repos = _por_nome(_ler(pasta, ARQUIVO_CONSENSO_REPOS))
    assert repos["org/c"]["origem_tipo_projeto"] == "pendente"


def test_decisao_que_deixou_de_ser_1_1_1_e_mantida_e_nao_aplicada(pasta, caplog):
    _tres_vias(pasta)
    gerar_consenso(pasta)
    _decidir(pasta, "tipo_projeto", "org/b", "", "outro")
    _rotular(pasta, "C", "org/b", tipo_projeto="aplicação/serviço")  # agora 2x1

    with caplog.at_level(logging.WARNING):
        resultado = gerar_consenso(pasta)

    assert resultado.decisoes_nao_aplicadas == 1
    assert resultado.pendentes == 0
    repos = _por_nome(_ler(pasta, ARQUIVO_CONSENSO_REPOS))
    assert (repos["org/b"]["tipo_projeto"], repos["org/b"]["origem_tipo_projeto"]) == \
        ("aplicação/serviço", "maioria")
    desempates = _ler(pasta, ARQUIVO_DESEMPATES)
    assert len(desempates) == 1
    assert desempates[0]["rotulo_final"] == "outro"
    assert desempates[0]["rotulo_C"] == "ferramenta CLI"  # linha mantida como foi decidida
    assert "não é mais 1-1-1 (agora: 2x1)" in caplog.text


def test_decisao_de_item_fora_do_sorteio_e_mantida_com_aviso(pasta, caplog):
    gerar_consenso(pasta)
    _escrever(pasta / ARQUIVO_DESEMPATES, COLUNAS_DESEMPATES, [
        {"dimensao": "corretiva", "full_name": "org/x", "tag_name": "v9",
         "rotulo_final": "SIM", "justificativa": "antigo"},
    ])
    with caplog.at_level(logging.WARNING):
        gerar_consenso(pasta)
    assert _ler(pasta, ARQUIVO_DESEMPATES)[0]["rotulo_final"] == "sim"
    assert "agora: fora do sorteio" in caplog.text


def test_caso_sem_decisao_que_deixou_de_ser_1_1_1_sai_do_arquivo(pasta):
    _tres_vias(pasta)
    gerar_consenso(pasta)
    _rotular(pasta, "C", "org/b", tipo_projeto="biblioteca/framework")
    gerar_consenso(pasta)
    assert _ler(pasta, ARQUIVO_DESEMPATES) == []


def test_rotulo_final_invalido_e_erro_e_nada_e_gravado(pasta, escrever_config, caplog):
    _tres_vias(pasta)
    gerar_consenso(pasta)
    _decidir(pasta, "tipo_projeto", "org/b", "", "talvez")
    antes = _bytes(pasta)

    with pytest.raises(ErroConsenso, match="rotulo_final: valor 'talvez' inválido"):
        gerar_consenso(pasta)
    assert _main(escrever_config) == 1
    assert _bytes(pasta) == antes
    assert "talvez" in caplog.text


def test_desempates_com_dimensao_desconhecida_caso_repetido_ou_sem_colunas(pasta):
    caso = {"dimensao": "tipo_projeto", "full_name": "org/b", "tag_name": "",
            "rotulo_final": "outro", "justificativa": "x"}
    _escrever(pasta / ARQUIVO_DESEMPATES, COLUNAS_DESEMPATES,
              [caso, caso, {**caso, "dimensao": "linguagem"}])
    with pytest.raises(ErroConsenso) as erro:
        gerar_consenso(pasta)
    assert len(erro.value.problemas) == 2
    assert "caso repetido" in str(erro.value)
    assert "dimensão 'linguagem' desconhecida" in str(erro.value)

    _escrever(pasta / ARQUIVO_DESEMPATES, ("dimensao", "full_name"),
              [{"dimensao": "tipo_projeto", "full_name": "org/b"}])
    with pytest.raises(ErroConsenso, match="sem a\\(s\\) coluna\\(s\\) tag_name, rotulo_final"):
        gerar_consenso(pasta)


def test_desempates_vazio_equivale_a_nenhuma_decisao(pasta):
    (pasta / ARQUIVO_DESEMPATES).write_text("", encoding="utf-8")
    assert gerar_consenso(pasta).pendentes == 0


# --- validação das planilhas ------------------------------------------------------------


def test_todos_os_problemas_sao_listados_de_uma_vez_e_nada_e_gravado(pasta):
    (pasta / arquivo_rotulos("B", "releases")).unlink()
    (pasta / arquivo_rotulos("C", "repos")).unlink()
    _rotular(pasta, "A", "org/d", entregas_reais="")
    with pytest.raises(ErroConsenso) as erro:
        gerar_consenso(pasta)
    assert erro.value.problemas == [
        "avaliador A: rotulos_A_repos.csv, item org/d, coluna entregas_reais: rótulo vazio",
        "avaliador C: arquivo rotulos_C_repos.csv ausente",
        "avaliador B: arquivo rotulos_B_releases.csv ausente",
    ]
    assert not any((pasta / arquivo).exists() for arquivo in SAIDAS)


def test_rotulo_invalido_informa_avaliador_arquivo_item_coluna_e_valor(pasta):
    _rotular(pasta, "B", ("org/a", "v2"), corretiva="talvez")
    with pytest.raises(ErroConsenso) as erro:
        gerar_consenso(pasta)
    assert erro.value.problemas == [
        "avaliador B: rotulos_B_releases.csv, item org/a v2, coluna corretiva: "
        "valor 'talvez' inválido (válidos: sim, não)",
    ]


def test_item_faltando_sobrando_e_repetido(pasta):
    caminho = pasta / arquivo_rotulos("A", "repos")
    linhas = [linha for linha in _linhas_repos() if linha["full_name"] != "org/c"]
    linhas += [{**linhas[0], "full_name": "org/zzz"}, linhas[1]]
    _escrever(caminho, COLUNAS_ROTULOS_REPOS, linhas)
    with pytest.raises(ErroConsenso) as erro:
        gerar_consenso(pasta)
    assert erro.value.problemas == [
        "avaliador A: rotulos_A_repos.csv, item org/b repetido",
        "avaliador A: rotulos_A_repos.csv, item org/c faltando",
        "avaliador A: rotulos_A_repos.csv, item org/zzz sobrando (fora do sorteio)",
    ]


def test_planilha_sem_coluna_de_rotulo_e_erro(pasta):
    _escrever(pasta / arquivo_rotulos("C", "releases"), ("full_name", "tag_name"),
              [{"full_name": n, "tag_name": t} for n, t in RELEASES])
    with pytest.raises(ErroConsenso, match="rotulos_C_releases.csv sem a\\(s\\) coluna\\(s\\) corretiva"):
        gerar_consenso(pasta)


def test_normalizacao_aceita_espacos_e_maiusculas_e_grava_o_valor_canonico(pasta):
    _rotular(pasta, "A", "org/a", tipo_projeto=" BIBLIOTECA/Framework ", entregas_reais="  SIM ")
    _rotular(pasta, "B", ("org/b", "1.0"), corretiva="NÃO")
    gerar_consenso(pasta)
    repos = _por_nome(_ler(pasta, ARQUIVO_CONSENSO_REPOS))
    assert (repos["org/a"]["tipo_projeto"], repos["org/a"]["entregas_reais"]) == \
        ("biblioteca/framework", "sim")
    assert repos["org/a"]["origem_entregas_reais"] == "unanime"
    assert _ler(pasta, ARQUIVO_DIVERGENCIAS) == []


def test_normalizacao_nao_inventa_sinonimos(pasta):
    _rotular(pasta, "A", ("org/a", "v1"), corretiva="nao")
    with pytest.raises(ErroConsenso, match="valor 'nao' inválido"):
        gerar_consenso(pasta)


def test_planilha_salva_com_ponto_e_virgula_e_sem_bom_e_aceita(pasta):
    _rotular(pasta, "C", "org/a", entregas_reais="não")
    _escrever(pasta / arquivo_rotulos("A", "repos"), COLUNAS_ROTULOS_REPOS,
              _linhas_repos(observacoes="vírgula, aqui; e ponto e vírgula"), sep=";")
    _escrever(pasta / arquivo_rotulos("B", "releases"), COLUNAS_ROTULOS_RELEASES,
              _linhas_releases(), codificacao="utf-8")
    assert (pasta / arquivo_rotulos("A", "repos")).read_bytes().startswith(b"\xef\xbb\xbf")
    assert not (pasta / arquivo_rotulos("B", "releases")).read_bytes().startswith(b"\xef\xbb\xbf")

    gerar_consenso(pasta)

    repos = _por_nome(_ler(pasta, ARQUIVO_CONSENSO_REPOS))
    assert repos["org/a"]["origem_entregas_reais"] == "maioria"
    assert (pasta / ARQUIVO_CONSENSO_REPOS).read_bytes().startswith(b"\xef\xbb\xbffull_name,")


def test_planilha_fora_de_utf8_e_erro(pasta):
    _escrever(pasta / arquivo_rotulos("A", "releases"), COLUNAS_ROTULOS_RELEASES,
              _linhas_releases(), sep=";", codificacao="cp1252")
    with pytest.raises(ErroConsenso, match="rotulos_A_releases.csv não está em UTF-8"):
        gerar_consenso(pasta)


def test_sorteio_ausente_vazio_repetido_ou_sem_colunas(pasta):
    (pasta / "sorteio_repos.csv").unlink()
    _escrever(pasta / "sorteio_releases.csv", COLUNAS_SORTEIO_RELEASES, [])
    with pytest.raises(ErroConsenso) as erro:
        gerar_consenso(pasta)
    assert "sorteio repos: arquivo sorteio_repos.csv ausente" in erro.value.problemas
    assert "sorteio releases: sorteio_releases.csv sem itens" in erro.value.problemas

    _escrever(pasta / "sorteio_repos.csv", ("nome",), [{"nome": "org/a"}])
    _escrever(pasta / "sorteio_releases.csv", COLUNAS_SORTEIO_RELEASES,
              [{"full_name": n, "tag_name": t} for n, t in RELEASES + RELEASES[:1]])
    with pytest.raises(ErroConsenso) as erro:
        gerar_consenso(pasta)
    assert "sorteio repos: sorteio_repos.csv sem a(s) coluna(s) full_name" in erro.value.problemas
    assert "sorteio releases: sorteio_releases.csv, item org/a v1 repetido" in erro.value.problemas


# --- reprodutibilidade, formatação e CLI ------------------------------------------------


def test_mesma_entrada_gera_arquivos_byte_a_byte_identicos(pasta):
    _tres_vias(pasta)
    _rotular(pasta, "C", "org/a", entregas_reais="incerto")
    gerar_consenso(pasta)
    primeira = _bytes(pasta)
    for arquivo in SAIDAS:
        (pasta / arquivo).unlink()
    gerar_consenso(pasta)
    assert _bytes(pasta) == primeira


def test_numero_tem_4_casas_e_sem_zero_negativo():
    assert _numero(0.123456) == "0.1235"
    assert _numero(-0.25) == "-0.2500"
    assert _numero(-0.00001) == "0.0000"


def test_ler_csv_detecta_separador_e_tolera_bom(tmp_path):
    caminho = tmp_path / "x.csv"
    caminho.write_bytes("﻿a ; b\r\n1;2\r\n3\r\n".encode("utf-8"))
    assert ler_csv(caminho) == [{"a": "1", "b": "2"}, {"a": "3", "b": ""}]
    caminho.write_text("", encoding="utf-8")
    assert ler_csv(caminho) == []


def test_config_invalida_devolve_2(tmp_path, escrever_config):
    assert main(["--config", str(tmp_path / "nao_existe.yaml")]) == 2
    assert main(["--config", str(escrever_config({"saida: ": "pasta: "}))]) == 2


def test_main_sem_planilhas_devolve_1(tmp_path, escrever_config, caplog):
    assert _main(escrever_config) == 1
    assert "sorteio_repos.csv ausente" in caplog.text
