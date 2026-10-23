"""RQ06: resultados conhecidos, empates, ausências, Holm e execução offline."""

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from analises import rq06


@pytest.fixture
def dados():
    return pd.DataFrame({
        'full_name': [f'org/r{i:02}' for i in range(24)],
        'stars': list(range(1000, 1024)), 'contributors': list(range(24)),
        'idade_dias': list(range(24)),
        'tipo_projeto': ['biblioteca/framework'] * 12 + ['ferramenta CLI'] * 12,
        **{m: [i / 24 if m.startswith('cfr_') else i for i in range(24)]
           for m in rq06.METRICAS},
    })


def test_quartis_limites_e_empates():
    valores = pd.Series([1, 1, 2, 2, 3, 3, 4, 4, np.nan])
    grupos, limites = rq06.agrupar_fator(valores, True)
    assert grupos.iloc[:8].tolist() == ['Q1', 'Q1', 'Q2', 'Q2', 'Q3', 'Q3', 'Q4', 'Q4']
    assert pd.isna(grupos.iloc[8])
    assert [l['superior'] for l in limites] == [1.75, 2.5, 3.25, 4]
    assert [l['n'] for l in limites] == [2] * 4
    assert limites[0]['inclui_inferior'] and not limites[1]['inclui_inferior']


def test_cortes_repetidos_e_fator_constante():
    grupos, limites = rq06.agrupar_fator(pd.Series([1] * 6 + [2] * 2), True)
    assert grupos.tolist() == ['G1'] * 6 + ['G2'] * 2
    assert len(limites) == 2
    grupos, limites = rq06.agrupar_fator(pd.Series([3] * 10), True)
    assert grupos.eq('G1').all() and limites[0]['inferior'] == limites[0]['superior'] == 3
    grupos, limites = rq06.agrupar_fator(pd.Series([np.nan]), True)
    assert grupos.isna().all() and limites == []


def test_kruskal_com_resultado_calculavel_no_papel():
    r = rq06.comparar_grupos({'a': list(range(1, 6)), 'b': list(range(6, 11)), 'c': list(range(11, 16))})
    assert r['teste'] == 'kruskal_wallis'
    assert r['n'] == 15
    assert r['estatistica'] == pytest.approx(12.5)
    assert r['p_bruto'] == pytest.approx(np.exp(-12.5 / 2))
    assert r['efeito'] == pytest.approx(12.5 / 14)


def test_mann_whitney_ordem_e_delta():
    r = rq06.comparar_grupos({'b': [6, 7, 8, 9, 10], 'a': [1, 2, 3, 4, 5]})
    assert r['grupos'] == 'a | b'
    assert r['teste'] == 'mann_whitney' and r['estatistica'] == 0
    assert r['efeito'] == -1 and r['efeito_interpretacao'] == 'grande'
    assert r['p_bruto'] == pytest.approx(0.012185780355344813)
    inverso = rq06.comparar_grupos({'a': [6, 7, 8, 9, 10], 'b': [1, 2, 3, 4, 5]})
    assert inverso['efeito'] == 1 and inverso['p_bruto'] == r['p_bruto']
    empatado = rq06.comparar_grupos({'a': [1, 1, 2, 2, 3], 'b': [1, 2, 2, 3, 3]})
    x, y = [1, 1, 2, 2, 3], [1, 2, 2, 3, 3]
    delta = sum((a > b) - (a < b) for a in x for b in y) / 25
    assert empatado['efeito'] == pytest.approx(delta)


@pytest.mark.parametrize('delta,esperado', [(0, 'desprezível'), (.147, 'pequeno'),
                                          (-.33, 'médio'), (.474, 'grande')])
def test_limites_cliff(delta, esperado):
    assert rq06.tamanho_cliff(delta) == esperado


@pytest.mark.parametrize('amostras,situacao', [({}, 'grupos_insuficientes'),
    ({'a': [1] * 5}, 'grupos_insuficientes'),
    ({'a': [1] * 5, 'b': [2] * 4}, 'grupo_menor_que_5'),
    ({'a': [1] * 5, 'b': [1] * 5}, 'variavel_constante')])
def test_testes_inviaveis_sem_resultados_inventados(amostras, situacao):
    r = rq06.comparar_grupos(amostras)
    assert r['situacao'] == situacao
    assert r['p_bruto'] is None and r['efeito'] is None


def test_amostra_infinita_e_recusada():
    with pytest.raises(ValueError, match='finitos'):
        rq06.comparar_grupos({'a': [float('inf')]})


def test_holm_familia_global_preserva_ordem_e_ignora_inviaveis():
    tabela = pd.DataFrame({'p_bruto': [.01, None, .04, .03],
                          'situacao': ['calculado', 'variavel_constante', 'calculado', 'calculado']})
    antes = tabela.copy(deep=True)
    r = rq06.corrigir_holm(tabela)
    assert r.loc[[0, 2, 3], 'p_holm'].tolist() == pytest.approx([.03, .06, .06])
    assert r.loc[[0, 2, 3], 'rejeita_holm'].tolist() == [True, False, False]
    assert pd.isna(r.loc[1, 'rejeita_holm']) and pd.isna(r.loc[1, 'p_holm'])
    assert r['n_testes_familia'].eq(3).all()
    pd.testing.assert_frame_equal(tabela, antes)
    tabela['situacao'] = 'variavel_constante'
    assert rq06.corrigir_holm(tabela)['p_holm'].isna().all()


