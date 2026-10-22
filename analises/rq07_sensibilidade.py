"""RQ 07 (#49): sensibilidade da classificação DORA à definição operacional.

Uso: ``python -m analises.rq07_sensibilidade --config config.yaml [--dataset CAMINHO]``.
Não acessa a rede.

Entrada: ``<caminhos.saida>/metricas_repos.csv`` (Issue #35), uma linha por repositório, e as
combinações de definições de ``config.yaml → sensibilidade.combinacoes``. Cada combinação escolhe:

- a **unidade de deploy**, que define a frequência: ``release`` (``frequencia_semana``),
  ``release_prerelease`` (``frequencia_prerelease_semana``) ou ``tag`` (``frequencia_tag_semana``);
- o **lead time**: ``a`` por release (``lead_time_release_horas``) ou ``b`` por commit
  (``lead_time_commit_horas``);
- o **CFR**: ``a`` proxy de CI (``cfr_ci``) ou ``b`` proxy de entrega (``cfr_entrega``).

O tempo de recuperação (``recuperacao_mediana_horas``) é o mesmo em todas as combinações. Lead
time e CFR (b) só existem para as releases principais, porque a API compare foi coletada só entre
elas; a unidade de deploy altera, portanto, a frequência. Cada repositório é classificado com
``metricas.classificacao.classificar_repositorio``; a categoria geral usa as métricas com valor
(mínimo de três). Repositório sem categoria geral numa combinação fica fora da proporção de
mudança e do kappa desse par (``n_excluidos``) e entra na matriz como ``sem_classificacao``.

Saídas em ``<caminhos.saida>/analises/rq07/`` (CSV com vírgula, UTF-8 com BOM):

- ``combinacoes.csv``: definições e colunas do dataset usadas por combinação;
- ``frequencia_por_unidade.csv``: mediana, quartis e IQR da frequência de deploys em cada unidade;
- ``classificacao_combinacoes.csv``: categoria de cada métrica e a geral, por repositório e combinação;
- ``distribuicao_combinacoes.csv``: repositórios por categoria geral e combinação;
- ``sensibilidade_pares.csv``: por par, n, exclusões, repositórios que mudaram (e para melhor ou pior),
  proporção de mudança, mudanças adjacentes (uma categoria) e saltos (duas ou mais) e kappa de Cohen
  ponderado (pesos lineares) com a faixa de Landis & Koch;
- ``sensibilidade_metricas.csv``: por par, em quantos repositórios cada métrica (frequência, lead time,
  CFR) muda de categoria, e em que direção, para apontar o que move a categoria geral;
- ``matrizes_transicao.csv``: contagem por (categoria na 1ª combinação, categoria na 2ª), por par;
- ``resumo.md``: as tabelas em Markdown (vírgula decimal, 2 casas), sem interpretação;
- ``figuras/*.png``: matrizes de transição e distribuição por combinação.

Códigos de saída: 0 = ok; 2 = configuração ou dataset inválido.
"""

from __future__ import annotations

import argparse
import itertools
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from analises.rq01_rq04 import (
    COR_CORTE,
    COR_SERIE,
    COR_TEXTO,
    COR_TEXTO_SECUNDARIO,
    formatar_numero,
    gravar_csv,
)
from metricas.classificacao import CATEGORIAS, classificar_repositorio
from metricas.concordancia import interpretar_kappa
from metricas.descritiva import resumo_descritivo
from metricas.sensibilidade import (
    ORDEM_MATRIZ,
    SEM_CLASSIFICACAO,
    comparar_classificacoes,
    matriz_transicao,
)
from pipeline.config import MIN_COMBINACOES, Combinacao, ErroConfiguracao, carregar_config

log = logging.getLogger("analises.rq07")

ARQUIVO_DATASET = "metricas_repos.csv"
PASTA_SAIDA = Path("analises") / "rq07"
PASTA_FIGURAS = "figuras"
ARQUIVO_RESUMO = "resumo.md"
CODIFICACAO = "utf-8-sig"
DPI = 150

