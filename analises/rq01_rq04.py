"""RQ 01 a RQ 04 (#48): descritiva, lead time (a) × (b), classificação DORA C1, censura e figuras.

Uso: ``python -m analises.rq01_rq04 --config config.yaml [--dataset CAMINHO]``. Não acessa a rede.

Entrada: ``<caminhos.saida>/dataset_metricas.csv`` (padrão; produzido pela Issue #35), uma linha
por repositório, com as colunas de ``COLUNAS``. Células vazias = ausente; colunas extras são
ignoradas. Unidades: frequência em releases/semana, lead time e recuperação em horas, CFR e
proporção de censurados como fração 0–1.

Saídas em ``<caminhos.saida>/analises/rq01_rq04/`` (CSV com vírgula, UTF-8 com BOM):

- ``descritiva.csv``: n, ausentes, mediana, Q1, Q3, IQR, mínimo e máximo por métrica e variante;
- ``comparacao_lead_time.csv``: pares com as duas variantes, quantos têm (b) < (a), (b) = (a) e
  (b) > (a), e a mediana da razão (b)/(a) entre os pares com (a) > 0;
- ``classificacao_c1.csv``: categoria DORA de cada métrica e a geral (C1 = frequência, lead
  time (a), CFR (a), recuperação);
- ``distribuicao_c1.csv``: contagem e proporção por categoria, por métrica e na geral;
- ``censura_e_cobertura.csv``: totais de releases e episódios censurados (somas só dos
  presentes; repositórios sem contagem à parte), quartis e proporção agregada de episódios
  censurados, e cobertura C1;
- ``resumo.md``: as tabelas acima em Markdown (vírgula decimal, 2 casas; frações também em %);
- ``figuras/*.png``: boxplots das RQ 01 a 04 e barras da classificação geral C1.

As tabelas nunca excluem valores. Nas figuras, a caixa usa a mediana e os quartis de todos os
valores (os da descritiva); em escala log, valores ≤ 0 não viram ponto (a contagem aparece no
título) e caixa com estatística ≤ 0 é desenhada truncada na base do eixo, com aviso no título. Códigos de saída: 0 = ok; 2 = configuração ou dataset inválido.
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import statistics
import sys
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from metricas import classificacao as dora
from metricas.classificacao import CATEGORIAS, classificar_repositorio
from metricas.descritiva import (
    ORDEM_DISTRIBUICAO,
    SEM_CLASSIFICACAO,
    distribuicao_categorias,
    resumo_descritivo,
)
from pipeline.config import ErroConfiguracao, carregar_config

log = logging.getLogger("analises.rq01_rq04")  # não "__main__" ao rodar com -m

# Nome lógico -> coluna do dataset da #35. Para renomear, mude só o valor.
COLUNAS = {
    "full_name": "full_name",
    "frequencia": "frequencia_semana",
    "lead_time_a": "lead_time_a_horas",
    "lead_time_b": "lead_time_b_horas",
    "cfr_a": "cfr_a",
    "cfr_b": "cfr_b",
    "cfr_b_n_avaliadas": "cfr_b_n_avaliadas",
    "cfr_b_n_falharam": "cfr_b_n_falharam",
    "cfr_b_n_censuradas": "cfr_b_n_censuradas",
    "recuperacao": "recuperacao_horas",
    "recuperacao_n_episodios": "recuperacao_n_episodios",
    "recuperacao_prop_censurados": "recuperacao_prop_censurados",
}
FRACOES = ("cfr_a", "cfr_b", "recuperacao_prop_censurados")  # devem estar entre 0 e 1
CONTAGENS = ("cfr_b_n_avaliadas", "cfr_b_n_falharam", "cfr_b_n_censuradas",
             "recuperacao_n_episodios")  # inteiras ≥ 0 (aceitas também como "20.0")
NUMERICAS = tuple(nome for nome in COLUNAS if nome != "full_name")

ARQUIVO_DATASET = "dataset_metricas.csv"
PASTA_SAIDA = Path("analises") / "rq01_rq04"
PASTA_FIGURAS = "figuras"
ARQUIVO_RESUMO = "resumo.md"
CODIFICACAO = "utf-8-sig"
DPI = 150
CASAS_CSV = 6
ORIGEM_DATASET = "o dataset_metricas.csv é produzido pela Issue #35"

UNIDADE_FRACAO = "fração"
# (rq, metrica, variante, unidade, nome lógico da coluna)
LINHAS_DESCRITIVA = (
    ("RQ01", "frequencia", "", "releases/semana", "frequencia"),
    ("RQ02", "lead_time", "a", "horas", "lead_time_a"),
    ("RQ02", "lead_time", "b", "horas", "lead_time_b"),
    ("RQ03", "cfr", "a", UNIDADE_FRACAO, "cfr_a"),
    ("RQ03", "cfr", "b", UNIDADE_FRACAO, "cfr_b"),
    ("RQ04", "recuperacao", "", "horas", "recuperacao"),
)
ESTATISTICAS = ("mediana", "q1", "q3", "iqr", "minimo", "maximo")
COLUNAS_DESCRITIVA = ("rq", "metrica", "variante", "unidade", "n", "n_ausentes", *ESTATISTICAS)
COLUNAS_COMPARACAO = ("n_pares", "n_b_menor", "n_iguais", "n_b_maior", "prop_b_menor", "mediana_razao_b_a")
METRICAS_C1 = ("frequencia", "lead_time", "cfr", "recuperacao")
COLUNAS_CLASSIFICACAO = ("full_name", *METRICAS_C1, "geral", "n_metricas")
COLUNAS_DISTRIBUICAO = ("metrica", "categoria", "n", "proporcao")
COLUNAS_CENSURA = ("indicador", "valor")

# indicador de censura_e_cobertura.csv -> descrição no resumo.md
INDICADORES = {
    "total_repositorios": "Repositórios no dataset",
    "soma_cfr_b_n_avaliadas": "Releases avaliadas no CFR (b)",
    "soma_cfr_b_n_falharam": "Releases que falharam no CFR (b)",
    "soma_cfr_b_n_censuradas": "Releases censuradas no CFR (b)",
    "repos_sem_contagem_cfr_b": "Repositórios sem contagem de releases do CFR (b)",
    "soma_recuperacao_n_episodios": "Episódios de recuperação",
    "repos_sem_contagem_episodios": "Repositórios sem contagem de episódios de recuperação",
    "q1_recuperacao_prop_censurados": "Q1 da proporção de episódios censurados",
    "mediana_recuperacao_prop_censurados": "Mediana da proporção de episódios censurados",
    "q3_recuperacao_prop_censurados": "Q3 da proporção de episódios censurados",
    "prop_agregada_episodios_censurados": "Episódios censurados ÷ total de episódios",
    "repos_com_episodio_censurado": "Repositórios com ao menos 1 episódio censurado",
    "repos_sem_episodio": "Repositórios sem episódio de recuperação",
    "repos_c1_4_metricas": "Repositórios com 4 métricas em C1",
    "repos_c1_3_metricas": "Repositórios com 3 métricas em C1",
    "repos_c1_ate_2_metricas": "Repositórios com 2 métricas ou menos em C1",
    "repos_geral_nulo": "Repositórios sem classificação geral",
}
INDICADORES_FRACAO = (
    "q1_recuperacao_prop_censurados",
    "mediana_recuperacao_prop_censurados",
    "q3_recuperacao_prop_censurados",
    "prop_agregada_episodios_censurados",
)

TABELAS = {  # nome da tabela -> colunas do CSV
    "descritiva": COLUNAS_DESCRITIVA,
    "comparacao_lead_time": COLUNAS_COMPARACAO,
    "classificacao_c1": COLUNAS_CLASSIFICACAO,
    "distribuicao_c1": COLUNAS_DISTRIBUICAO,
    "censura_e_cobertura": COLUNAS_CENSURA,
}

ROTULOS_METRICA = {
    "frequencia": "Frequência",
    "lead_time": "Lead time (a)",
    "cfr": "CFR (a)",
    "recuperacao": "Recuperação",
    "geral": "Geral",
}
ROTULO_SEM_CLASSIFICACAO = "Sem classificação"


class ErroDataset(ValueError):
    """Dataset ausente ou fora do contrato; guarda todos os problemas encontrados."""

    def __init__(self, problemas: list[str]):
        self.problemas = problemas
        super().__init__(
            f"dataset inválido ({ORIGEM_DATASET}):\n" + "\n".join(f"- {p}" for p in problemas))


# --- leitura e validação ----------------------------------------------------------------


def ler_dataset(caminho: Path) -> pd.DataFrame:
    """Lê o CSV com todas as células como texto (BOM opcional); vazio continua vazio."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroDataset([f"arquivo não encontrado: {caminho}"])
    try:
        return pd.read_csv(caminho, dtype=str, keep_default_na=False, encoding=CODIFICACAO)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as e:
        raise ErroDataset([f"não foi possível ler {caminho}: {e}"]) from e


