import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from pipeline.metadados import (
    PARAMETROS_CONTRIBUIDORES,
    coletar_contribuidores,
    contar_contribuidores,
    extrair_links,
    ultima_pagina,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "contribuidores.json"

# Cabeçalho real de GET /repos/psf/requests/contributors?per_page=1&anon=true
LINK_REAL = (
    '<https://api.github.com/repositories/1362490/contributors?per_page=1&anon=true&page=2>; rel="next", '
    '<https://api.github.com/repositories/1362490/contributors?per_page=1&anon=true&page=795>; rel="last"'
)


# --- cabeçalho Link (puro) ----------------------------------------------------------


def test_extrair_links_do_cabecalho_real():
    assert extrair_links(LINK_REAL) == {
        "next": "https://api.github.com/repositories/1362490/contributors?per_page=1&anon=true&page=2",
        "last": "https://api.github.com/repositories/1362490/contributors?per_page=1&anon=true&page=795",
    }


def test_ultima_pagina_do_cabecalho_real():
    assert ultima_pagina(LINK_REAL) == 795


def test_ultima_pagina_com_todas_as_rels():
    link = (
        '<https://api.github.com/x?page=1&per_page=1>; rel="first", '
        '<https://api.github.com/x?page=3&per_page=1>; rel="prev", '
        '<https://api.github.com/x?page=5&per_page=1>; rel="next", '
        '<https://api.github.com/x?page=40&per_page=1>; rel="last"'
    )
    assert ultima_pagina(link) == 40


def test_ordem_das_rels_nao_importa():
    link = (
        '<https://api.github.com/x?page=12>; rel="last", '
        '<https://api.github.com/x?page=2>; rel="next"'
    )
    assert ultima_pagina(link) == 12


def test_sem_rel_last_devolve_none():
    """Na última página a API manda só first/prev: não há 'last'."""
    link = (
        '<https://api.github.com/x?page=1>; rel="first", '
        '<https://api.github.com/x?page=2>; rel="prev"'
    )
    assert ultima_pagina(link) is None


@pytest.mark.parametrize("vazio", [None, "", "   "])
def test_cabecalho_ausente_ou_vazio(vazio):
    assert extrair_links(vazio) == {}
    assert ultima_pagina(vazio) is None


def test_page_nao_e_confundido_com_per_page():
    link = '<https://api.github.com/x?per_page=100&anon=true&page=7&q=a%2Cb>; rel="last"'
    assert ultima_pagina(link) == 7


def test_page_antes_de_per_page_na_url():
    link = '<https://api.github.com/x?page=9&per_page=1&anon=true>; rel="last"'
    assert ultima_pagina(link) == 9


def test_url_com_virgula_e_parametros_extras_no_link():
    link = (
        '<https://api.github.com/x?page=2&q=a,b>; rel="next"; title="seguinte", '
        '<https://api.github.com/x?q=a,b&page=31>; type="application/json"; rel="last"'
    )
    assert ultima_pagina(link) == 31


def test_rel_sem_aspas_e_maiusculas():
    link = "<https://api.github.com/x?page=2>; REL=Next, <https://api.github.com/x?page=8>; rel=Last"
    assert ultima_pagina(link) == 8


def test_rel_com_varios_valores():
    link = '<https://api.github.com/x?page=6>; rel="next last"'
    assert extrair_links(link) == {
        "next": "https://api.github.com/x?page=6",
        "last": "https://api.github.com/x?page=6",
    }
    assert ultima_pagina(link) == 6


def test_last_sem_parametro_page_devolve_none():
    assert ultima_pagina('<https://api.github.com/x?per_page=1>; rel="last"') is None


def test_last_com_page_invalido_devolve_none():
    assert ultima_pagina('<https://api.github.com/x?page=abc>; rel="last"') is None
    assert ultima_pagina('<https://api.github.com/x?page=0>; rel="last"') is None


def test_rel_repetida_mantem_a_primeira():
    link = '<https://api.github.com/x?page=3>; rel="last", <https://api.github.com/x?page=99>; rel="last"'
    assert ultima_pagina(link) == 3


# --- contagem de contribuidores (pura) ---------------------------------------------


def respostas_reais() -> dict:
    dados = json.loads(FIXTURE.read_text(encoding="utf-8"))
    dados.pop("_origem")
    return dados


@dataclass
class Resposta:
    json: object
    headers: dict = field(default_factory=dict)


@pytest.mark.parametrize("repo, esperado", [("psf/requests", 795), ("octocat/Hello-World", 3)])
def test_contagem_pela_ultima_pagina_com_respostas_reais(repo, esperado):
    r = respostas_reais()[repo]
    assert contar_contribuidores(r["json"], r["headers"]) == esperado


def test_sem_link_conta_os_itens():
    """Com um único contribuidor a API não manda Link: conta-se o item da resposta."""
    item = respostas_reais()["octocat/Hello-World"]["json"]
    assert contar_contribuidores(item, {}) == 1


@pytest.mark.parametrize("vazio", [[], None, ""])
def test_corpo_vazio_e_zero(vazio):
    assert contar_contribuidores(vazio, {}) == 0


def test_cabecalho_link_em_minusculas():
    """requests usa dicionário case-insensitive; um dict comum pode vir com 'link'."""
    r = respostas_reais()["psf/requests"]
    assert contar_contribuidores(r["json"], {"link": r["headers"]["Link"]}) == 795


def test_link_sem_last_conta_os_itens():
    assert contar_contribuidores([{"type": "User"}], {"Link": '<https://x?page=1>; rel="first"'}) == 1


def test_headers_none_conta_os_itens():
    assert contar_contribuidores([{"type": "User"}], None) == 1


def test_lista_grande_demais_e_desconhecida():
    r = respostas_reais()["torvalds/linux"]
    assert contar_contribuidores(r["json"], r["headers"]) is None


@pytest.mark.parametrize("corpo", [{"message": "Not Found"}, 42, "texto"])
def test_corpo_inesperado_e_desconhecido(corpo):
    assert contar_contribuidores(corpo, {}) is None


# --- coleta de contribuidores (rede, via cliente) -----------------------------------


class ClienteFalso:
    """Contrato 5.1: devolve respostas fixas por caminho e registra as chamadas."""

    def __init__(self, respostas: dict[str, object]):
        self.respostas = respostas
        self.gets: list[tuple[str, dict]] = []

    def get(self, path: str, params: dict | None = None):
        self.gets.append((path, dict(params or {})))
        resposta = self.respostas[path]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    def get_paginated(self, path, params=None, item_key=None):
        raise AssertionError("contribuidores não devem ser paginados")


def cliente_com_fixtures() -> ClienteFalso:
    return ClienteFalso({
        f"/repos/{nome}/contributors": Resposta(r["json"], r["headers"])
        for nome, r in respostas_reais().items()
    })


def test_coleta_usa_per_page_1_e_anon():
    cliente = cliente_com_fixtures()
    assert coletar_contribuidores(cliente, "psf/requests") == 795
    assert cliente.gets == [("/repos/psf/requests/contributors", {"per_page": 1, "anon": "true"})]
    assert PARAMETROS_CONTRIBUIDORES == {"per_page": 1, "anon": "true"}


def test_coleta_lista_grande_demais_devolve_none_com_aviso(caplog):
    with caplog.at_level(logging.WARNING, logger="pipeline.metadados"):
        assert coletar_contribuidores(cliente_com_fixtures(), "torvalds/linux") is None
    avisos = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("torvalds/linux" in m and "too large" in m for m in avisos)


def test_coleta_repositorio_vazio_204_com_json_atributo():
    """Repositório vazio: a API responde 204 sem corpo."""
    cliente = ClienteFalso({"/repos/a/vazio/contributors": Resposta(None, {})})
    assert coletar_contribuidores(cliente, "a/vazio") == 0


class RespostaRequests:
    """Imita requests.Response: .json() é método e falha com corpo vazio."""

    def __init__(self, status_code: int, corpo: str, headers: dict | None = None):
        self.status_code = status_code
        self.text = corpo
        self.content = corpo.encode()
        self.headers = headers or {}

    def json(self):
        return json.loads(self.text)  # json.JSONDecodeError é ValueError, como no requests


def test_coleta_204_do_requests_e_zero():
    cliente = ClienteFalso({"/repos/a/vazio/contributors": RespostaRequests(204, "")})
    assert coletar_contribuidores(cliente, "a/vazio") == 0


def test_coleta_corpo_vazio_sem_status_e_zero():
    resposta = RespostaRequests(200, "")
    del resposta.status_code
    cliente = ClienteFalso({"/repos/a/vazio/contributors": resposta})
    assert coletar_contribuidores(cliente, "a/vazio") == 0


def test_coleta_corpo_invalido_propaga_erro():
    cliente = ClienteFalso({"/repos/a/b/contributors": RespostaRequests(200, "<html>")})
    with pytest.raises(ValueError):
        coletar_contribuidores(cliente, "a/b")


def test_coleta_json_invalido_sem_content_propaga_erro():
    class SemContent:
        headers: dict = {}

        def json(self):
            raise ValueError("não é JSON")

    cliente = ClienteFalso({"/repos/a/b/contributors": SemContent()})
    with pytest.raises(ValueError):
        coletar_contribuidores(cliente, "a/b")


def test_coleta_resposta_requests_com_link():
    r = respostas_reais()["psf/requests"]
    resposta = RespostaRequests(200, json.dumps(r["json"]), r["headers"])
    cliente = ClienteFalso({"/repos/psf/requests/contributors": resposta})
    assert coletar_contribuidores(cliente, "psf/requests") == 795


class ErroHTTP(Exception):
    """Imita requests.HTTPError: a mensagem da API fica em .response.text."""

    def __init__(self, resposta):
        super().__init__(f"{resposta.status_code} Client Error: Forbidden")
        self.response = resposta


def test_coleta_lista_grande_demais_levantada_como_excecao_devolve_none(caplog):
    corpo = json.dumps(respostas_reais()["torvalds/linux"]["json"])
    cliente = ClienteFalso({"/repos/torvalds/linux/contributors": ErroHTTP(RespostaRequests(403, corpo))})
    with caplog.at_level(logging.WARNING, logger="pipeline.metadados"):
        assert coletar_contribuidores(cliente, "torvalds/linux") is None
    assert any("torvalds/linux" in r.getMessage() for r in caplog.records)


def test_coleta_lista_grande_demais_na_mensagem_da_excecao_devolve_none():
    erro = RuntimeError("403: The history or contributor list is too large to list contributors")
    cliente = ClienteFalso({"/repos/a/b/contributors": erro})
    assert coletar_contribuidores(cliente, "a/b") is None


def test_coleta_outros_erros_do_cliente_sao_propagados():
    """Rate limit, 5xx, rede: não podem virar 'desconhecido' em silêncio."""
    cliente = ClienteFalso({"/repos/a/b/contributors": ErroHTTP(RespostaRequests(500, "erro"))})
    with pytest.raises(ErroHTTP):
        coletar_contribuidores(cliente, "a/b")


def test_coleta_erro_nao_listavel_vira_none_com_aviso(caplog):
    cliente = ClienteFalso({"/repos/a/sumiu/contributors": Resposta({"message": "Not Found"})})
    with caplog.at_level(logging.WARNING, logger="pipeline.metadados"):
        assert coletar_contribuidores(cliente, "a/sumiu") is None
    assert any("Not Found" in r.getMessage() for r in caplog.records)