COLUNA_FREQUENCIA = {
    "release": "frequencia_semana",
    "release_prerelease": "frequencia_prerelease_semana",
    "tag": "frequencia_tag_semana",
}
COLUNA_LEAD_TIME = {"a": "lead_time_release_horas", "b": "lead_time_commit_horas"}
COLUNA_CFR = {"a": "cfr_ci", "b": "cfr_entrega"}
COLUNA_RECUPERACAO = "recuperacao_mediana_horas"
METRICAS = ("frequencia", "lead_time", "cfr", "recuperacao")  # ordem de classificar_repositorio
METRICAS_QUE_VARIAM = ("frequencia", "lead_time", "cfr")     # a recuperação é a mesma em todas
FRACOES = ("cfr_ci", "cfr_entrega")                          # devem estar entre 0 e 1
COLUNAS_NUMERICAS = (*COLUNA_FREQUENCIA.values(), *COLUNA_LEAD_TIME.values(),
                     *COLUNA_CFR.values(), COLUNA_RECUPERACAO)

COLUNAS_COMBINACOES = ("combinacao", "unidade_deploy", "lead_time", "cfr",
                       "coluna_frequencia", "coluna_lead_time", "coluna_cfr")
COLUNAS_FREQUENCIA = ("unidade_deploy", "coluna", "n", "n_ausentes", "mediana", "q1", "q3", "iqr")
COLUNAS_DISTRIBUICAO = ("combinacao", "categoria", "n", "proporcao")
COLUNAS_PARES = ("par", "de", "para", "n_total", "n_comparados", "n_excluidos", "n_mudaram",
                 "prop_mudaram", "n_melhoraram", "n_pioraram", "n_adjacentes", "n_saltos",
                 "kappa_ponderado", "interpretacao")
COLUNAS_METRICAS_PAR = ("par", "metrica", "n_comparados", "n_mudaram", "prop_mudaram",
                        "n_melhoraram", "n_pioraram")
COLUNAS_MATRIZ = ("par", "de", "para", "n")
TABELAS = ("combinacoes", "frequencia_por_unidade", "classificacao_combinacoes", "distribuicao_combinacoes",
           "sensibilidade_pares", "sensibilidade_metricas", "matrizes_transicao")

ROTULO_CATEGORIA = {SEM_CLASSIFICACAO: "Sem classificação"}
ROTULO_UNIDADE = {"release": "release", "release_prerelease": "release + pré-release", "tag": "tag"}
ROTULO_METRICA = {"frequencia": "Frequência", "lead_time": "Lead time", "cfr": "CFR"}
CORES_COMBINACOES = (COR_SERIE, "#e08a1e", "#3b9a5b", "#8a4fb3", "#c24b4b")


class ErroDataset(ValueError):
    """Dataset ausente ou fora do contrato; guarda todos os problemas encontrados."""

    def __init__(self, problemas: list[str]):
        self.problemas = problemas
        super().__init__("dataset inválido (o metricas_repos.csv é produzido pela Issue #35):\n"
                         + "\n".join(f"- {p}" for p in problemas))


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


def validar(bruto: pd.DataFrame) -> pd.DataFrame:
    """Converte as colunas usadas para números e confere o contrato; vazio vira NaN."""
    necessarias = ("full_name", *COLUNAS_NUMERICAS)
    faltando = [c for c in necessarias if c not in bruto.columns]
    if faltando:
        raise ErroDataset([f"colunas ausentes: {', '.join(faltando)}"])
    problemas: list[str] = []
    if bruto.empty:
        problemas.append("nenhuma linha de dados")
    nomes = bruto["full_name"]
    if (nomes.str.strip() == "").any():
        problemas.append("full_name vazio")
    repetidos = sorted(nomes[nomes.duplicated()].unique())
    if repetidos:
        problemas.append(f"full_name repetido: {', '.join(repetidos[:3])}")
    dados = pd.DataFrame({"full_name": nomes})
    for coluna in COLUNAS_NUMERICAS:
        texto = bruto[coluna].str.strip()
        numeros = pd.to_numeric(texto.replace("", np.nan), errors="coerce")
        invalidos = texto[(texto != "") & numeros.isna()]
        if not invalidos.empty:
            problemas.append(f"{coluna}: valor não numérico, ex.: {invalidos.iloc[0]!r}")
        elif np.isinf(numeros.dropna()).any():
            problemas.append(f"{coluna}: valor infinito")
        elif (numeros < 0).any():
            problemas.append(f"{coluna}: valor negativo")
        elif coluna in FRACOES and (numeros > 1).any():
            problemas.append(f"{coluna}: fração fora de 0–1")
        dados[coluna] = numeros
    if problemas:
        raise ErroDataset(problemas)
    return dados.reset_index(drop=True)