def _exemplos(linhas: list[tuple[int, str]]) -> str:
    """Até 3 exemplos `linha N = valor` (N = linha do arquivo, cabeçalho = 1)."""
    texto = ", ".join(f"linha {i + 2} = {v!r}" for i, v in linhas[:3])
    return texto + (", ..." if len(linhas) > 3 else "")


def validar(bruto: pd.DataFrame) -> pd.DataFrame:
    """Converte as colunas de `COLUNAS` (texto) para números e confere o contrato.

    Retorna um DataFrame só com essas colunas: `full_name` como texto e as demais como float
    (NaN = ausente). Levanta `ErroDataset` listando todos os problemas: coluna obrigatória
    faltando, `full_name` vazio ou repetido, valor não numérico ou infinito, negativo,
    fração fora de 0–1, contagem não inteira, `cfr_b_n_falharam` > `cfr_b_n_avaliadas` e
    `recuperacao_n_episodios` incoerente com `recuperacao_horas` (0 episódios ⇔ horas vazio;
    sem contagem de episódios, essa coerência não é verificada).
    """
    faltando = [c for c in COLUNAS.values() if c not in bruto.columns]
    if faltando:
        raise ErroDataset([f"coluna obrigatória ausente: {c}" for c in faltando])
    if bruto.empty:
        raise ErroDataset(["o dataset não tem nenhuma linha de repositório"])

    problemas: list[str] = []
    nomes = bruto[COLUNAS["full_name"]].fillna("").str.strip()
    vazios = [(i, v) for i, v in nomes.items() if not v]
    if vazios:
        problemas.append(f"coluna {COLUNAS['full_name']}: vazia em {_exemplos(vazios)}")
    repetidos = sorted(set(nomes[nomes.duplicated() & (nomes != "")]))
    if repetidos:
        problemas.append(f"coluna {COLUNAS['full_name']}: repositório repetido: {', '.join(repetidos)}")

    dados = pd.DataFrame({COLUNAS["full_name"]: nomes})
    for nome in NUMERICAS:
        coluna = COLUNAS[nome]
        valores, invalidos = [], []
        for i, texto in bruto[coluna].items():
            texto = texto.strip() if isinstance(texto, str) else ""
            if not texto:
                valores.append(math.nan)
                continue
            try:
                valor = float(texto)
            except ValueError:
                valor = math.nan
            if not math.isfinite(valor):
                invalidos.append((i, texto))
            valores.append(valor)
        serie = pd.Series(valores, index=bruto.index, dtype=float)
        if invalidos:
            problemas.append(f"coluna {coluna}: valor não numérico em {_exemplos(invalidos)}")
        negativos = [(i, bruto.at[i, coluna]) for i in serie.index[serie < 0]]
        if negativos:
            problemas.append(f"coluna {coluna}: valor negativo em {_exemplos(negativos)}")
        if nome in FRACOES:
            acima = [(i, bruto.at[i, coluna]) for i in serie.index[serie > 1]]
            if acima:
                problemas.append(f"coluna {coluna}: fração fora de 0–1 em {_exemplos(acima)}")
        if nome in CONTAGENS:
            fracionarias = [(i, bruto.at[i, coluna])
                            for i in serie.index[serie.notna() & (serie % 1 != 0)]]
            if fracionarias:
                problemas.append(f"coluna {coluna}: valor não inteiro em {_exemplos(fracionarias)}")
        dados[coluna] = serie
    if not problemas:  # coerência entre colunas só com cada coluna já válida
        problemas = _incoerencias(dados)
    if problemas:
        raise ErroDataset(problemas)
    return dados


