"""RQ06: fatores associados às métricas DORA, offline, com correção global de Holm."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import statsmodels
from scipy.stats import kruskal, mannwhitneyu
from statsmodels.stats.multitest import multipletests

FATORES = ("stars", "contributors", "idade_dias", "tipo_projeto")
METRICAS = {
    "frequencia_semana": "releases/semana",
    "lead_time_release_horas": "horas",
    "lead_time_commit_horas": "horas",
    "cfr_ci": "fração 0–1",
    "cfr_entrega": "fração 0–1",
    "recuperacao_mediana_horas": "horas",
}
TIPOS = ("aplicação/serviço", "biblioteca/framework", "ferramenta CLI", "outro")
ALFA = 0.05
MIN_POR_GRUPO = 5


def validar_dados(dados: pd.DataFrame) -> pd.DataFrame:
    """Valida domínios e devolve cópia ordenada; ausências permanecem ausências."""
    colunas = ("full_name", *FATORES, *METRICAS)
    faltantes = set(colunas) - set(dados.columns)
    if faltantes or dados.columns.duplicated().any():
        raise ValueError(f"Colunas ausentes ou repetidas: {sorted(faltantes)}")
    tabela = dados.loc[:, list(colunas)].copy()
    for coluna in colunas:
        tabela[coluna] = tabela[coluna].astype("string").str.strip().replace("", pd.NA)
    nomes = tabela["full_name"]
    if nomes.isna().any() or nomes.duplicated().any():
        raise ValueError("full_name deve ser preenchido e único")
    tipos = tabela["tipo_projeto"].dropna()
    if not tipos.isin(TIPOS).all():
        raise ValueError("tipo_projeto deve usar as categorias do consenso humano")
    for coluna in (*FATORES[:-1], *METRICAS):
        try:
            numeros = pd.to_numeric(tabela[coluna], errors="raise").astype(float)
        except (ValueError, TypeError) as erro:
            raise ValueError(f"{coluna}: valor não numérico") from erro
        invalidos = numeros.notna() & (~np.isfinite(numeros) | (numeros < 0))
        if coluna.startswith("cfr_"):
            invalidos |= numeros > 1
        if coluna in FATORES[:-1]:
            invalidos |= numeros.notna() & (numeros % 1 != 0)
        if invalidos.any():
            raise ValueError(f"{coluna}: valor fora do domínio")
        tabela[coluna] = numeros
    return tabela.sort_values("full_name").reset_index(drop=True)


def agrupar_fator(valores: pd.Series, numerico: bool) -> tuple[pd.Series, list[dict]]:
    """Agrupa por quartis sem separar empates ou por categoria; retorna limites."""
    grupos = pd.Series(pd.NA, index=valores.index, dtype="string")
    limites = []
    validos = valores.dropna()
    if validos.empty:
        return grupos, limites
    if not numerico:
        grupos.loc[validos.index] = validos.astype("string")
        for categoria in sorted(validos.unique()):
            limites.append({"grupo": categoria, "inferior": None, "superior": None,
                            "inclui_inferior": None, "n": int((validos == categoria).sum())})
        return grupos, limites
    if validos.nunique() == 1:
        grupos.loc[validos.index] = "G1"
        valor = float(validos.iloc[0])
        return grupos, [{"grupo": "G1", "inferior": valor, "superior": valor,
                          "inclui_inferior": True, "n": len(validos)}]
    codigos, cortes = pd.qcut(validos, q=4, labels=False, retbins=True, duplicates="drop")
    prefixo = "Q" if len(cortes) == 5 else "G"
    for indice in range(len(cortes) - 1):
        nome = f"{prefixo}{indice + 1}"
        selecionados = codigos.index[codigos == indice]
        grupos.loc[selecionados] = nome
        limites.append({"grupo": nome, "inferior": float(cortes[indice]),
                        "superior": float(cortes[indice + 1]), "inclui_inferior": indice == 0,
                        "n": len(selecionados)})
    return grupos, limites


def tamanho_cliff(delta: float) -> str:
    """Interpreta |δ| pelos limites do enunciado, sem unidade."""
    for limite, nome in [(0.147, "desprezível"), (0.33, "pequeno"), (0.474, "médio")]:
        if abs(delta) < limite:
            return nome
    return "grande"


def comparar_grupos(amostras: dict[str, list[float]]) -> dict:
    """Testa distribuições; ε² ou δ são adimensionais. Mínimo de 5 por grupo."""
    nomes = sorted(amostras)
    valores = [np.asarray(amostras[nome], dtype=float) for nome in nomes]
    if any(v.ndim != 1 or not np.isfinite(v).all() for v in valores):
        raise ValueError("Amostras devem ser vetores finitos")
    n = sum(len(v) for v in valores)
    resultado = {"n": n, "n_grupos": len(nomes), "grupos": " | ".join(nomes),
                 "teste": None, "estatistica": None, "p_bruto": None,
                 "efeito_nome": None, "efeito": None, "efeito_interpretacao": None,
                 "situacao": "grupos_insuficientes"}
    if len(nomes) < 2:
        return resultado
    if any(len(v) < MIN_POR_GRUPO for v in valores):
        return resultado | {"situacao": "grupo_menor_que_5"}
    if np.unique(np.concatenate(valores)).size == 1:
        return resultado | {"situacao": "variavel_constante"}
    if len(nomes) == 2:
        teste = mannwhitneyu(*valores, alternative="two-sided", method="asymptotic",
                            use_continuity=True)
        efeito = 2 * float(teste.statistic) / (len(valores[0]) * len(valores[1])) - 1
        detalhes = {"teste": "mann_whitney", "efeito_nome": "delta_cliff",
                    "efeito": efeito, "efeito_interpretacao": tamanho_cliff(efeito)}
    else:
        teste = kruskal(*valores)
        detalhes = {"teste": "kruskal_wallis", "efeito_nome": "epsilon_quadrado",
                    "efeito": float(teste.statistic) / (n - 1)}
    return resultado | detalhes | {"estatistica": float(teste.statistic),
                                  "p_bruto": float(teste.pvalue), "situacao": "calculado"}


def corrigir_holm(testes: pd.DataFrame) -> pd.DataFrame:
    """Corrige em uma única família todos os testes calculáveis, preservando a ordem."""
    resultado = testes.copy()
    resultado["p_holm"] = np.nan
    resultado["rejeita_holm"] = pd.Series(pd.NA, index=resultado.index, dtype="boolean")
    indices = resultado.index[resultado["situacao"] == "calculado"]
    if len(indices):
        rejeita, ajustados, _, _ = multipletests(resultado.loc[indices, "p_bruto"],
                                               alpha=ALFA, method="holm")
        resultado.loc[indices, "p_holm"] = ajustados
        resultado.loc[indices, "rejeita_holm"] = rejeita
    resultado["n_testes_familia"] = len(indices)
    return resultado


def analisar_dados(dados: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Produz tabelas por fator × métrica, sem rede nem disco e sem mutar a entrada."""
    tabela = validar_dados(dados)
    testes, descritivas, exclusoes, agrupamentos, limites = [], [], [], [], []
    for fator in FATORES:
        grupos, cortes = agrupar_fator(tabela[fator], numerico=fator != "tipo_projeto")
        limites.extend({"fator": fator, **corte} for corte in cortes)
        for indice, linha in tabela.iterrows():
            agrupamentos.append({"full_name": linha["full_name"], "fator": fator,
                                 "valor": linha[fator], "grupo": grupos.at[indice]})
        nomes = sorted(grupos.dropna().unique())
        for metrica, unidade in METRICAS.items():
            amostras = {}
            for grupo in nomes:
                valores = tabela.loc[grupos.eq(grupo).fillna(False), metrica]
                validos = valores.dropna()
                amostras[grupo] = validos.tolist()
                quantis = validos.quantile([.25, .5, .75])
                descritivas.append({"fator": fator, "metrica": metrica, "unidade": unidade,
                                    "grupo": grupo, "n_total_grupo": len(valores), "n": len(validos),
                                    "n_ausentes": int(valores.isna().sum()),
                                    "q1": quantis.loc[.25], "mediana": quantis.loc[.5],
                                    "q3": quantis.loc[.75], "iqr": quantis.loc[.75] - quantis.loc[.25]})
            resultado = comparar_grupos(amostras)
            testes.append({"fator": fator, "metrica": metrica, "unidade": unidade,
                           "n_total": len(tabela), "n_excluidos": len(tabela) - resultado["n"],
                           **resultado})
            for indice, linha in tabela.iterrows():
                motivos = []
                if pd.isna(grupos.at[indice]):
                    motivos.append("sem_fator")
                if pd.isna(linha[metrica]):
                    motivos.append("sem_metrica")
                if motivos:
                    exclusoes.append({"fator": fator, "metrica": metrica,
                                      "full_name": linha["full_name"], "motivo": ";".join(motivos)})
    return {"testes": corrigir_holm(pd.DataFrame(testes)),
            "descritivas": pd.DataFrame(descritivas, columns=["fator", "metrica", "unidade", "grupo",
                "n_total_grupo", "n", "n_ausentes", "q1", "mediana", "q3", "iqr"]),
            "exclusoes": pd.DataFrame(exclusoes, columns=["fator", "metrica", "full_name", "motivo"]),
            "agrupamentos": pd.DataFrame(agrupamentos, columns=["full_name", "fator", "valor", "grupo"]),
            "limites_grupos": pd.DataFrame(limites, columns=["fator", "grupo", "inferior", "superior", "inclui_inferior", "n"])}