def validar_combinacoes(combinacoes: tuple[Combinacao, ...]) -> None:
    if len(combinacoes) < MIN_COMBINACOES:
        raise ErroConfiguracao(
            f"config.yaml → sensibilidade.combinacoes precisa de pelo menos {MIN_COMBINACOES} "
            "combinações para a RQ 07")


# --- cálculo ----------------------------------------------------------------------------


def _numero(valor: float) -> float | None:
    return None if pd.isna(valor) else float(valor)


def classificar_combinacao(dados: pd.DataFrame, combinacao: Combinacao) -> pd.DataFrame:
    """Categoria de cada métrica e a geral, por repositório, segundo as definições da combinação."""
    colunas = {
        "frequencia": COLUNA_FREQUENCIA[combinacao.unidade_deploy],
        "lead_time": COLUNA_LEAD_TIME[combinacao.lead_time],
        "cfr": COLUNA_CFR[combinacao.cfr],
        "recuperacao": COLUNA_RECUPERACAO,
    }
    linhas = [
        classificar_repositorio(**{m: _numero(linha[c]) for m, c in colunas.items()})
        for linha in dados.to_dict("records")
    ]
    return pd.DataFrame(linhas, columns=[*METRICAS, "geral"], dtype=object)


def calcular(dados: pd.DataFrame, combinacoes: tuple[Combinacao, ...]) -> dict[str, pd.DataFrame]:
    """Todas as tabelas da RQ 07 (nome → DataFrame)."""
    classes = {c.nome: classificar_combinacao(dados, c) for c in combinacoes}

    definicoes = pd.DataFrame([{
        "combinacao": c.nome, "unidade_deploy": c.unidade_deploy,
        "lead_time": c.lead_time, "cfr": c.cfr,
        "coluna_frequencia": COLUNA_FREQUENCIA[c.unidade_deploy],
        "coluna_lead_time": COLUNA_LEAD_TIME[c.lead_time], "coluna_cfr": COLUNA_CFR[c.cfr],
    } for c in combinacoes], columns=COLUNAS_COMBINACOES)

    unidades = list(dict.fromkeys(c.unidade_deploy for c in combinacoes))
    frequencia = []
    for unidade in unidades:
        coluna = COLUNA_FREQUENCIA[unidade]
        resumo = resumo_descritivo(dados[coluna].tolist())
        frequencia.append({"unidade_deploy": unidade, "coluna": coluna,
                           **{k: resumo[k] for k in ("n", "n_ausentes", "mediana", "q1", "q3", "iqr")}})

    por_repositorio = pd.DataFrame({"full_name": dados["full_name"]})
    for nome, tabela in classes.items():
        for coluna in tabela.columns:
            por_repositorio[f"{nome}_{coluna}"] = tabela[coluna]

    distribuicao = []
    for nome, tabela in classes.items():
        gerais = ["sem_classificacao" if pd.isna(g) else g for g in tabela["geral"]]
        for categoria in ORDEM_MATRIZ:
            n = sum(1 for g in gerais if g == categoria)
            distribuicao.append({"combinacao": nome, "categoria": categoria, "n": n,
                                 "proporcao": n / len(gerais)})

    pares, metricas_par, matrizes = [], [], []
    for a, b in itertools.combinations([c.nome for c in combinacoes], 2):
        par = f"{a}x{b}"
        comparacao = comparar_classificacoes(classes[a]["geral"].tolist(), classes[b]["geral"].tolist())
        kappa = comparacao["kappa_ponderado"]
        pares.append({"par": par, "de": a, "para": b, **comparacao,
                      "interpretacao": interpretar_kappa(kappa)})
        for metrica in METRICAS_QUE_VARIAM:
            c = comparar_classificacoes(classes[a][metrica].tolist(), classes[b][metrica].tolist())
            metricas_par.append({"par": par, "metrica": metrica, **{k: c[k] for k in (
                "n_comparados", "n_mudaram", "prop_mudaram", "n_melhoraram", "n_pioraram")}})
        matriz = matriz_transicao(classes[a]["geral"].tolist(), classes[b]["geral"].tolist())
        matrizes += [{"par": par, "de": de, "para": para, "n": n} for (de, para), n in matriz.items()]

    return {
        "combinacoes": definicoes,
        "frequencia_por_unidade": pd.DataFrame(frequencia, columns=COLUNAS_FREQUENCIA),
        "classificacao_combinacoes": por_repositorio,
        "distribuicao_combinacoes": pd.DataFrame(distribuicao, columns=COLUNAS_DISTRIBUICAO),
        "sensibilidade_pares": pd.DataFrame(pares, columns=COLUNAS_PARES),
        "sensibilidade_metricas": pd.DataFrame(metricas_par, columns=COLUNAS_METRICAS_PAR),
        "matrizes_transicao": pd.DataFrame(matrizes, columns=COLUNAS_MATRIZ),
    }