def _incoerencias(dados: pd.DataFrame) -> list[str]:
    """Contagens incoerentes entre colunas da mesma linha (uma mensagem por linha e regra)."""
    falharam, avaliadas = _serie(dados, "cfr_b_n_falharam"), _serie(dados, "cfr_b_n_avaliadas")
    episodios, horas = _serie(dados, "recuperacao_n_episodios"), _serie(dados, "recuperacao")
    c_falharam, c_avaliadas = COLUNAS["cfr_b_n_falharam"], COLUNAS["cfr_b_n_avaliadas"]
    c_episodios, c_horas = COLUNAS["recuperacao_n_episodios"], COLUNAS["recuperacao"]
    problemas = []
    for i in dados.index:
        onde = f"linha {i + 2} ({dados.at[i, COLUNAS['full_name']]})"
        if falharam[i] > avaliadas[i]:
            problemas.append(
                f"{onde}: {c_falharam} ({falharam[i]:g}) maior que {c_avaliadas} ({avaliadas[i]:g})")
        if episodios[i] == 0 and pd.notna(horas[i]):
            problemas.append(f"{onde}: {c_episodios} = 0, mas {c_horas} preenchido")
        if episodios[i] > 0 and pd.isna(horas[i]):
            problemas.append(f"{onde}: {c_episodios} = {episodios[i]:g}, mas {c_horas} vazio")
    return problemas


# --- cálculo (puro) ---------------------------------------------------------------------


def _serie(dados: pd.DataFrame, nome: str) -> pd.Series:
    return dados[COLUNAS[nome]]


def _inteiro(valor: float) -> int | float | None:
    """Contagens chegam como float; devolve int quando o valor é inteiro e None se ausente."""
    if _vazio(valor):
        return None
    return int(valor) if float(valor).is_integer() else float(valor)


def _soma(serie: pd.Series) -> int | float | None:
    """Soma dos valores presentes; None (nunca 0) quando todos estão ausentes."""
    return _inteiro(serie.sum(min_count=1))


def _tabela(linhas: list[dict], colunas: tuple[str, ...]) -> pd.DataFrame:
    """DataFrame de objetos Python (preserva int e None, sem virar float/NaN)."""
    return pd.DataFrame([[linha.get(c) for c in colunas] for linha in linhas],
                        columns=list(colunas), dtype=object)


