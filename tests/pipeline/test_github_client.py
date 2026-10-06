"""GitHubClient com sessão HTTP falsa: sem rede, sem espera real."""

import json
import logging

import pytest
import requests
from requests.structures import CaseInsensitiveDict

from pipeline.github_client import (
    URL_BASE,
    ErroHTTP,
    GitHubClient,
    Response,
    proxima_pagina,
)

TOKEN = "ghp_token_de_teste_nao_vaza"


class RespostaFalsa:
    def __init__(self, status=200, corpo=None, headers=None, bruto=None):
        self.status_code = status
        self.headers = CaseInsensitiveDict(headers or {})
        if bruto is not None:
            self.content = bruto
        else:
            self.content = b"" if corpo is None else json.dumps(corpo).encode()
        self.text = self.content.decode()

    def json(self):
        return json.loads(self.content)


class SessaoFalsa:
    """Devolve as respostas na ordem; uma exceção na fila é levantada."""

    def __init__(self, *respostas):
        self.headers = {}
        self.fila = list(respostas)
        self.chamadas = []

    def get(self, url, params=None, timeout=None):
        self.chamadas.append((url, params))
        proxima = self.fila.pop(0)
        if isinstance(proxima, Exception):
            raise proxima
        return proxima


class Relogio:
    def __init__(self, inicio=1_000_000.0):
        self.agora = inicio
        self.esperas = []

    def dormir(self, segundos):
        self.esperas.append(segundos)
        self.agora += segundos

    def __call__(self):
        return self.agora


def cliente(tmp_path, *respostas, relogio=None, **extra):
    relogio = relogio or Relogio()
    sessao = SessaoFalsa(*respostas)
    c = GitHubClient(TOKEN, tmp_path / "cache", sessao=sessao,
                     dormir=relogio.dormir, agora=relogio, **extra)
    return c, sessao, relogio


def ok(corpo, **headers):
    return RespostaFalsa(200, corpo, headers)


# --- contrato básico -------------------------------------------------------------------


def test_get_devolve_json_e_headers_e_envia_token(tmp_path):
    c, sessao, _ = cliente(tmp_path, ok({"a": 1}, Link='<x>; rel="next"', **{"Set-Cookie": "z"}))

    resposta = c.get("/repos/o/r", {"per_page": 1})

    assert isinstance(resposta, Response)
    assert resposta.json == {"a": 1}
    assert resposta.headers == {"Link": '<x>; rel="next"'}  # só o que a retomada usa
    assert sessao.chamadas == [(f"{URL_BASE}/repos/o/r", {"per_page": "1"})]
    assert sessao.headers["Authorization"] == f"Bearer {TOKEN}"


def test_token_nao_aparece_no_repr_nem_no_cache(tmp_path):
    c, _, _ = cliente(tmp_path, ok({"a": 1}))
    c.get("/repos/o/r")
    assert TOKEN not in repr(c)
    for arquivo in (tmp_path / "cache").rglob("*.json"):
        assert TOKEN not in arquivo.read_text()


def test_token_vazio_e_recusado(tmp_path):
    with pytest.raises(ValueError):
        GitHubClient("  ", tmp_path)


@pytest.mark.parametrize("caminho", ["https://evil.example/x", "//evil.example/x", "repos/o/r"])
def test_caminho_absoluto_ou_sem_barra_e_recusado(tmp_path, caminho):
    c, sessao, _ = cliente(tmp_path)
    with pytest.raises(ValueError):
        c.get(caminho)
    assert sessao.chamadas == []


def test_corpo_vazio_204_vira_none(tmp_path):
    c, _, _ = cliente(tmp_path, RespostaFalsa(204))
    assert c.get("/repos/o/r/contributors").json is None


def test_corpo_de_sucesso_sem_json_e_erro(tmp_path):
    c, _, _ = cliente(tmp_path, RespostaFalsa(200, bruto=b"<html>"))
    with pytest.raises(ValueError):
        c.get("/x")


# --- cache e retomada ----------------------------------------------------------------


def test_segunda_chamada_igual_vem_do_cache(tmp_path):
    c, sessao, _ = cliente(tmp_path, ok([1, 2], Link='<y>; rel="next"'))
    primeira = c.get("/repos/o/r/releases", {"per_page": 100})
    segunda = c.get("/repos/o/r/releases", {"per_page": 100})
    assert segunda == primeira
    assert len(sessao.chamadas) == 1
    assert (c.requisicoes_rede, c.acertos_cache) == (1, 1)


def test_ordem_dos_parametros_nao_muda_a_chave(tmp_path):
    c, sessao, _ = cliente(tmp_path, ok([]))
    c.get("/x", {"a": 1, "b": 2})
    c.get("/x", {"b": 2, "a": 1})
    assert len(sessao.chamadas) == 1