# --- resumo em Markdown ----------------------------------------------------------------


def _rotulo(categoria: str) -> str:
    return ROTULO_CATEGORIA.get(categoria, categoria)


def _contagem_pct(n: int, total: int, proporcao: float | None) -> str:
    """`146 (48,67 %)`; ausente = travessão."""
    if proporcao is None or pd.isna(proporcao):
        return "—"
    return f"{n} ({formatar_numero(proporcao * 100)} %)"


def _tabela_md(cabecalho: list[str], linhas: list[list[str]], n_texto: int,
               texto_final: bool = False) -> str:
    """Tabela Markdown: `n_texto` primeiras colunas (e a última, se `texto_final`) à esquerda."""
    alinhamento = ["---"] * n_texto + ["---:"] * (len(cabecalho) - n_texto)
    if texto_final:
        alinhamento[-1] = "---"
    saida = ["| " + " | ".join(cabecalho) + " |", "| " + " | ".join(alinhamento) + " |"]
    return "\n".join(saida + ["| " + " | ".join(linha) + " |" for linha in linhas])


def gerar_resumo_md(tabelas: dict[str, pd.DataFrame]) -> str:
    """Tabelas Markdown das saídas, prontas para o artigo (sem interpretação)."""
    partes = ["# RQ 07: sensibilidade da classificação DORA", "", "## Combinações", ""]
    partes.append(_tabela_md(
        ["Combinação", "Unidade de deploy", "Lead time", "CFR"],
        [[l["combinacao"], ROTULO_UNIDADE[l["unidade_deploy"]], f"({l['lead_time']})", f"({l['cfr']})"]
         for l in tabelas["combinacoes"].to_dict("records")], 4))

    partes += ["", "## Frequência de deploys por unidade de deploy (releases ou tags por semana)", ""]
    partes.append(_tabela_md(
        ["Unidade de deploy", "n", "Mediana", "Q1", "Q3", "IQR"],
        [[ROTULO_UNIDADE[l["unidade_deploy"]], str(l["n"]), *[formatar_numero(l[k]) for k in ("mediana", "q1", "q3", "iqr")]]
         for l in tabelas["frequencia_por_unidade"].to_dict("records")], 1))

    distribuicao = tabelas["distribuicao_combinacoes"]
    nomes = list(tabelas["combinacoes"]["combinacao"])
    partes += ["", "## Categoria geral por combinação", ""]
    linhas = []
    for categoria in ORDEM_MATRIZ:
        celulas = []
        for nome in nomes:
            l = distribuicao[(distribuicao["combinacao"] == nome)
                             & (distribuicao["categoria"] == categoria)].iloc[0]
            celulas.append(f"{l['n']} ({formatar_numero(l['proporcao'] * 100)} %)")
        linhas.append([_rotulo(categoria), *celulas])
    partes.append(_tabela_md(["Categoria", *nomes], linhas, 1))

    partes += ["", "## Mudança de categoria geral e kappa ponderado, por par", ""]
    partes.append(_tabela_md(
        ["Par", "Comparados", "Excluídos", "Mudaram", "Melhoraram", "Pioraram", "Adjacentes",
         "Saltos", "κ ponderado", "Interpretação"],
        [[l["par"], str(l["n_comparados"]), str(l["n_excluidos"]),
          _contagem_pct(l["n_mudaram"], l["n_comparados"], l["prop_mudaram"]),
          str(l["n_melhoraram"]), str(l["n_pioraram"]), str(l["n_adjacentes"]), str(l["n_saltos"]),
          formatar_numero(l["kappa_ponderado"]),
          l["interpretacao"]] for l in tabelas["sensibilidade_pares"].to_dict("records")], 1,
        texto_final=True))
    partes += ["", "Melhoraram e pioraram contam a categoria da segunda combinação do par em relação à "
               "da primeira. Adjacentes mudaram uma categoria; saltos, duas ou mais. Excluídos são os "
               "repositórios sem categoria geral em alguma das duas.", ""]

    partes += ["## Mudança de categoria por métrica", ""]
    partes.append(_tabela_md(
        ["Par", "Métrica", "Comparados", "Mudaram", "Melhoraram", "Pioraram"],
        [[l["par"], ROTULO_METRICA[l["metrica"]], str(l["n_comparados"]),
          _contagem_pct(l["n_mudaram"], l["n_comparados"], l["prop_mudaram"]),
          str(l["n_melhoraram"]), str(l["n_pioraram"])]
         for l in tabelas["sensibilidade_metricas"].to_dict("records")], 2))

    matrizes = tabelas["matrizes_transicao"]
    for par in tabelas["sensibilidade_pares"]["par"]:
        a, b = par.split("x")
        partes += ["", f"## Matriz de transição {a} → {b}", "", f"Linhas: categoria em {a}; colunas: em {b}.", ""]
        sub = matrizes[matrizes["par"] == par]
        usadas = [c for c in ORDEM_MATRIZ
                  if c != SEM_CLASSIFICACAO or sub[(sub["de"] == c) | (sub["para"] == c)]["n"].sum() > 0]
        linhas = [[_rotulo(de), *[str(int(sub[(sub["de"] == de) & (sub["para"] == para)]["n"].iloc[0]))
                                  for para in usadas]] for de in usadas]
        partes.append(_tabela_md([f"{a} \\ {b}", *[_rotulo(c) for c in usadas]], linhas, 1))
    return "\n".join(partes) + "\n"


