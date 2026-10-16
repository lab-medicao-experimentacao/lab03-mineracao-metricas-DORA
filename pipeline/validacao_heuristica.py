"""Avaliação offline e histórico de versões da heurística corretiva."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import sklearn

from metricas import cfr, validacao
from metricas.concordancia import consenso, normalizar_rotulo
from metricas.frequencia import releases_publicadas
from pipeline.amostra_ouro import AVALIADORES, PASTA_AMOSTRA_OURO, gravar_csv
from pipeline.config import Config, ErroConfiguracao, carregar_config
from pipeline.consenso import (
    ARQUIVO_CONSENSO_RELEASES,
    ARQUIVO_CONSENSO_REPOS,
    PLANILHAS,
    ler_rotulos,
    ler_sorteio,
)

log = logging.getLogger("pipeline.validacao_heuristica")
PASTA_VALIDACAO = "validacao_heuristica"
COLUNAS_COMPARACAO = ("full_name", "tag_name", "corretiva_consenso", "corretiva_prevista",
                      "acertou", "sem_commits")
COLUNAS_HISTORICO = ("versao", "descricao", "n_itens", "n_corretivas_reais",
                     "n_corretivas_previstas", "vp", "fp", "fn", "vn", "precisao",
                     "recall", "f1", "situacao", "n_sem_commits", "dados_sha256", "codigo_sha256")


class ErroValidacao(ValueError):
    """Entrada incompleta, inválida ou tentativa de sobrescrever uma versão."""


def _tabela(caminho: Path, colunas: tuple[str, ...], permitir_vazia: bool = False) -> list[dict]:
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as erro:
        raise ErroValidacao(f"não foi possível ler {caminho}: {erro}") from erro
    cabecalho = texto.splitlines()[0] if texto else ""
    separador = ";" if cabecalho.count(";") > cabecalho.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto, newline=""), delimiter=separador)
    campos = leitor.fieldnames or []
    if len(set(campos)) != len(campos) or not set(colunas) <= set(campos):
        raise ErroValidacao(f"{caminho.name}: cabeçalho inválido; esperado: {', '.join(colunas)}")
    linhas = list(leitor)
    if not linhas and not permitir_vazia:
        raise ErroValidacao(f"{caminho.name}: arquivo sem itens")
    if any(None in linha or any(v is None for v in linha.values()) for linha in linhas):
        raise ErroValidacao(f"{caminho.name}: linha com quantidade incorreta de campos")
    return linhas


def _chave(linha: dict, tipo: str) -> tuple[str, str]:
    return linha["full_name"], linha["tag_name"] if tipo == "releases" else ""


def _consenso_completo(pasta: Path) -> list[dict]:
    # Verifica a existência dos consensos antes de abrir qualquer planilha individual.
    for nome in (ARQUIVO_CONSENSO_REPOS, ARQUIVO_CONSENSO_RELEASES):
        if not (pasta / nome).is_file():
            raise ErroValidacao("consenso ausente: conclua a rotulagem independente e gere o consenso")
    problemas: list[str] = []
    resultado = []
    for planilha in PLANILHAS:
        itens = ler_sorteio(pasta, planilha, problemas)
        votos = {a: ler_rotulos(pasta, planilha, a, itens, problemas) for a in AVALIADORES}
        if problemas:
            # Não expõe rótulos dos outros avaliadores em mensagens de erro.
            raise ErroValidacao("sorteio ou rotulagem incompleta/inválida; corrija e gere o consenso novamente")
        linhas = _tabela(pasta / planilha.arquivo_consenso, planilha.colunas_consenso)
        chaves = [_chave(linha, planilha.tipo) for linha in linhas]
        if len(set(chaves)) != len(chaves) or set(chaves) != set(itens):
            raise ErroValidacao(f"{planilha.arquivo_consenso}: itens diferentes do sorteio ou duplicados")
        for linha, chave in zip(linhas, chaves):
            for dimensao, valores in planilha.dimensoes.items():
                canonicos = {normalizar_rotulo(v): v for v in valores}
                rotulo = canonicos.get(normalizar_rotulo(linha[dimensao]))
                origem = linha[f"origem_{dimensao}"].strip()
                esperado, origem_esperada = consenso(tuple(votos[a][chave][dimensao] for a in AVALIADORES))
                if (rotulo not in valores or origem not in {"unanime", "maioria", "reuniao"}
                        or (esperado is not None and (rotulo != esperado or origem != origem_esperada))
                        or (esperado is None and origem != "reuniao")):
                    raise ErroValidacao(f"{planilha.arquivo_consenso}: consenso pendente ou desatualizado")
                linha[dimensao] = rotulo
        if planilha.tipo == "releases":
            resultado = linhas
    return resultado


def _data(valor: str) -> datetime | None:
    if not valor:
        return None
    data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if data.tzinfo is None:
        raise ValueError("data sem fuso horário")
    return data.astimezone(timezone.utc)


def _booleano(valor: str) -> bool:
    if valor.lower() not in {"true", "false"}:
        raise ValueError("booleano deve ser True ou False")
    return valor.lower() == "true"


def _entradas(config: Config, rotulos: list[dict]) -> tuple[dict, dict]:
    repos = {r["full_name"] for r in rotulos}
    releases = {nome: [] for nome in repos}
    commits = {nome: {} for nome in repos}
    colunas = ("full_name", "tag_name", "published_at", "draft", "prerelease")
    for linha in _tabela(config.dir_processados / "releases.csv", colunas):
        if linha["full_name"] not in repos:
            continue
        try:
            registro = {"tag_name": linha["tag_name"], "published_at": _data(linha["published_at"]),
                        "draft": _booleano(linha["draft"]), "prerelease": _booleano(linha["prerelease"])}
        except ValueError as erro:
            raise ErroValidacao(f"releases.csv: data ou booleano inválido ({erro})") from erro
        releases[linha["full_name"]].append(registro)
    for nome, historico in releases.items():
        tags = [r["tag_name"] for r in historico]
        if len(set(tags)) != len(tags):
            raise ErroValidacao(f"releases.csv: tag repetida em {nome}")
        historico.sort(key=lambda r: (r["published_at"] is None,
                                      r["published_at"] or config.janela.fim, r["tag_name"]))
    colunas = ("full_name", "tag_name", "sha", "author_date", "message")
    for linha in _tabela(config.dir_processados / "commits.csv", colunas, permitir_vazia=True):
        if linha["full_name"] in repos:
            commits[linha["full_name"]].setdefault(linha["tag_name"], []).append(
                {"sha": linha["sha"], "message": linha["message"]})
    for linha in rotulos:
        nome, tag = linha["full_name"], linha["tag_name"]
        elegiveis = releases_publicadas(releases[nome], config.janela.inicio, config.janela.fim)
        if tag not in {r["tag_name"] for r in elegiveis}:
            raise ErroValidacao(f"release do consenso ausente ou fora da janela: {nome} / {tag}")
    return releases, commits


def _hash_json(valor: object) -> str:
    return hashlib.sha256(json.dumps(valor, sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


def _relatorio(historico: list[dict]) -> str:
    """Texto com todas as versões avaliadas, pronto para apoiar a escrita do artigo."""
    linhas = [
        "# Validação da identificação automática de releases corretivas", "",
        "A referência é o consenso humano; a classe positiva é a release corretiva. "
        "Precisão, recall e F1 são frações de 0 a 1. Denominadores nulos são registrados como 0.", "",
        "| Versão | Descrição | Releases | Precisão | Recall | F1 | Meta de F1 | Situação |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    situacoes = {"atingiu_meta": "Meta atingida", "refinar": "Refinamento necessário",
                 "sem_positivos": "Consenso sem corretivas; detecção não validada"}
    for registro in historico:
        descricao = " ".join(registro["descricao"].split()).replace("|", r"\|")
        linhas.append(
            f"| {registro['versao']} | {descricao} | {registro['n_itens']} | "
            f"{registro['precisao']:.4f} | {registro['recall']:.4f} | {registro['f1']:.4f} | "
            f"{registro['f1_minimo']:.2f} | {situacoes[registro['situacao']]} |")
    linhas += ["", "Os valores da tabela são arredondados apenas para apresentação. "
               "A situação usa o F1 sem arredondamento, preservado nos arquivos de resultado.", ""]
    for registro in historico:
        versao = registro["versao"]
        unidade_repo = "repositório" if registro["n_repositorios"] == 1 else "repositórios"
        linhas += [
            f"## {versao}", "",
            f"Foram avaliadas {registro['n_itens']} releases de {registro['n_repositorios']} {unidade_repo}. "
            f"O consenso identificou {registro['n_corretivas_reais']} corretivas, e a heurística "
            f"previu {registro['n_corretivas_previstas']}. Foram {registro['vp']} verdadeiros positivos, "
            f"{registro['fp']} falsos positivos, {registro['fn']} falsos negativos e "
            f"{registro['vn']} verdadeiros negativos.", "",
            f"Há {registro['n_sem_commits']} releases sem commits disponíveis na entrada. "
            "Elas foram mantidas na comparação. Essa contagem não distingue comparações vazias "
            "de comparações indisponíveis.", "",
            f"Janela: `{registro['janela_inicio']}` até `{registro['janela_fim_exclusivo']}` "
            "(limite final exclusivo).", "",
            f"Dados: `{registro['dados_sha256']}`. Código: `{registro['codigo_sha256']}`. "
            f"scikit-learn: `{registro['scikit_learn']}`.", "",
            f"[Resultado completo](./{versao}/resultado.json), "
            f"[comparação por release](./{versao}/comparacao.csv) e "
            f"[código avaliado](./{versao}/codigo.json).", "",
        ]
    linhas += [
        "## Interpretação e limitações", "",
        "Um F1 abaixo da meta exige examinar os erros, refinar a heurística e registrar uma nova "
        "avaliação. As tentativas anteriores devem ser relatadas, inclusive as que não atingiram a meta. "
        "Sem corretivas no consenso, não há evidência para validar a detecção dessa classe.", "",
        "O refinamento e a reavaliação na mesma amostra podem produzir resultados otimistas para "
        "outros projetos. Releases de monorepos podem pertencer a pacotes diferentes, o que limita "
        "a interpretação da antecessora cronológica. Os resultados avaliam uma aproximação de "
        "release corretiva, sem comprovar incidentes em produção.", "",
    ]
    if len({r["dados_sha256"] for r in historico}) > 1:
        linhas += [
            "**As versões usaram entradas diferentes.** Uma variação de F1 pode ser causada "
            "pela mudança dos dados e não apenas pelo refinamento. Compare diretamente versões "
            "com o mesmo identificador de dados.", "",
        ]
    return "\n".join(linhas)


def _salvar(pasta: Path, registro: dict, comparacao: list[dict], codigo: dict) -> None:
    destino = pasta / registro["versao"]
    texto = json.dumps(registro, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    historico = []
    for caminho in sorted(pasta.glob("*/resultado.json")):
        try:
            antigo = json.loads(caminho.read_text(encoding="utf-8"))
            obrigatorios = {*COLUNAS_HISTORICO, "f1_minimo", "n_repositorios", "janela_inicio",
                            "janela_fim_exclusivo", "scikit_learn"}
            if not isinstance(antigo, dict) or not obrigatorios <= set(antigo):
                raise ValueError("campos ausentes")
        except (OSError, ValueError) as erro:
            raise ErroValidacao(f"histórico inválido: {caminho}") from erro
        if caminho.parent == destino:
            if antigo != registro:
                raise ErroValidacao("versão já registrada com dados, código ou descrição diferentes; use nova versão")
        else:
            historico.append(antigo)
    if destino.exists():
        if not (destino / "resultado.json").is_file():
            raise ErroValidacao("pasta de versão já existe sem resultado válido")
        anteriores = _tabela(destino / "comparacao.csv", COLUNAS_COMPARACAO)
        esperados = [{chave: str(valor) for chave, valor in linha.items()} for linha in comparacao]
        if anteriores != esperados:
            raise ErroValidacao("comparação da versão registrada foi alterada; resultados preservados")
        try:
            codigo_anterior = json.loads((destino / "codigo.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as erro:
            raise ErroValidacao("código da versão registrada ausente ou inválido") from erro
        if codigo_anterior != codigo:
            raise ErroValidacao("código da versão registrada foi alterado; resultados preservados")
    else:
        pasta.mkdir(parents=True, exist_ok=True)
        # Publica os dois arquivos da versão juntos; interrupção não deixa versão parcial.
        with tempfile.TemporaryDirectory(dir=pasta, prefix=".avaliacao-") as temporaria:
            versao = Path(temporaria) / "versao"
            versao.mkdir()
            (versao / "resultado.json").write_text(texto, encoding="utf-8")
            (versao / "codigo.json").write_text(
                json.dumps(codigo, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            gravar_csv(versao / "comparacao.csv", COLUNAS_COMPARACAO, comparacao)
            versao.rename(destino)
    historico.append(registro)
    historico.sort(key=lambda r: r["versao"])
    linhas = [{coluna: r[coluna] for coluna in COLUNAS_HISTORICO} for r in historico]
    with tempfile.TemporaryDirectory(dir=pasta, prefix=".historico-") as temporaria:
        caminho = Path(temporaria) / "historico.csv"
        gravar_csv(caminho, COLUNAS_HISTORICO, linhas)
        relatorio = Path(temporaria) / "relatorio.md"
        relatorio.write_text(_relatorio(historico), encoding="utf-8")
        caminho.replace(pasta / "historico.csv")
        relatorio.replace(pasta / "relatorio.md")


def gerar_avaliacao(config: Config, versao: str, descricao: str) -> dict:
    """Valida entradas locais, avalia a heurística e preserva os resultados por versão."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", versao) or not descricao.strip():
        raise ErroValidacao("informe versão (letras, números, _ ou -, até 64 caracteres) e descrição não vazia")
    pasta = config.dir_saida / PASTA_AMOSTRA_OURO
    rotulos = _consenso_completo(pasta)
    releases, commits = _entradas(config, rotulos)
    previsoes = {}
    for nome, historico in releases.items():
        anterior = None
        for release in historico:
            if (release["draft"] or release["prerelease"] or release["published_at"] is None
                    or release["published_at"] >= config.janela.fim):
                continue
            tag = release["tag_name"]
            if release["published_at"] >= config.janela.inicio:
                previsoes[(nome, tag)] = cfr.release_corretiva(release, anterior, commits[nome].get(tag, []))
            anterior = release
    comparacao = []
    reais, previstos = [], []
    for linha in rotulos:
        nome, tag = linha["full_name"], linha["tag_name"]
        real, previsto = linha["corretiva"] == "sim", previsoes[(nome, tag)]
        reais.append(real)
        previstos.append(previsto)
        comparacao.append({"full_name": nome, "tag_name": tag,
                           "corretiva_consenso": "sim" if real else "não",
                           "corretiva_prevista": "sim" if previsto else "não",
                           "acertou": real == previsto, "sem_commits": not commits[nome].get(tag)})
    codigo = {"cfr": Path(cfr.__file__).read_text(encoding="utf-8"),
              "validacao": Path(validacao.__file__).read_text(encoding="utf-8"),
              "pipeline": Path(__file__).read_text(encoding="utf-8")}
    dados = {"releases": releases, "commits": commits, "rotulos": rotulos,
             "inicio": config.janela.inicio, "fim": config.janela.fim}
    registro = {"versao": versao, "descricao": descricao.strip(),
                **validacao.avaliar_classificacao(reais, previstos),
                "n_sem_commits": sum(linha["sem_commits"] for linha in comparacao),
                "dados_sha256": _hash_json(dados), "codigo_sha256": _hash_json(codigo),
                "scikit_learn": sklearn.__version__, "f1_minimo": validacao.F1_MINIMO,
                "n_repositorios": len({r["full_name"] for r in rotulos}),
                "janela_inicio": config.janela.inicio.isoformat(),
                "janela_fim_exclusivo": config.janela.fim.isoformat()}
    _salvar(config.dir_saida / PASTA_VALIDACAO, registro, comparacao, codigo)
    return registro


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avaliação offline da heurística frente ao consenso humano")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--versao", required=True, help="identificador único da versão avaliada")
    parser.add_argument("--descricao", required=True, help="descrição da versão ou do refinamento")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        config = carregar_config(args.config)
    except ErroConfiguracao as erro:
        log.error("%s", erro)
        return 2
    try:
        resultado = gerar_avaliacao(config, args.versao, args.descricao)
    except (ErroValidacao, OSError) as erro:
        log.error("%s", erro)
        return 1
    log.info("versão %s: precisão=%.4f, recall=%.4f, F1=%.4f (%s)", args.versao,
             resultado["precisao"], resultado["recall"], resultado["f1"], resultado["situacao"])
    if resultado["situacao"] == "sem_positivos":
        log.warning("consenso sem corretivas: não foi possível validar a detecção da classe positiva")
        return 4
    if resultado["situacao"] == "refinar":
        log.warning("F1 abaixo de %.2f: refine a heurística e reavalie com nova versão", validacao.F1_MINIMO)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
