"""RQ05: frequência (releases/semana) × CFR (fração), sem acesso à rede."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.stats import spearmanr

LOGGER = logging.getLogger(__name__)
VARIANTES = ("cfr_ci", "cfr_entrega")
COLUNAS_PADRAO = ("full_name", "deployment_frequency", *VARIANTES)
MIN_PARES = 3


def analisar_dados(
    dados: pd.DataFrame, colunas: tuple[str, str, str, str] = COLUNAS_PADRAO
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Retorna resumo, pares usados e exclusões por variante; não altera a entrada.

    Frequência em releases/semana e CFR em fração 0–1. Células vazias/NaN
    são ausências; números inválidos, infinitos e fora do domínio são erros.
    """
    if len(colunas) != 4 or len(set(colunas)) != 4:
        raise ValueError("Informe quatro colunas distintas: repositório, frequência, CFR (a), CFR (b).")
    faltantes = set(colunas) - set(dados.columns)
    if faltantes:
        raise ValueError(f"Colunas ausentes: {', '.join(sorted(faltantes))}.")
    tabela = dados.loc[:, list(colunas)].copy()
    tabela.columns = COLUNAS_PADRAO
    nomes = tabela["full_name"].astype("string").str.strip()
    if nomes.isna().any() or nomes.eq("").any() or nomes.duplicated().any():
        raise ValueError("Cada repositório deve ter um identificador preenchido e único.")
    tabela["full_name"] = nomes
    for coluna in COLUNAS_PADRAO[1:]:
        serie = tabela[coluna].astype("string").str.strip().replace("", pd.NA)
        try:
            numeros = pd.to_numeric(serie, errors="raise").astype(float)
        except (ValueError, TypeError) as erro:
            raise ValueError(f"Coluna {coluna}: valor não numérico.") from erro
        invalidos = numeros.notna() & (~np.isfinite(numeros) | (numeros < 0))
        if coluna in VARIANTES:
            invalidos |= numeros > 1
        if invalidos.any():
            repos = tabela.loc[invalidos, "full_name"].tolist()
            raise ValueError(f"Coluna {coluna}: valor fora do domínio em {repos}.")
        tabela[coluna] = numeros
    tabela = tabela.sort_values("full_name").reset_index(drop=True)
    resumos, pares, exclusoes = [], [], []
    for variante in VARIANTES:
        falta_frequencia = tabela["deployment_frequency"].isna()
        falta_cfr = tabela[variante].isna()
        usados = tabela.loc[~(falta_frequencia | falta_cfr)]
        x, y = usados["deployment_frequency"], usados[variante]
        n = len(usados)
        rho = p_valor = None
        if n < MIN_PARES:
            situacao = "pares_insuficientes"
        elif x.nunique() < 2 or y.nunique() < 2:
            situacao = "variavel_constante"
        else:
            resultado = spearmanr(x, y, alternative="two-sided", nan_policy="raise")
            rho, p_valor = float(resultado.statistic), float(resultado.pvalue)
            situacao = "calculado"
        resumos.append({
            "variante": variante, "n_total": len(tabela), "n": n,
            "n_excluidos": len(tabela) - n,
            "n_sem_frequencia": int(falta_frequencia.sum()),
            "n_sem_cfr": int(falta_cfr.sum()),
            "rho": rho, "p_valor": p_valor, "situacao": situacao,
        })
        for linha in usados.to_dict("records"):
            pares.append({"variante": variante, "full_name": linha["full_name"],
                          "deployment_frequency": linha["deployment_frequency"],
                          "cfr": linha[variante]})
        for i in tabela.index[falta_frequencia | falta_cfr]:
            motivos = []
            if falta_frequencia[i]:
                motivos.append("sem_frequencia")
            if falta_cfr[i]:
                motivos.append("sem_cfr")
            exclusoes.append({"variante": variante, "full_name": tabela.at[i, "full_name"],
                              "motivo": ";".join(motivos)})
    return (
        pd.DataFrame(resumos),
        pd.DataFrame(pares, columns=["variante", "full_name", "deployment_frequency", "cfr"]),
        pd.DataFrame(exclusoes, columns=["variante", "full_name", "motivo"]),
    )


