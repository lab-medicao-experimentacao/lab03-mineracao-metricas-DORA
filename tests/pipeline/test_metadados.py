import pytest

from pipeline.metadados import extrair_links, ultima_pagina

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