def test_parametros_diferentes_sao_requisicoes_diferentes(tmp_path):
    c, sessao, _ = cliente(tmp_path, ok([]), ok([]))
    c.get("/x", {"page": 1})
    c.get("/x", {"page": 2})
    assert len(sessao.chamadas) == 2


def test_retoma_em_novo_cliente_sem_repetir_chamadas(tmp_path):
    c1, _, _ = cliente(tmp_path, ok({"v": 1}))
    c1.get("/repos/o/r")

    c2, sessao2, _ = cliente(tmp_path)  # fila vazia: qualquer chamada à rede falharia
    assert c2.get("/repos/o/r").json == {"v": 1}
    assert sessao2.chamadas == []


def test_booleano_vai_como_texto_minusculo(tmp_path):
    c, sessao, _ = cliente(tmp_path, ok([]))
    c.get("/x", {"anon": True})
    assert sessao.chamadas[0][1] == {"anon": "true"}


def test_cache_corrompido_e_refeito(tmp_path, caplog):
    c, _, _ = cliente(tmp_path, ok({"v": 1}))
    c.get("/x")
    (arquivo,) = (tmp_path / "cache").rglob("*.json")
    arquivo.write_text("{meio")

    c2, sessao2, _ = cliente(tmp_path, ok({"v": 2}))
    with caplog.at_level(logging.WARNING):
        assert c2.get("/x").json == {"v": 2}
    assert len(sessao2.chamadas) == 1
    assert "cache ilegível" in caplog.text