def tabela_descritiva(dados: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por métrica/variante, na unidade do dataset (horas, releases/semana, fração)."""
    linhas = []
    for rq, metrica, variante, unidade, nome in LINHAS_DESCRITIVA:
        resumo = resumo_descritivo(_serie(dados, nome).tolist())
        linhas.append({"rq": rq, "metrica": metrica, "variante": variante, "unidade": unidade, **resumo})
    return _tabela(linhas, COLUNAS_DESCRITIVA)


def tabela_comparacao_lead_time(dados: pd.DataFrame) -> pd.DataFrame:
    """Hipótese da RQ 02: (b) < (a) na maioria dos repositórios com as duas variantes.

    `prop_b_menor` é fração 0–1 dos pares; a razão (b)/(a) usa só pares com (a) > 0.
    """
    a, b = _serie(dados, "lead_time_a"), _serie(dados, "lead_time_b")
    pares = a.notna() & b.notna()
    a, b = a[pares], b[pares]
    n_pares = int(pares.sum())
    n_b_menor = int((b < a).sum())
    razoes = (b[a > 0] / a[a > 0]).tolist()
    linha = {
        "n_pares": n_pares,
        "n_b_menor": n_b_menor,
        "n_iguais": int((b == a).sum()),
        "n_b_maior": int((b > a).sum()),
        "prop_b_menor": n_b_menor / n_pares if n_pares else None,
        "mediana_razao_b_a": statistics.median(razoes) if razoes else None,
    }
    return _tabela([linha], COLUNAS_COMPARACAO)


def tabela_classificacao_c1(dados: pd.DataFrame) -> pd.DataFrame:
    """C1: frequência, lead time (a), CFR (a) e recuperação, via `classificar_repositorio`."""
    linhas = []
    for _, repo in dados.iterrows():
        categorias = classificar_repositorio(
            repo[COLUNAS["frequencia"]], repo[COLUNAS["lead_time_a"]],
            repo[COLUNAS["cfr_a"]], repo[COLUNAS["recuperacao"]])
        n_metricas = sum(categorias[m] is not None for m in METRICAS_C1)
        linhas.append({"full_name": repo[COLUNAS["full_name"]], **categorias, "n_metricas": n_metricas})
    return _tabela(linhas, COLUNAS_CLASSIFICACAO)


def tabela_distribuicao_c1(classificacao: pd.DataFrame) -> pd.DataFrame:
    """Contagem e proporção (fração 0–1 do total de repositórios) por categoria e métrica."""
    linhas = []
    for metrica in (*METRICAS_C1, "geral"):
        for categoria, contagem in distribuicao_categorias(classificacao[metrica].tolist()).items():
            linhas.append({"metrica": metrica, "categoria": categoria, **contagem})
    return _tabela(linhas, COLUNAS_DISTRIBUICAO)


def tabela_censura_e_cobertura(dados: pd.DataFrame, classificacao: pd.DataFrame) -> pd.DataFrame:
    """Totais de censura (CFR (b) e recuperação) e de cobertura da classificação C1.

    Somas usam só os valores presentes (vazias, nunca 0, se todos forem ausentes); os
    ausentes ficam em `repos_sem_contagem_*`. `prop_agregada_episodios_censurados` =
    Σ(prop·n_episodios) ÷ Σn_episodios (episódios censurados ÷ total, fração 0–1), nas
    linhas com as duas colunas preenchidas; vazia sem episódios.
    """
    prop = _serie(dados, "recuperacao_prop_censurados")
    episodios = _serie(dados, "recuperacao_n_episodios")
    resumo_prop = resumo_descritivo(prop.tolist())
    ambos = prop.notna() & episodios.notna()
    total_episodios = episodios[ambos].sum()
    agregada = float((prop[ambos] * episodios[ambos]).sum() / total_episodios) if total_episodios else None
    n_metricas = classificacao["n_metricas"]
    valores = {
        "total_repositorios": len(dados),
        "soma_cfr_b_n_avaliadas": _soma(_serie(dados, "cfr_b_n_avaliadas")),
        "soma_cfr_b_n_falharam": _soma(_serie(dados, "cfr_b_n_falharam")),
        "soma_cfr_b_n_censuradas": _soma(_serie(dados, "cfr_b_n_censuradas")),
        "repos_sem_contagem_cfr_b": int(_serie(dados, "cfr_b_n_avaliadas").isna().sum()),
        "soma_recuperacao_n_episodios": _soma(episodios),
        "repos_sem_contagem_episodios": int(episodios.isna().sum()),
        "q1_recuperacao_prop_censurados": resumo_prop["q1"],
        "mediana_recuperacao_prop_censurados": resumo_prop["mediana"],
        "q3_recuperacao_prop_censurados": resumo_prop["q3"],
        "prop_agregada_episodios_censurados": agregada,
        "repos_com_episodio_censurado": int((prop > 0).sum()),
        "repos_sem_episodio": int((episodios == 0).sum()),
        "repos_c1_4_metricas": int((n_metricas == 4).sum()),
        "repos_c1_3_metricas": int((n_metricas == 3).sum()),
        "repos_c1_ate_2_metricas": int((n_metricas <= 2).sum()),
        "repos_geral_nulo": int(classificacao["geral"].isna().sum()),
    }
    return _tabela([{"indicador": k, "valor": v} for k, v in valores.items()], COLUNAS_CENSURA)


def calcular(dados: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Todas as tabelas, a partir do DataFrame já validado por `validar`."""
    classificacao = tabela_classificacao_c1(dados)
    return {
        "descritiva": tabela_descritiva(dados),
        "comparacao_lead_time": tabela_comparacao_lead_time(dados),
        "classificacao_c1": classificacao,
        "distribuicao_c1": tabela_distribuicao_c1(classificacao),
        "censura_e_cobertura": tabela_censura_e_cobertura(dados, classificacao),
    }


# --- resumo.md (puro) -------------------------------------------------------------------


def _vazio(valor: object) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def formatar_numero(valor: object) -> str:
    """Inteiro sem casas; real com 2 casas e vírgula decimal; ausente = travessão."""
    if _vazio(valor):
        return "—"
    if isinstance(valor, (int, np.integer)):
        return str(valor)
    # arredonda meio para cima sobre o decimal impresso (0,625 -> 0,63; f"{:.2f}" daria 0,62)
    arredondado = Decimal(repr(float(valor))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{arredondado:.2f}".replace(".", ",")


def formatar_fracao(valor: object) -> str:
    """Fração 0–1 com 2 casas e o percentual entre parênteses: `0,25 (25,00 %)`."""
    if _vazio(valor):
        return "—"
    return f"{formatar_numero(float(valor))} ({formatar_numero(float(valor) * 100)} %)"


def _tabela_md(cabecalho: list[str], linhas: Iterable[list[str]], n_texto: int) -> str:
    """Tabela Markdown; as `n_texto` primeiras colunas à esquerda, as demais à direita."""
    alinhamento = ["---"] * n_texto + ["---:"] * (len(cabecalho) - n_texto)
    saida = ["| " + " | ".join(cabecalho) + " |", "| " + " | ".join(alinhamento) + " |"]
    saida += ["| " + " | ".join(linha) + " |" for linha in linhas]
    return "\n".join(saida)


def _rotulo_categoria(categoria: str) -> str:
    return ROTULO_SEM_CLASSIFICACAO if categoria == SEM_CLASSIFICACAO else categoria


def gerar_resumo_md(tabelas: dict[str, pd.DataFrame]) -> str:
    """Tabelas Markdown das saídas, prontas para colar no artigo (sem interpretação)."""
    partes = ["# RQ 01 a RQ 04: tabelas"]

    linhas = []
    for linha in tabelas["descritiva"].to_dict("records"):
        formato = formatar_fracao if linha["unidade"] == UNIDADE_FRACAO else formatar_numero
        linhas.append([linha["rq"], linha["metrica"], linha["variante"] or "—", linha["unidade"],
                       formatar_numero(linha["n"]), formatar_numero(linha["n_ausentes"]),
                       *(formato(linha[e]) for e in ESTATISTICAS)])
    partes += ["## Estatística descritiva", _tabela_md(
        ["RQ", "Métrica", "Variante", "Unidade", "n", "Ausentes",
         "Mediana", "Q1", "Q3", "IQR", "Mínimo", "Máximo"], linhas, 4)]

    comp = tabelas["comparacao_lead_time"].to_dict("records")[0]
    partes += ["## Lead time: variante (b) × variante (a)", _tabela_md(
        ["Pares", "(b) < (a)", "(b) = (a)", "(b) > (a)", "Proporção (b) < (a)", "Mediana (b)/(a)"],
        [[formatar_numero(comp["n_pares"]), formatar_numero(comp["n_b_menor"]),
          formatar_numero(comp["n_iguais"]), formatar_numero(comp["n_b_maior"]),
          formatar_fracao(comp["prop_b_menor"]), formatar_numero(comp["mediana_razao_b_a"])]], 0)]

    dist = tabelas["distribuicao_c1"]
    metricas = (*METRICAS_C1, "geral")
    linhas = []
    for categoria in ORDEM_DISTRIBUICAO:
        celulas = []
        for metrica in metricas:
            linha = dist[(dist["metrica"] == metrica) & (dist["categoria"] == categoria)].iloc[0]
            pct = "—" if _vazio(linha["proporcao"]) else f"{formatar_numero(linha['proporcao'] * 100)} %"
            celulas.append(f"{linha['n']} ({pct})")
        linhas.append([_rotulo_categoria(categoria), *celulas])
    partes += ["## Distribuição das categorias DORA (C1)", _tabela_md(
        ["Categoria", *(ROTULOS_METRICA[m] for m in metricas)], linhas, 1)]

    linhas = []
    for linha in tabelas["censura_e_cobertura"].to_dict("records"):
        formato = formatar_fracao if linha["indicador"] in INDICADORES_FRACAO else formatar_numero
        linhas.append([INDICADORES[linha["indicador"]], formato(linha["valor"])])
    partes += ["## Censura e cobertura", _tabela_md(["Indicador", "Valor"], linhas, 1)]

    linhas = [
        [linha["full_name"], *("—" if _vazio(linha[m]) else linha[m] for m in metricas),
         formatar_numero(linha["n_metricas"])]
        for linha in tabelas["classificacao_c1"].to_dict("records")
    ]
    partes += ["## Classificação DORA por repositório (C1)", _tabela_md(
        ["Repositório", *(ROTULOS_METRICA[m] for m in metricas), "Métricas"], linhas, 6)]
    return "\n\n".join(partes) + "\n"


# --- figuras (puras: devolvem Figure, sem disco) ------------------------------------------

COR_SERIE = "#2a78d6"
COR_TEXTO = "#0b0b0b"
COR_TEXTO_SECUNDARIO = "#52514e"
COR_CORTE = "#8a8984"
COR_GRADE = "#e4e3df"

CORTES_FREQUENCIA = (
    (dora.FREQUENCIA_ELITE, "Elite ≥ 7/semana"),
    (dora.FREQUENCIA_HIGH, "High ≥ 1/semana"),
    (dora.FREQUENCIA_MEDIUM, "Medium ≥ 1/mês"),
)
CORTES_LEAD_TIME = (
    (dora.LEAD_TIME_ELITE, "Elite < 1 dia"),
    (dora.LEAD_TIME_HIGH, "High < 1 semana"),
    (dora.LEAD_TIME_MEDIUM, "Medium < 30 dias"),
)
CORTES_CFR = (
    (dora.CFR_ELITE, "Elite ≤ 15 %"),
    (dora.CFR_HIGH, "High ≤ 30 %"),
    (dora.CFR_MEDIUM, "Medium ≤ 45 %"),
)
CORTES_RECUPERACAO = (
    (dora.RECUPERACAO_ELITE, "Elite < 1 hora"),
    (dora.RECUPERACAO_HIGH, "High < 1 dia"),
    (dora.RECUPERACAO_MEDIUM, "Medium < 1 semana"),
)


def _nova_figura() -> Figure:
    figura = Figure(figsize=(7.0, 4.8), layout="constrained")
    FigureCanvasAgg(figura)  # renderização Agg, sem pyplot nem backend global
    return figura


def _estilo_eixos(eixos) -> None:
    for lado in ("top", "right"):
        eixos.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        eixos.spines[lado].set_color(COR_TEXTO_SECUNDARIO)
    eixos.tick_params(colors=COR_TEXTO_SECUNDARIO, labelcolor=COR_TEXTO)
    eixos.yaxis.grid(True, color=COR_GRADE, linewidth=0.8)
    eixos.set_axisbelow(True)


def valores_para_figura(serie: pd.Series, escala_log: bool) -> tuple[np.ndarray, int]:
    """Valores presentes e quantos ≤ 0 foram excluídos (só em escala log; senão 0)."""
    valores = serie.dropna().to_numpy(dtype=float)
    if not escala_log:
        return valores, 0
    return valores[valores > 0], int((valores <= 0).sum())


def estatisticas_caixa(serie: pd.Series, escala_log: bool) -> dict | None:
    """Estatísticas da caixa, as mesmas da descritiva: mediana e quartis de TODOS os valores.

    Os valores ≤ 0 entram na mediana e nos quartis mesmo em escala log (só os pontos são
    omitidos). Bigodes = mínimo e máximo dos valores desenhados como ponto (em log, os > 0;
    sem regra de 1,5·IQR). `truncada` lista as estatísticas da caixa ≤ 0 em escala log, que
    não cabem no eixo. None quando não há valor presente.
    """
    resumo = resumo_descritivo(serie.tolist())
    if resumo["n"] == 0:
        return None
    pontos, _ = valores_para_figura(serie, escala_log)
    truncada = []
    if escala_log:
        truncada = [nome for nome, chave in (("mediana", "mediana"), ("Q1", "q1"), ("Q3", "q3"))
                    if resumo[chave] <= 0]
    return {
        "med": resumo["mediana"],
        "q1": resumo["q1"],
        "q3": resumo["q3"],
        "whislo": float(pontos.min()) if len(pontos) else None,
        "whishi": float(pontos.max()) if len(pontos) else None,
        "truncada": truncada,
    }


def _piso_log(series: list[tuple[str, pd.Series]], cortes: tuple[tuple[float, str], ...]) -> float:
    """Base do eixo log onde as estatísticas ≤ 0 são desenhadas (metade do menor valor > 0)."""
    positivos = [valor for _, serie in series for valor in valores_para_figura(serie, True)[0]]
    return min(positivos + [valor for valor, _ in cortes], default=1.0) / 2


def figura_boxplot(
    series: list[tuple[str, pd.Series]],
    *,
    titulo: str,
    rotulo_y: str,
    cortes: tuple[tuple[float, str], ...],
    escala_log: bool,
    limites_y: tuple[float, float] | None = None,
) -> Figure:
    """Caixa com as estatísticas de `estatisticas_caixa`, pontos sobrepostos e cortes DORA.

    Em escala log, valores ≤ 0 não viram ponto (a contagem vai no título), mas entram na
    caixa; mediana ou quartil ≤ 0 é desenhado na base do eixo e avisado no título.
    """
    figura = _nova_figura()
    eixos = figura.add_subplot()
    _estilo_eixos(eixos)
    gerador = np.random.default_rng(0)  # jitter reprodutível
    piso = _piso_log(series, cortes) if escala_log else None
    resumo_n, resumo_excluidos, resumo_truncada = [], [], []
    for posicao, (rotulo, serie) in enumerate(series, start=1):
        pontos, excluidos = valores_para_figura(serie, escala_log)
        caixa = estatisticas_caixa(serie, escala_log)
        sufixo = f" {rotulo.split()[0]}" if len(series) > 1 else ""  # "(a)", "(b)"
        resumo_n.append(f"{int(serie.notna().sum())}{sufixo}")
        resumo_excluidos.append(f"{excluidos}{sufixo}")
        if caixa and caixa["truncada"]:
            prefixo = f"{sufixo.strip()} " if sufixo else ""
            resumo_truncada.append(f"{prefixo}{' e '.join(caixa['truncada'])} ≤ 0")
        if caixa is None or caixa["whishi"] is None:
            eixos.text(posicao, 0.5, "sem dados" if caixa is None else "todos os valores ≤ 0",
                       transform=eixos.get_xaxis_transform(), ha="center", color=COR_TEXTO_SECUNDARIO)
            continue
        desenho = {chave: caixa[chave] for chave in ("med", "q1", "q3", "whislo", "whishi")}
        if escala_log:
            for chave in ("med", "q1", "q3"):
                desenho[chave] = max(desenho[chave], piso)
        desenho["whislo"] = min(desenho["whislo"], desenho["q1"])
        eixos.bxp([desenho], positions=[posicao], widths=0.5, showfliers=False,
                  boxprops={"color": COR_TEXTO_SECUNDARIO},
                  whiskerprops={"color": COR_TEXTO_SECUNDARIO},
                  capprops={"color": COR_TEXTO_SECUNDARIO},
                  medianprops={"color": COR_TEXTO, "linewidth": 2})
        deslocamento = gerador.uniform(-0.15, 0.15, size=len(pontos))
        eixos.scatter(posicao + deslocamento, pontos, s=18, color=COR_SERIE, alpha=0.6,
                      edgecolors="white", linewidths=0.5, zorder=3)

    if escala_log:
        eixos.set_yscale("log")
    for valor, rotulo in cortes:
        eixos.axhline(valor, color=COR_CORTE, linestyle="--", linewidth=1, zorder=1)
        eixos.text(1.01, valor, rotulo, transform=eixos.get_yaxis_transform(),
                   va="center", ha="left", fontsize=8, color=COR_TEXTO_SECUNDARIO)
    if limites_y:
        eixos.set_ylim(*limites_y)
    elif resumo_truncada:
        eixos.set_ylim(bottom=piso)  # caixa truncada encosta na base do eixo
    eixos.set_xticks(range(1, len(series) + 1), [rotulo for rotulo, _ in series])
    eixos.set_xlim(0.5, len(series) + 0.5)
    eixos.set_ylabel(rotulo_y, color=COR_TEXTO)

    subtitulo = "n = " + ", ".join(resumo_n)
    if escala_log:
        subtitulo += "; pontos ≤ 0 omitidos no eixo log: " + ", ".join(resumo_excluidos)
    if resumo_truncada:
        subtitulo += "\ncaixa truncada no eixo: " + "; ".join(resumo_truncada)
    eixos.set_title(f"{titulo}\n{subtitulo}", fontsize=10, color=COR_TEXTO)
    return figura


def figura_rq01(dados: pd.DataFrame) -> Figure:
    return figura_boxplot(
        [("Repositórios", _serie(dados, "frequencia"))],
        titulo="RQ 01: frequência de deploy por repositório",
        rotulo_y="Frequência (releases/semana, escala log)",
        cortes=CORTES_FREQUENCIA, escala_log=True)


def figura_rq02(dados: pd.DataFrame) -> Figure:
    return figura_boxplot(
        [("(a) por release", _serie(dados, "lead_time_a")),
         ("(b) por commit", _serie(dados, "lead_time_b"))],
        titulo="RQ 02: lead time por repositório, variantes (a) e (b)",
        rotulo_y="Lead time (horas, escala log)",
        cortes=CORTES_LEAD_TIME, escala_log=True)


def figura_rq03(dados: pd.DataFrame) -> Figure:
    return figura_boxplot(
        [("(a) proxy de CI", _serie(dados, "cfr_a")),
         ("(b) proxy de entrega", _serie(dados, "cfr_b"))],
        titulo="RQ 03: change failure rate por repositório, variantes (a) e (b)",
        rotulo_y="CFR (fração de falhas, 0 a 1)",
        cortes=CORTES_CFR, escala_log=False, limites_y=(-0.02, 1.02))


def figura_rq04(dados: pd.DataFrame) -> Figure:
    return figura_boxplot(
        [("Repositórios", _serie(dados, "recuperacao"))],
        titulo="RQ 04: tempo de recuperação por repositório (mediana dos episódios)",
        rotulo_y="Tempo de recuperação (horas, escala log)",
        cortes=CORTES_RECUPERACAO, escala_log=True)


def figura_c1(classificacao: pd.DataFrame) -> Figure:
    """Barras da classificação geral C1, de Elite a Low, mais os sem classificação."""
    distribuicao = distribuicao_categorias(classificacao["geral"].tolist())
    rotulos = [_rotulo_categoria(c) for c in ORDEM_DISTRIBUICAO]
    contagens = [distribuicao[c]["n"] for c in ORDEM_DISTRIBUICAO]
    figura = _nova_figura()
    eixos = figura.add_subplot()
    _estilo_eixos(eixos)
    cores = [COR_SERIE] * len(CATEGORIAS) + [COR_CORTE]  # sem classificação em cinza
    barras = eixos.bar(rotulos, contagens, color=cores, width=0.6)
    eixos.bar_label(barras, labels=[str(n) for n in contagens], padding=2, color=COR_TEXTO)
    eixos.set_ylim(0, max(contagens + [1]) * 1.15)
    eixos.yaxis.set_major_locator(MaxNLocator(integer=True))
    eixos.set_xlabel("Classificação DORA geral (C1)", color=COR_TEXTO)
    eixos.set_ylabel("Repositórios (nº)", color=COR_TEXTO)
    eixos.set_title(f"Classificação DORA geral, configuração C1 (n = {len(classificacao)} repositórios)",
                    fontsize=10, color=COR_TEXTO)
    return figura


def gerar_figuras(dados: pd.DataFrame, tabelas: dict[str, pd.DataFrame]) -> dict[str, Figure]:
    """Nome do arquivo PNG -> figura."""
    return {
        "rq01_frequencia.png": figura_rq01(dados),
        "rq02_lead_time.png": figura_rq02(dados),
        "rq03_cfr.png": figura_rq03(dados),
        "rq04_recuperacao.png": figura_rq04(dados),
        "c1_distribuicao.png": figura_c1(tabelas["classificacao_c1"]),
    }


# --- gravação (disco) -------------------------------------------------------------------


def _celula(valor: object) -> str:
    if _vazio(valor):
        return ""
    if isinstance(valor, (float, np.floating)):
        return repr(round(float(valor), CASAS_CSV))
    return str(valor)


def gravar_csv(caminho: Path, tabela: pd.DataFrame) -> None:
    """CSV com vírgula, UTF-8 com BOM; ausente = célula vazia; reais com até 6 casas."""
    with caminho.open("w", encoding=CODIFICACAO, newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(tabela.columns)
        escritor.writerows([_celula(v) for v in linha] for linha in tabela.itertuples(index=False))


def gravar(tabelas: dict[str, pd.DataFrame], figuras: dict[str, Figure], pasta: Path) -> None:
    """Grava os CSVs, o resumo.md e as figuras em `pasta` (criada se preciso)."""
    pasta_figuras = pasta / PASTA_FIGURAS
    pasta_figuras.mkdir(parents=True, exist_ok=True)
    for nome in TABELAS:
        gravar_csv(pasta / f"{nome}.csv", tabelas[nome])
    (pasta / ARQUIVO_RESUMO).write_text(gerar_resumo_md(tabelas), encoding="utf-8")
    for nome, figura in figuras.items():
        figura.savefig(pasta_figuras / nome, dpi=DPI, facecolor="white")


def executar(caminho_dataset: Path, pasta_saida: Path) -> dict[str, pd.DataFrame]:
    """Lê, valida, calcula e grava; devolve as tabelas. Levanta `ErroDataset`."""
    dados = validar(ler_dataset(caminho_dataset))
    tabelas = calcular(dados)
    gravar(tabelas, gerar_figuras(dados, tabelas), pasta_saida)
    log.info("RQ 01 a 04: %d repositórios; tabelas e figuras gravadas em %s", len(dados), pasta_saida)
    return tabelas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="analises.rq01_rq04",
        description="Descritiva, classificação DORA C1 e figuras das RQ 01 a RQ 04",
    )
    parser.add_argument("--config", default="config.yaml", help="caminho do config.yaml")
    parser.add_argument("--dataset", help=f"CSV do dataset (padrão: <caminhos.saida>/{ARQUIVO_DATASET})")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        config = carregar_config(args.config)
    except ErroConfiguracao as e:
        log.error("%s", e)
        return 2

    saida = Path(config.dir_saida)
    dataset = Path(args.dataset) if args.dataset else saida / ARQUIVO_DATASET
    try:
        executar(dataset, saida / PASTA_SAIDA)
    except ErroDataset as e:
        log.error("%s", e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