# --- figuras ---------------------------------------------------------------------------


def figura_transicao(tabelas: dict[str, pd.DataFrame]) -> Figure:
    """Um mapa de calor por par: linhas = 1ª combinação, colunas = 2ª, de Elite a Low."""
    pares = tabelas["sensibilidade_pares"].to_dict("records")
    figura = Figure(figsize=(4.6 * len(pares), 4.8), layout="constrained")
    FigureCanvasAgg(figura)  # renderização Agg, sem pyplot nem backend global
    matrizes = tabelas["matrizes_transicao"]
    categorias = list(reversed(CATEGORIAS))
    for eixos, par in zip(figura.subplots(1, len(pares), squeeze=False)[0], pares):
        sub = matrizes[matrizes["par"] == par["par"]]
        valores = np.array([[int(sub[(sub["de"] == de) & (sub["para"] == para)]["n"].iloc[0])
                             for para in categorias] for de in categorias])
        eixos.imshow(valores, cmap="Blues", vmin=0, vmax=max(valores.max(), 1))
        for i, j in itertools.product(range(len(categorias)), repeat=2):
            cor = "white" if valores[i, j] > valores.max() * 0.55 else COR_TEXTO
            eixos.text(j, i, str(valores[i, j]), ha="center", va="center", color=cor, fontsize=10)
        eixos.set_xticks(range(len(categorias)), categorias, color=COR_TEXTO_SECUNDARIO)
        eixos.set_yticks(range(len(categorias)), categorias, color=COR_TEXTO_SECUNDARIO)
        eixos.set_xlabel(f"Categoria geral em {par['para']}", color=COR_TEXTO)
        eixos.set_ylabel(f"Categoria geral em {par['de']}", color=COR_TEXTO)
        kappa = formatar_numero(par["kappa_ponderado"])
        eixos.set_title(
            f"{par['de']} → {par['para']}: {formatar_numero(par['prop_mudaram'] * 100)} % mudaram, "
            f"κ = {kappa}\n(n = {par['n_comparados']}; {par['n_excluidos']} sem classificação)",
            fontsize=9, color=COR_TEXTO)
    return figura