def gerar_relatorio(tabelas: dict[str, pd.DataFrame], manifesto: dict) -> str:
    """Relatório reproduzível com testes, descritivas e limitações."""
    linhas = ["# RQ06 — Características associadas ao desempenho DORA", "",
              f"Entrada SHA-256: `{manifesto['entrada_sha256']}`. SciPy {scipy.__version__}; statsmodels {statsmodels.__version__}.", "",
              "Fatores: estrelas, contribuidores, idade e tipo de projeto. As seis variantes são analisadas, "
              "incluindo CFR (b) com interpretação provisória até a #34. "
              "Holm usa uma única família de todos os testes calculáveis; α = 0,05. "
              "O mínimo é de cinco observações válidas em cada grupo. "
              "Testes inviáveis ficam sem p-valor ou rejeição, com motivo explícito.", "",
              "| Fator | Métrica | n | Teste | Estatística | p bruto | p Holm | Efeito | Rejeita Holm | Situação |",
              "|---|---|---:|---|---:|---:|---:|---:|---|---|"]
    def numero(valor):
        return "indefinido" if pd.isna(valor) else f"{float(valor):.6g}"
    for linha in tabelas["testes"].to_dict("records"):
        rejeita = "indefinido" if pd.isna(linha["rejeita_holm"]) else ("sim" if linha["rejeita_holm"] else "não")
        linhas.append(f"| {linha['fator']} | {linha['metrica']} | {linha['n']} | {linha['teste'] or '—'} | "
                      f"{numero(linha['estatistica'])} | {numero(linha['p_bruto'])} | {numero(linha['p_holm'])} | "
                      f"{numero(linha['efeito'])} | {rejeita} | {linha['situacao']} |")
    linhas += ["", "## Medianas e IQR por grupo", "",
               "| Fator | Métrica | Grupo | n | Ausentes | Mediana | Q1 | Q3 | IQR | Unidade |",
               "|---|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for linha in tabelas["descritivas"].to_dict("records"):
        linhas.append(f"| {linha['fator']} | {linha['metrica']} | {linha['grupo']} | {linha['n']} | {linha['n_ausentes']} | "
                      f"{numero(linha['mediana'])} | {numero(linha['q1'])} | {numero(linha['q3'])} | {numero(linha['iqr'])} | {linha['unidade']} |")
    linhas += ["", "## Método e limites", "",
               "Quartis calculados uma vez por fator, antes de excluir métricas ausentes. "
               "Empates permanecem juntos; cortes repetidos são removidos (`qcut`, `duplicates='drop'`). "
               "Com quatro intervalos os nomes são Q1–Q4; com menos são G1–Gk. "
               "Intervalos são abertos à esquerda e fechados à direita, exceto o primeiro, que inclui o mínimo. "
               "`limites_grupos.csv` e `agrupamentos.csv` registram limites e membros. "
               "Tipo de projeto usa as categorias do consenso presentes no dataset; ausências não são imputadas. "
               "`exclusoes.csv` discrimina ausências por fator × métrica.", "",
               "Kruskal-Wallis compara três ou mais grupos e reporta ε² = H/(n−1); "
               "não identifica quais pares diferem. Não há testes post hoc nesta análise. "
               "Dois grupos usam Mann-Whitney bilateral, aproximação assintótica com correção de empates e continuidade, "
               "e δ = 2U₁/(n₁n₂)−1. A ordem dos grupos é lexicográfica, registrada em `testes.csv`; "
               "δ positivo indica valores maiores no primeiro grupo. "
               "Limites de |δ|: <0,147 desprezível; <0,33 pequeno; <0,474 médio; demais grande. "
               "Não se atribuem faixas arbitrárias ao ε².", "",
               "As métricas usam as unidades do dataset (horas, releases/semana e frações). "
               "Diferenças nas distribuições não demonstram causalidade nem que um grupo é superior em todas as métricas. "
               "Grupos pequenos, desbalanceamento, empates, ausências e seleção de projetos populares limitam a inferência. "
               "Não significância não demonstra equivalência. A validação da heurística de CFR (b) está pendente (#34); "
               "refinamentos exigem regenerar o dataset e repetir toda a família de testes.", "",
               "Fontes: [Kruskal-Wallis](https://docs.scipy.org/doc/scipy-1.14.1/reference/generated/scipy.stats.kruskal.html), "
               "[Mann-Whitney](https://docs.scipy.org/doc/scipy-1.14.1/reference/generated/scipy.stats.mannwhitneyu.html), "
               "[Holm](https://www.statsmodels.org/v0.14.4/generated/statsmodels.stats.multitest.multipletests.html).", ""]
    return "\n".join(linhas)


def executar(entrada: Path, saida: Path) -> dict[str, pd.DataFrame]:
    """Lê dataset, calcula análise e salva tabelas, manifesto e relatório."""
    nomes = ("testes", "descritivas", "exclusoes", "agrupamentos", "limites_grupos")
    destinos = [saida / f"{nome}.csv" for nome in nomes] + [saida / "manifesto.json", saida / "relatorio.md"]
    if entrada.resolve() in [p.resolve() for p in destinos]:
        raise ValueError("Entrada não pode ser arquivo de saída")
    bruto = entrada.read_bytes()
    texto = bruto.decode("utf-8-sig")
    cabecalho = next(csv.reader(io.StringIO(texto)), [])
    if len(cabecalho) != len(set(cabecalho)):
        raise ValueError("Colunas repetidas no CSV")
    dados = pd.read_csv(io.StringIO(texto), dtype="string", keep_default_na=False,
                        na_values=["", "NaN", "nan", "NA", "null", "None"])
    tabelas = analisar_dados(dados)
    manifesto = {"entrada_sha256": hashlib.sha256(bruto).hexdigest(),
                 "codigo_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 "scipy": scipy.__version__, "statsmodels": statsmodels.__version__,
                 "pandas": pd.__version__, "numpy": np.__version__,
                 "fatores": list(FATORES), "metricas": METRICAS, "alfa": ALFA,
                 "min_por_grupo": MIN_POR_GRUPO, "n_repositorios": len(dados),
                 "n_testes_familia": int((tabelas['testes']['situacao'] == 'calculado').sum()),
                 "cfr_entrega_validacao": "pendente_issue_34"}
    saida.mkdir(parents=True, exist_ok=True)
    for nome, tabela in tabelas.items():
        tabela.to_csv(saida / f"{nome}.csv", index=False, lineterminator="\n")
    (saida / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (saida / "relatorio.md").write_text(gerar_relatorio(tabelas, manifesto), encoding="utf-8")
    return tabelas


def main(argv: list[str] | None = None) -> int:
    """CLI offline: 0 = análise gerada; 1 = entrada inválida ou falha de execução."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=Path("output/metricas_repos.csv"))
    parser.add_argument("--saida", type=Path, default=Path("output/analises/rq06"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        executar(args.entrada, args.saida)
    except (ValueError, OSError, UnicodeError) as erro:
        logging.error("Não foi possível executar a RQ06: %s", erro)
        return 1
    logging.info("RQ06 gerada em %s", args.saida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