def test_analise_completa_sem_mutacao_e_descritivas_conhecidas(dados):
    antes = dados.copy(deep=True)
    tabelas = rq06.analisar_dados(dados)
    testes = tabelas['testes']
    assert len(testes) == 24 and testes['n_testes_familia'].eq(24).all()
    assert set(testes['teste']) == {'kruskal_wallis', 'mann_whitney'}
    linha = tabelas['descritivas'].query("fator == 'stars' and metrica == 'frequencia_semana'").iloc[0]
    assert linha['n'] == 6 and linha['mediana'] == 2.5
    assert linha['q1'] == 1.25 and linha['q3'] == 3.75 and linha['iqr'] == 2.5
    assert len(tabelas['agrupamentos']) == 4 * len(dados)
    pd.testing.assert_frame_equal(dados, antes)


def test_ausencias_por_fator_metrica_e_quartis_fixos(dados):
    dados.loc[0, 'tipo_projeto'] = None
    dados.loc[0, 'cfr_entrega'] = None
    dados.loc[1, 'contributors'] = None
    r = rq06.analisar_dados(dados)
    testes = r['testes'].set_index(['fator', 'metrica'])
    assert testes.loc[('stars', 'cfr_entrega'), 'n'] == 23
    assert testes.loc[('stars', 'cfr_ci'), 'n'] == 24
    assert testes.loc[('tipo_projeto', 'cfr_entrega'), 'n_excluidos'] == 1
    assert testes.loc[('contributors', 'cfr_ci'), 'n_excluidos'] == 1
    exclusoes = r['exclusoes'].set_index(['fator', 'metrica', 'full_name'])
    assert exclusoes.loc[('tipo_projeto', 'cfr_entrega', 'org/r00'), 'motivo'] == 'sem_fator;sem_metrica'
    assert r['limites_grupos'].query("fator == 'stars'")['n'].tolist() == [6] * 4


@pytest.mark.parametrize('coluna,valor', [('stars', -1), ('contributors', 2.5),
    ('cfr_ci', 1.1), ('cfr_entrega', 'texto'), ('idade_dias', float('inf')),
    ('lead_time_commit_horas', -1), ('tipo_projeto', 'inventado'), ('full_name', '')])
def test_dominios_invalidos(dados, coluna, valor):
    dados[coluna] = dados[coluna].astype(object)
    dados.loc[0, coluna] = valor
    with pytest.raises(ValueError):
        rq06.validar_dados(dados)


def test_colunas_ausentes_duplicadas_e_identificadores(dados):
    with pytest.raises(ValueError):
        rq06.validar_dados(dados.drop(columns='stars'))
    with pytest.raises(ValueError):
        rq06.validar_dados(pd.concat([dados, dados[['stars']]], axis=1))
    dados.loc[1, 'full_name'] = dados.loc[0, 'full_name']
    with pytest.raises(ValueError):
        rq06.validar_dados(dados)


def test_vazio_e_tipo_inteiramente_ausente(dados):
    r = rq06.analisar_dados(dados.iloc[:0])
    assert len(r['testes']) == 24 and r['testes']['n'].eq(0).all()
    assert r['testes']['p_holm'].isna().all()
    dados['tipo_projeto'] = None
    r = rq06.analisar_dados(dados)
    assert r['testes'].query("fator == 'tipo_projeto'")['situacao'].eq('grupos_insuficientes').all()


def test_execucao_reproduz_arquivos_sem_rede(dados, tmp_path, monkeypatch):
    import requests
    def sem_rede(*a, **kw):
        pytest.fail('A análise não pode acessar a rede')
    monkeypatch.setattr(requests.sessions.Session, 'request', sem_rede)
    entrada = tmp_path / 'dataset.csv'
    dados.to_csv(entrada, index=False, encoding='utf-8-sig')
    bruto = entrada.read_bytes()
    saida = tmp_path / 'saida'
    assert rq06.main(['--entrada', str(entrada), '--saida', str(saida)]) == 0
    fotos = {p.name: p.read_bytes() for p in saida.iterdir()}
    assert len(fotos) == 7
    rq06.executar(entrada, saida)
    assert fotos == {p.name: p.read_bytes() for p in saida.iterdir()}
    assert entrada.read_bytes() == bruto
    manifesto = json.loads((saida / 'manifesto.json').read_text())
    assert manifesto['entrada_sha256'] == hashlib.sha256(bruto).hexdigest()
    assert manifesto['n_testes_familia'] == 24
    assert 'consultar_validacao_da_versao_do_dataset_issue_34' == manifesto['cfr_entrega_validacao']
    assert 'Medianas e IQR' in (saida / 'relatorio.md').read_text()


def test_cli_recusa_erros_antes_de_gravar(dados, tmp_path):
    entrada = tmp_path / 'entrada.csv'
    saida = tmp_path / 'saida'
    assert rq06.main(['--entrada', str(entrada), '--saida', str(saida)]) == 1
    entrada.write_text('stars,stars\n1,2\n')
    assert rq06.main(['--entrada', str(entrada), '--saida', str(saida)]) == 1
    assert not saida.exists()
    entrada = tmp_path / 'testes.csv'
    dados.to_csv(entrada, index=False)
    with pytest.raises(ValueError, match='Entrada'):
        rq06.executar(entrada, tmp_path)