def test_interrupcao_na_gravacao_nao_deixa_arquivo_parcial(tmp_path, monkeypatch):
    c, _, _ = cliente(tmp_path, ok({"v": 1}))

    def interrompe(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("pipeline.github_client.json.dump", interrompe)
    with pytest.raises(KeyboardInterrupt):
        c.get("/x")
    assert not list((tmp_path / "cache").rglob("*.json"))
    assert not list((tmp_path / "cache").rglob("*.tmp"))


# --- erros -----------------------------------------------------------------------------


def test_404_levanta_erro_com_status_e_fica_em_cache(tmp_path):
    c, sessao, _ = cliente(tmp_path, RespostaFalsa(404, {"message": "Not Found"}))
    with pytest.raises(ErroHTTP) as e1:
        c.get("/repos/o/r/compare/a...b")
    assert e1.value.status_code == 404
    assert e1.value.response.status_code == 404
    assert "Not Found" in str(e1.value)

    with pytest.raises(ErroHTTP) as e2:
        c.get("/repos/o/r/compare/a...b")
    assert e2.value.status_code == 404
    assert len(sessao.chamadas) == 1


def test_403_lista_de_contribuidores_grande_demais_expoe_a_mensagem(tmp_path):
    mensagem = "The history or contributor list is too large to list contributors for this repository via the API."
    c, _, _ = cliente(tmp_path, RespostaFalsa(403, {"message": mensagem}))
    with pytest.raises(ErroHTTP) as e:
        c.get("/repos/torvalds/linux/contributors", {"per_page": 1, "anon": "true"})
    assert "contributor list is too large" in str(e.value)
    assert "contributor list is too large" in e.value.response.text


def test_401_nao_e_guardado_no_cache(tmp_path):
    c, sessao, _ = cliente(tmp_path, RespostaFalsa(401, {"message": "Bad credentials"}),
                           ok({"v": 1}))
    with pytest.raises(ErroHTTP):
        c.get("/x")
    assert c.get("/x").json == {"v": 1}  # tentou de novo na rede
    assert len(sessao.chamadas) == 2


def test_erro_com_corpo_nao_json_guarda_o_texto(tmp_path):
    c, _, _ = cliente(tmp_path, RespostaFalsa(404, bruto=b"<html>nao achei</html>"))
    with pytest.raises(ErroHTTP) as e:
        c.get("/x")
    assert "nao achei" in str(e.value)


# --- backoff exponencial ---------------------------------------------------------------


def test_5xx_repete_com_backoff_1_2_4_e_sucede(tmp_path):
    erro = RespostaFalsa(502, {"message": "Bad Gateway"})
    c, sessao, relogio = cliente(tmp_path, erro, erro, erro, ok({"v": 1}))
    assert c.get("/x").json == {"v": 1}
    assert relogio.esperas == [1.0, 2.0, 4.0]
    assert len(sessao.chamadas) == 4


def test_5xx_esgota_tentativas_e_nao_vai_para_o_cache(tmp_path):
    erro = RespostaFalsa(500, {"message": "boom"})
    c, sessao, relogio = cliente(tmp_path, *[erro] * 5, ok({"v": 1}), max_tentativas=5)
    with pytest.raises(ErroHTTP) as e:
        c.get("/x")
    assert e.value.status_code == 500
    assert relogio.esperas == [1.0, 2.0, 4.0, 8.0]
    assert len(sessao.chamadas) == 5
    assert c.get("/x").json == {"v": 1}  # nada foi guardado: vai à rede de novo


def test_falha_de_rede_tambem_usa_backoff(tmp_path):
    c, _, relogio = cliente(tmp_path, requests.ConnectionError("x"), requests.Timeout("y"),
                            ok({"v": 1}))
    assert c.get("/x").json == {"v": 1}
    assert relogio.esperas == [1.0, 2.0]


def test_falha_de_rede_persistente_propaga(tmp_path):
    c, _, _ = cliente(tmp_path, *[requests.ConnectionError("x")] * 3, max_tentativas=3)
    with pytest.raises(requests.ConnectionError):
        c.get("/x")


# --- rate limit ------------------------------------------------------------------------


def test_cota_zerada_espera_a_renovacao_antes_da_proxima_chamada(tmp_path):
    relogio = Relogio(inicio=1_000.0)
    primeira = ok({"n": 1}, **{"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1060",
                               "X-RateLimit-Resource": "core"})
    c, sessao, _ = cliente(tmp_path, primeira, ok({"n": 2}), relogio=relogio)

    c.get("/a")
    assert relogio.esperas == []  # a primeira chamada não espera
    c.get("/b")

    assert relogio.esperas == [61.0]  # 60 s até o reset + 1 s de folga
    assert len(sessao.chamadas) == 2


def test_cota_restante_nao_faz_esperar(tmp_path):
    c, _, relogio = cliente(tmp_path, ok({}, **{"X-RateLimit-Remaining": "4999",
                                                "X-RateLimit-Reset": "9999999999"}), ok({}))
    c.get("/a")
    c.get("/b")
    assert relogio.esperas == []


def test_cota_e_controlada_por_recurso(tmp_path):
    busca_zerada = ok({"items": []}, **{"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1060",
                                        "X-RateLimit-Resource": "search"})
    c, _, relogio = cliente(tmp_path, busca_zerada, ok({}), ok({"items": []}),
                            relogio=Relogio(1_000.0))
    c.get("/search/repositories", {"q": "a"})
    c.get("/repos/o/r")                        # core: segue sem esperar
    assert relogio.esperas == []
    c.get("/search/repositories", {"q": "b"})  # search: espera a renovação
    assert relogio.esperas == [61.0]


def test_403_de_cota_espera_o_reset_e_repete(tmp_path):
    limite = RespostaFalsa(403, {"message": "API rate limit exceeded"},
                           {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1030"})
    c, sessao, relogio = cliente(tmp_path, limite, ok({"v": 1}), relogio=Relogio(1_000.0))
    assert c.get("/x").json == {"v": 1}
    assert relogio.esperas == [31.0]  # uma espera só, sem repetir em _aguardar_cota
    assert len(sessao.chamadas) == 2


def test_limite_secundario_usa_retry_after(tmp_path):
    limite = RespostaFalsa(429, {"message": "secondary rate limit"}, {"Retry-After": "10"})
    c, _, relogio = cliente(tmp_path, limite, ok({"v": 1}))
    c.get("/x")
    assert relogio.esperas == [11.0]


def test_403_de_limite_sem_cabecalhos_espera_60s(tmp_path):
    limite = RespostaFalsa(403, {"message": "You have exceeded a secondary rate limit."})
    c, _, relogio = cliente(tmp_path, limite, ok({"v": 1}))
    c.get("/x")
    assert relogio.esperas == [60.0]


def test_429_sem_cabecalhos_nem_mensagem_e_limite_e_espera(tmp_path):
    c, sessao, relogio = cliente(tmp_path, RespostaFalsa(429, bruto=b""), ok({"v": 1}))
    assert c.get("/x").json == {"v": 1}
    assert relogio.esperas == [60.0]
    assert len(sessao.chamadas) == 2


def test_403_de_abuse_detection_e_limite_secundario(tmp_path):
    limite = RespostaFalsa(403, {"message": "You have triggered an abuse detection mechanism."})
    c, _, relogio = cliente(tmp_path, limite, ok({"v": 1}))
    assert c.get("/x").json == {"v": 1}
    assert relogio.esperas == [60.0]


def test_limite_secundario_repetido_espera_cada_vez_mais(tmp_path):
    limite = RespostaFalsa(403, {"message": "You have exceeded a secondary rate limit."})
    c, _, relogio = cliente(tmp_path, limite, limite, limite, ok({"v": 1}))
    assert c.get("/x").json == {"v": 1}
    assert relogio.esperas == [60.0, 120.0, 240.0]


def test_403_de_cota_nao_e_guardado_no_cache(tmp_path):
    limite = RespostaFalsa(403, {"message": "API rate limit exceeded"},
                           {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1030"})
    c, _, _ = cliente(tmp_path, limite, ok({"v": 1}), relogio=Relogio(1_000.0))
    c.get("/x")
    (arquivo,) = (tmp_path / "cache").rglob("*.json")
    assert json.loads(arquivo.read_text())["status_code"] == 200


def test_403_de_cota_repetido_desiste_apos_o_limite_de_esperas(tmp_path):
    limite = RespostaFalsa(403, {"message": "API rate limit exceeded"}, {"Retry-After": "1"})
    c, _, relogio = cliente(tmp_path, *[limite] * 6)
    with pytest.raises(ErroHTTP):
        c.get("/x")
    assert len(relogio.esperas) == 5


# --- paginação -------------------------------------------------------------------------


def test_proxima_pagina_le_o_rel_next():
    link = ('<https://api.github.com/x?page=2>; rel="next", '
            '<https://api.github.com/x?page=9>; rel="last"')
    assert proxima_pagina(link) == "https://api.github.com/x?page=2"
    assert proxima_pagina('<https://api.github.com/x?page=1>; rel="prev"') is None
    assert proxima_pagina(None) is None


def test_get_paginated_segue_link_e_junta_listas(tmp_path):
    c, sessao, _ = cliente(
        tmp_path,
        ok([{"i": 1}], Link='<https://api.github.com/repos/o/r/releases?per_page=100&page=2>; rel="next"'),
        ok([{"i": 2}], Link='<https://api.github.com/repos/o/r/releases?per_page=100&page=3>; rel="next"'),
        ok([{"i": 3}]),
    )
    itens = c.get_paginated("/repos/o/r/releases", {"per_page": 100})
    assert itens == [{"i": 1}, {"i": 2}, {"i": 3}]
    assert [p for _, p in sessao.chamadas] == [
        {"per_page": "100"},
        {"per_page": "100", "page": "2"},
        {"per_page": "100", "page": "3"},
    ]


def test_get_paginated_com_item_key(tmp_path):
    c, _, _ = cliente(
        tmp_path,
        ok({"total_count": 3, "items": [{"i": 1}, {"i": 2}]},
           Link='<https://api.github.com/search/repositories?q=a&page=2>; rel="next"'),
        ok({"total_count": 3, "items": [{"i": 3}]}),
    )
    assert c.get_paginated("/search/repositories", {"q": "a"}, item_key="items") == [
        {"i": 1}, {"i": 2}, {"i": 3},
    ]


def test_get_paginated_retoma_do_cache_pagina_a_pagina(tmp_path):
    respostas = [
        ok([{"i": 1}], Link='<https://api.github.com/x?page=2>; rel="next"'),
        ok([{"i": 2}]),
    ]
    c1, _, _ = cliente(tmp_path, *respostas)
    c1.get_paginated("/x")
    c2, sessao2, _ = cliente(tmp_path)
    assert c2.get_paginated("/x") == [{"i": 1}, {"i": 2}]
    assert sessao2.chamadas == []


def test_get_paginated_recusa_link_para_outro_host(tmp_path):
    c, sessao, _ = cliente(
        tmp_path, ok([{"i": 1}], Link='<https://evil.example/x?page=2>; rel="next"'))
    with pytest.raises(ValueError):
        c.get_paginated("/x")
    assert len(sessao.chamadas) == 1  # o token não foi enviado ao outro host


def test_get_paginated_recusa_link_http_sem_tls(tmp_path):
    c, _, _ = cliente(
        tmp_path, ok([], Link='<http://api.github.com/x?page=2>; rel="next"'))
    with pytest.raises(ValueError):
        c.get_paginated("/x")


def test_get_paginated_detecta_laco(tmp_path):
    c, _, _ = cliente(tmp_path, ok([], Link='<https://api.github.com/x>; rel="next"'))
    with pytest.raises(RuntimeError):
        c.get_paginated("/x")


def test_get_paginated_lista_sem_item_key_exige_lista(tmp_path):
    c, _, _ = cliente(tmp_path, ok({"items": []}))
    with pytest.raises(ValueError):
        c.get_paginated("/x")


def test_get_paginated_item_key_ausente_e_erro(tmp_path):
    c, _, _ = cliente(tmp_path, ok({"total_count": 0}))
    with pytest.raises(ValueError):
        c.get_paginated("/x", item_key="items")


def test_get_paginated_corpo_vazio_da_lista_vazia(tmp_path):
    c, _, _ = cliente(tmp_path, RespostaFalsa(204))
    assert c.get_paginated("/x") == []


def test_get_paginated_propaga_erro_http(tmp_path):
    c, _, _ = cliente(tmp_path, RespostaFalsa(404, {"message": "Not Found"}))
    with pytest.raises(ErroHTTP) as e:
        c.get_paginated("/repos/o/r/compare/a...b", item_key="commits")
    assert e.value.status_code == 404