def gerar_grafico(pares: pd.DataFrame, resumo: dict, destino: Path, escala: str) -> None:
    """Salva dispersão PNG; symlog preserva zero, log exige frequências positivas."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import PercentFormatter

    figura = Figure(figsize=(7, 4.5), layout="constrained")
    FigureCanvasAgg(figura)
    eixo = figura.subplots()
    eixo.scatter(pares["deployment_frequency"], pares["cfr"], alpha=0.65, s=25,
                 label=f"Repositórios (n={len(pares)})")
    if escala == "symlog":
        eixo.set_xscale("symlog", linthresh=1)
    else:
        eixo.set_xscale(escala)
    eixo.set(xlabel="Frequência de deploy (releases/semana)", ylabel="CFR",
             title=f"RQ05 — {resumo['variante']}", ylim=(-0.03, 1.03))
    eixo.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    if resumo["situacao"] == "calculado":
        anotacao = f"ρ = {resumo['rho']:.4f}; p = {resumo['p_valor']:.4g}"
    else:
        anotacao = resumo["situacao"].replace("_", " ")
    eixo.text(0.02, 0.97, anotacao, transform=eixo.transAxes, va="top")
    eixo.grid(alpha=0.2)
    eixo.legend(loc="lower right")
    figura.savefig(destino, dpi=180, metadata={"Software": "analises.rq05"})


def gerar_relatorio(resumo: pd.DataFrame, sha256: str, colunas: tuple, escala: str) -> str:
    """Produz tabela e discussão descritiva sem inferir causalidade ou validar CFR."""
    linhas = [
        "# RQ05 — Frequência de deploy × taxa de falha", "",
        f"SHA-256 do CSV de entrada: `{sha256}`.", "",
        f"Colunas (repositório, frequência, CFR a, CFR b): `{', '.join(colunas)}`.",
        f"SciPy: {scipy.__version__}. Teste bilateral `scipy.stats.spearmanr`.", "",
        "| Variante | n total | n usado | Excluídos | ρ | p-valor | Situação |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for linha in resumo.to_dict("records"):
        definido = linha["situacao"] == "calculado"
        rho = f"{linha['rho']:.6g}" if definido else "indefinido"
        p_valor = f"{linha['p_valor']:.6g}" if definido else "indefinido"
        linhas.append(f"| {linha['variante']} | {linha['n_total']} | {linha['n']} | "
                      f"{linha['n_excluidos']} | {rho} | {p_valor} | {linha['situacao']} |")
    linhas += ["", "## Leitura dos resultados", ""]
    for linha in resumo.to_dict("records"):
        if linha["situacao"] != "calculado":
            linhas += [f"Para `{linha['variante']}`, a correlação permanece indefinida "
                       f"({linha['situacao']}; n={linha['n']}).", ""]
            continue
        if linha["rho"] == 0:
            leitura = "não houve associação monotônica observada (ρ = 0)"
        elif linha["rho"] > 0:
            leitura = "maior frequência acompanhou maior CFR (associação positiva)"
        else:
            leitura = "maior frequência acompanhou menor CFR (associação negativa)"
        linhas += [f"Para `{linha['variante']}`, {leitura}: ρ={linha['rho']:.6g}, "
                   f"p={linha['p_valor']:.6g}, n={linha['n']}.", ""]
    linhas += [
        "A hipótese prévia espera associação fraca, possivelmente distinta entre os proxies. "
        "Compare a magnitude e o sinal dos dois coeficientes com essa hipótese; "
        "o p-valor isolado não mede força de associação. Amostras diferentes por ausência "
        "de dados também podem contribuir para diferenças entre os coeficientes.", "",
        "ρ positivo indica que maior frequência acompanha maior CFR; ρ negativo indica "
        "que maior frequência acompanha menor CFR. Um coeficiente próximo de zero "
        "indica pouca associação monotônica observada, sem demonstrar ausência de "
        "relações não monotônicas. Nenhum desses resultados estabelece causalidade.", "",
        "O CFR (a) mede falhas de CI; o CFR (b) usa releases corretivas como proxy de "
        "falhas de entrega. Versionamento e cadência de correções podem afetar o segundo. "
        "A interpretação de CFR (b) deve considerar a validação da versão usada no dataset "
        "(#34; veja `output/validacao_heuristica/relatorio.md` e a metodologia do artigo). "
        "Esses proxies não comprovam, por si só, a afirmação DORA sobre produção.", "",
        "## Exclusões e limites", "",
        "Os pares completos são selecionados separadamente por variante, sem imputação. "
        "`exclusoes.csv` lista cada repositório e motivo; `pares.csv` preserva os pontos "
        "usados em cada teste e gráfico. No resumo, as contagens sem frequência e sem CFR "
        "podem se sobrepor. n < 3 ou variável constante deixa ρ e p indefinidos.", "",
        "Os p-valores são os aproximados retornados por `spearmanr`, sem ajuste entre "
        "as duas variantes. A documentação do SciPy ressalta maior precisão em amostras "
        "acima de 500 observações; amostras menores exigem cautela na inferência. "
        "A seleção de projetos populares e o uso de proxies limitam a generalização.", "",
        f"Escala horizontal dos gráficos: `{escala}`. "
        "Na escala symlog, a região entre 0 e 1 release/semana é linear e os valores "
        "maiores são logarítmicos; zeros são preservados. Na escala log, zero é recusado. "
        "A escala é apenas visual e não transforma os valores usados em Spearman.", "",
        "Fonte: [SciPy — spearmanr]"
        "(https://docs.scipy.org/doc/scipy-1.14.1/reference/generated/scipy.stats.spearmanr.html).",
        "", "![CFR de CI](dispersao_cfr_ci.png)", "",
        "![CFR de entrega](dispersao_cfr_entrega.png)", "",
    ]
    return "\n".join(linhas)


def executar(entrada: Path, saida: Path, colunas: tuple = COLUNAS_PADRAO,
             escala: str = "symlog") -> pd.DataFrame:
    """Lê CSV UTF-8 e grava resultados da RQ05; entrada permanece intacta."""
    if escala not in {"linear", "log", "symlog"}:
        raise ValueError("Escala deve ser linear, log ou symlog.")
    conteudo = entrada.read_bytes()
    texto = conteudo.decode("utf-8-sig")
    cabecalho = next(csv.reader(io.StringIO(texto)), [])
    if len(cabecalho) != len(set(cabecalho)):
        raise ValueError("O CSV contém nomes de colunas repetidos.")
    dados = pd.read_csv(io.StringIO(texto), dtype="string", keep_default_na=False,
                        na_values=["", "NaN", "nan", "NA", "null", "None"])
    resumo, pares, exclusoes = analisar_dados(dados, colunas)
    if escala == "log" and (pares["deployment_frequency"] <= 0).any():
        raise ValueError("Escala log exige frequência positiva; use symlog para preservar zeros.")
    arquivos = ["correlacoes.csv", "pares.csv", "exclusoes.csv", "relatorio.md",
                *(f"dispersao_{v}.png" for v in VARIANTES)]
    if entrada.resolve() in [(saida / nome).resolve() for nome in arquivos]:
        raise ValueError("A entrada não pode ser um dos arquivos de saída.")
    saida.mkdir(parents=True, exist_ok=True)
    for nome, tabela in (("correlacoes", resumo), ("pares", pares), ("exclusoes", exclusoes)):
        tabela.to_csv(saida / f"{nome}.csv", index=False, lineterminator="\n")
    for linha in resumo.to_dict("records"):
        variante = linha["variante"]
        gerar_grafico(pares.loc[pares["variante"] == variante], linha,
                      saida / f"dispersao_{variante}.png", escala)
    (saida / "relatorio.md").write_text(
        gerar_relatorio(resumo, hashlib.sha256(conteudo).hexdigest(), colunas, escala),
        encoding="utf-8",
    )
    return resumo


def main(argv: list[str] | None = None) -> int:
    """CLI offline; saída 0 = análise gerada, 1 = entrada/execução inválida."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, required=True, help="CSV final da #35 (UTF-8, vírgula).")
    parser.add_argument("--saida", type=Path, default=Path("output/rq05"))
    parser.add_argument("--coluna-repo", default=COLUNAS_PADRAO[0])
    parser.add_argument("--coluna-frequencia", default=COLUNAS_PADRAO[1])
    parser.add_argument("--coluna-cfr-ci", default=COLUNAS_PADRAO[2])
    parser.add_argument("--coluna-cfr-entrega", default=COLUNAS_PADRAO[3])
    parser.add_argument("--escala-x", choices=["linear", "log", "symlog"], default="symlog")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        executar(args.entrada, args.saida,
                 (args.coluna_repo, args.coluna_frequencia, args.coluna_cfr_ci,
                  args.coluna_cfr_entrega), args.escala_x)
    except (OSError, ValueError, UnicodeError) as erro:
        LOGGER.error("Não foi possível executar a RQ05: %s", erro)
        return 1
    LOGGER.info("RQ05 gerada em %s. Consulte correlacoes.csv e relatorio.md.", args.saida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