def figura_distribuicao(tabelas: dict[str, pd.DataFrame]) -> Figure:
    """Barras agrupadas: repositórios por categoria geral, uma cor por combinação."""
    distribuicao = tabelas["distribuicao_combinacoes"]
    nomes = list(tabelas["combinacoes"]["combinacao"])
    categorias = list(ORDEM_MATRIZ)
    figura = Figure(figsize=(7.5, 4.8), layout="constrained")
    FigureCanvasAgg(figura)
    eixos = figura.add_subplot()
    for lado in ("top", "right"):
        eixos.spines[lado].set_visible(False)
    eixos.yaxis.grid(True, color="#e4e3df", linewidth=0.8)
    eixos.set_axisbelow(True)
    largura = 0.8 / len(nomes)
    for k, nome in enumerate(nomes):
        contagens = [int(distribuicao[(distribuicao["combinacao"] == nome)
                                      & (distribuicao["categoria"] == c)]["n"].iloc[0]) for c in categorias]
        posicoes = np.arange(len(categorias)) + (k - (len(nomes) - 1) / 2) * largura
        barras = eixos.bar(posicoes, contagens, width=largura, label=nome,
                           color=CORES_COMBINACOES[k % len(CORES_COMBINACOES)])
        eixos.bar_label(barras, labels=[str(n) for n in contagens], padding=2, fontsize=8, color=COR_TEXTO)
    eixos.set_xticks(range(len(categorias)), [_rotulo(c) for c in categorias], color=COR_TEXTO_SECUNDARIO)
    eixos.yaxis.set_major_locator(MaxNLocator(integer=True))
    eixos.set_ylabel("Repositórios (nº)", color=COR_TEXTO)
    eixos.set_xlabel("Classificação DORA geral", color=COR_TEXTO)
    eixos.set_title(f"Categoria geral por combinação (n = {int(distribuicao['n'].sum() / len(nomes))} repositórios)",
                    fontsize=10, color=COR_TEXTO)
    eixos.legend(frameon=False, title="Combinação")
    return figura


def gerar_figuras(tabelas: dict[str, pd.DataFrame]) -> dict[str, Figure]:
    """Nome do arquivo PNG → figura."""
    return {"transicao_pares.png": figura_transicao(tabelas),
            "distribuicao_combinacoes.png": figura_distribuicao(tabelas)}


# --- gravação (disco) -------------------------------------------------------------------


def gravar(tabelas: dict[str, pd.DataFrame], figuras: dict[str, Figure], pasta: Path) -> None:
    """Grava os CSVs, o resumo.md e as figuras em `pasta` (criada se preciso)."""
    (pasta / PASTA_FIGURAS).mkdir(parents=True, exist_ok=True)
    for nome in TABELAS:
        gravar_csv(pasta / f"{nome}.csv", tabelas[nome])
    (pasta / ARQUIVO_RESUMO).write_text(gerar_resumo_md(tabelas), encoding="utf-8")
    for nome, figura in figuras.items():
        figura.savefig(pasta / PASTA_FIGURAS / nome, dpi=DPI, facecolor="white")


def executar(caminho_dataset: Path, combinacoes: tuple[Combinacao, ...],
             pasta_saida: Path) -> dict[str, pd.DataFrame]:
    """Lê, valida, calcula e grava; devolve as tabelas. Levanta `ErroDataset`."""
    validar_combinacoes(combinacoes)
    dados = validar(ler_dataset(caminho_dataset))
    tabelas = calcular(dados, combinacoes)
    gravar(tabelas, gerar_figuras(tabelas), pasta_saida)
    log.info("RQ 07: %d repositórios, %d combinações; saídas em %s",
             len(dados), len(combinacoes), pasta_saida)
    return tabelas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="analises.rq07_sensibilidade",
        description="Sensibilidade da classificação DORA à definição operacional (RQ 07)")
    parser.add_argument("--config", default="config.yaml", help="caminho do config.yaml")
    parser.add_argument("--dataset", help=f"CSV do dataset (padrão: <caminhos.saida>/{ARQUIVO_DATASET})")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        config = carregar_config(args.config)
        saida = Path(config.dir_saida)
        dataset = Path(args.dataset) if args.dataset else saida / ARQUIVO_DATASET
        executar(dataset, config.sensibilidade, saida / PASTA_SAIDA)
    except (ErroConfiguracao, ErroDataset) as e:
        log.error("%s", e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
