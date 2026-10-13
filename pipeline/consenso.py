"""Amostra-ouro (#33): concordância entre avaliadores, divergências, desempates e consenso.

Seção 6 do enunciado, passos 3 e 4. Uso: ``python -m pipeline.consenso --config config.yaml``.
Não acessa a rede: lê e grava só em ``<caminhos.saida>/amostra_ouro/``.

Entrada: ``sorteio_repos.csv``, ``sorteio_releases.csv`` (de ``python -m pipeline.amostra_ouro``)
e as seis planilhas ``rotulos_<A|B|C>_<repos|releases>.csv`` preenchidas. Item = ``full_name``
(repos) ou ``(full_name, tag_name)`` (releases). Planilhas salvas pelo Excel pt-BR com ``;`` são
aceitas (o separador é detectado pelo cabeçalho), com ou sem BOM; precisam estar em UTF-8.
Rótulos são comparados após ``normalizar_rotulo`` (espaços nas pontas, maiúsculas) e gravados
no valor canônico de ``VALORES_ROTULOS_*``; ``observacoes`` é ignorada. Qualquer problema
(arquivo ausente, item faltando/sobrando/repetido, rótulo vazio ou inválido, ``rotulo_final``
inválido em ``desempates.csv``) aborta **sem gravar nada**, listando todos de uma vez.

Saídas (mesma codificação das planilhas; linhas na ordem do sorteio):

- ``concordancia.csv``: por dimensão, concordância observada e kappa de Fleiss (4 casas; kappa
  vazio quando indefinido) com a interpretação de Landis & Koch;
- ``divergencias.csv``: itens sem unanimidade (``2x1`` ou ``1-1-1``);
- ``desempates.csv``: casos ``1-1-1``, a decidir em reunião preenchendo ``rotulo_final`` e
  ``justificativa``. Regerar preserva o que foi preenchido; uma decisão cujo caso deixou de ser
  ``1-1-1`` é mantida no arquivo (decisão humana nunca é apagada), com aviso no log, mas não é
  aplicada ao consenso;
- ``consenso_repos.csv`` e ``consenso_releases.csv``: rótulo de consenso e origem
  (``unanime``, ``maioria``, ``reuniao`` = desempate decidido, ``pendente`` = rótulo vazio).

Mesma entrada → arquivos byte a byte idênticos.

Códigos de saída: 0 = arquivos gerados e consenso completo; 1 = erro de validação das planilhas
ou de ``desempates.csv`` (nada é gravado); 2 = configuração inválida; 3 = arquivos gerados, mas
há casos ``1-1-1`` sem decisão em ``desempates.csv``.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from metricas.concordancia import (
    DIVERGENCIA_1_1_1,
    ORIGEM_PENDENTE,
    concordancia_observada,
    consenso,
    interpretar_kappa,
    kappa_fleiss,
    normalizar_rotulo,
    tipo_divergencia,
)
from pipeline.amostra_ouro import (
    ARQUIVO_SORTEIO_RELEASES,
    ARQUIVO_SORTEIO_REPOS,
    AVALIADORES,
    CODIFICACAO_PLANILHAS,
    PASTA_AMOSTRA_OURO,
    VALORES_ROTULOS_RELEASES,
    VALORES_ROTULOS_REPOS,
    arquivo_rotulos,
    gravar_csv,
)
from pipeline.config import ErroConfiguracao, carregar_config

log = logging.getLogger("pipeline.consenso")  # não "__main__" ao rodar com -m

ARQUIVO_CONCORDANCIA = "concordancia.csv"
ARQUIVO_DIVERGENCIAS = "divergencias.csv"
ARQUIVO_DESEMPATES = "desempates.csv"
ARQUIVO_CONSENSO_REPOS = "consenso_repos.csv"
ARQUIVO_CONSENSO_RELEASES = "consenso_releases.csv"

ORIGEM_REUNIAO = "reuniao"  # caso 1-1-1 decidido em desempates.csv
CASAS_DECIMAIS = 4

COLUNAS_ROTULOS_AVALIADORES = tuple(f"rotulo_{a}" for a in AVALIADORES)
COLUNAS_CHAVE_CASO = ("dimensao", "full_name", "tag_name")
COLUNAS_CONCORDANCIA = (
    "dimensao", "n_itens", "n_avaliadores", "concordancia_observada", "kappa_fleiss", "interpretacao",
)
COLUNAS_DIVERGENCIAS = (*COLUNAS_CHAVE_CASO, *COLUNAS_ROTULOS_AVALIADORES, "tipo")
COLUNAS_DECISAO = ("rotulo_final", "justificativa")
COLUNAS_DESEMPATES = (*COLUNAS_CHAVE_CASO, *COLUNAS_ROTULOS_AVALIADORES, *COLUNAS_DECISAO)

Chave = tuple[str, str]  # (full_name, tag_name); tag_name vazio nos repositórios
ChaveCaso = tuple[str, str, str]  # (dimensao, full_name, tag_name)


@dataclass(frozen=True)
class Planilha:
    """Um tipo de planilha de rótulos: itens do sorteio e dimensões rotuladas."""

    tipo: str  # sufixo de rotulos_<avaliador>_<tipo>.csv
    arquivo_sorteio: str
    colunas_chave: tuple[str, ...]
    dimensoes: dict[str, tuple[str, ...]]  # dimensão → valores válidos (canônicos)
    arquivo_consenso: str

    @property
    def colunas_consenso(self) -> tuple[str, ...]:
        origens = ((d, f"origem_{d}") for d in self.dimensoes)
        return (*self.colunas_chave, *(c for par in origens for c in par))

    def chave(self, linha: dict) -> Chave:
        tag = linha.get("tag_name") if "tag_name" in self.colunas_chave else ""
        return (linha.get("full_name") or "", tag or "")


PLANILHAS = (
    Planilha("repos", ARQUIVO_SORTEIO_REPOS, ("full_name",), VALORES_ROTULOS_REPOS,
             ARQUIVO_CONSENSO_REPOS),
    Planilha("releases", ARQUIVO_SORTEIO_RELEASES, ("full_name", "tag_name"),
             VALORES_ROTULOS_RELEASES, ARQUIVO_CONSENSO_RELEASES),
)
DIMENSOES = {d: v for p in PLANILHAS for d, v in p.dimensoes.items()}


class ErroConsenso(RuntimeError):
    """Planilhas de rótulos ou desempates inválidos; `problemas` lista todos."""

    def __init__(self, problemas: list[str]):
        self.problemas = problemas
        super().__init__(
            f"{len(problemas)} problema(s) nas planilhas da amostra-ouro (nada foi gravado):\n"
            + "\n".join(f"  - {p}" for p in problemas)
        )


@dataclass(frozen=True)
class Resultado:
    """Resumo de uma geração: pasta, casos 1-1-1 sem decisão e decisões mantidas sem uso."""

    pasta: Path
    pendentes: int
    decisoes_nao_aplicadas: int


# --- leitura ----------------------------------------------------------------------------


def ler_csv(caminho: Path) -> list[dict[str, str]]:
    """Linhas de um CSV em UTF-8 (com ou sem BOM), separado por `,` ou `;`.

    O separador é o mais frequente na linha de cabeçalho. Nomes de coluna sem espaços nas
    pontas; células ausentes viram `""`. Levanta `UnicodeDecodeError` se não for UTF-8.
    """
    texto = caminho.read_text(encoding=CODIFICACAO_PLANILHAS)  # utf-8-sig: BOM opcional
    cabecalho = texto.splitlines()[0] if texto else ""
    separador = ";" if cabecalho.count(";") > cabecalho.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto, newline=""), delimiter=separador, restval="")
    leitor.fieldnames = [c.strip() for c in (leitor.fieldnames or [])]
    return [{k: v for k, v in linha.items() if k is not None} for linha in leitor]


def _descrever(chave: Chave) -> str:
    full_name, tag = chave
    return f"{full_name} {tag}" if tag else full_name


def _canonicos(valores: tuple[str, ...]) -> dict[str, str]:
    return {normalizar_rotulo(v): v for v in valores}


def _ler(caminho: Path, problemas: list[str], contexto: str) -> list[dict[str, str]] | None:
    """`ler_csv` que registra arquivo ausente ou fora de UTF-8 em `problemas`."""
    if not caminho.is_file():
        problemas.append(f"{contexto}: arquivo {caminho.name} ausente")
        return None
    try:
        return ler_csv(caminho)
    except UnicodeDecodeError:
        problemas.append(f"{contexto}: {caminho.name} não está em UTF-8 (salve como CSV UTF-8)")
        return None


def _faltando_colunas(linhas: list[dict], colunas: tuple[str, ...]) -> list[str]:
    presentes = set(linhas[0]) if linhas else set()
    return [c for c in colunas if c not in presentes]


def ler_sorteio(pasta: Path, planilha: Planilha, problemas: list[str]) -> list[Chave]:
    """Itens do sorteio, na ordem do arquivo; problemas vão para `problemas`."""
    contexto = f"sorteio {planilha.tipo}"
    linhas = _ler(pasta / planilha.arquivo_sorteio, problemas, contexto)
    if linhas is None:
        return []
    if not linhas:
        problemas.append(f"{contexto}: {planilha.arquivo_sorteio} sem itens")
        return []
    faltando = _faltando_colunas(linhas, planilha.colunas_chave)
    if faltando:
        problemas.append(f"{contexto}: {planilha.arquivo_sorteio} sem a(s) coluna(s) {', '.join(faltando)}")
        return []
    chaves = [planilha.chave(linha) for linha in linhas]
    repetidos = sorted(c for c, n in Counter(chaves).items() if n > 1)
    for chave in repetidos:
        problemas.append(f"{contexto}: {planilha.arquivo_sorteio}, item {_descrever(chave)} repetido")
    return list(dict.fromkeys(chaves))


def ler_rotulos(
    pasta: Path, planilha: Planilha, avaliador: str, itens: list[Chave], problemas: list[str],
) -> dict[Chave, dict[str, str]]:
    """Rótulos canônicos de um avaliador: item → dimensão → valor; problemas vão para `problemas`."""
    arquivo = arquivo_rotulos(avaliador, planilha.tipo)
    contexto = f"avaliador {avaliador}"
    linhas = _ler(pasta / arquivo, problemas, contexto)
    if linhas is None:
        return {}
    colunas = (*planilha.colunas_chave, *planilha.dimensoes)
    faltando = _faltando_colunas(linhas, colunas)
    if faltando:
        problemas.append(f"{contexto}: {arquivo} sem a(s) coluna(s) {', '.join(faltando)}")
        return {}

    rotulos: dict[Chave, dict[str, str]] = {}
    for linha in linhas:
        chave = planilha.chave(linha)
        local = f"{contexto}: {arquivo}, item {_descrever(chave)}"
        if chave in rotulos:
            problemas.append(f"{local} repetido")
            continue
        rotulos[chave] = {}
        for dimensao, valores in planilha.dimensoes.items():
            bruto = linha.get(dimensao) or ""
            normalizado = normalizar_rotulo(bruto)
            canonico = _canonicos(valores).get(normalizado)
            if not normalizado:
                problemas.append(f"{local}, coluna {dimensao}: rótulo vazio")
            elif canonico is None:
                problemas.append(
                    f"{local}, coluna {dimensao}: valor {bruto!r} inválido "
                    f"(válidos: {', '.join(valores)})")
            else:
                rotulos[chave][dimensao] = canonico

    esperados = set(itens)
    for chave in itens:
        if chave not in rotulos:
            problemas.append(f"{contexto}: {arquivo}, item {_descrever(chave)} faltando")
    for chave in rotulos:
        if chave not in esperados:
            problemas.append(f"{contexto}: {arquivo}, item {_descrever(chave)} sobrando (fora do sorteio)")
    return rotulos


def ler_desempates(caminho: Path, problemas: list[str]) -> dict[ChaveCaso, dict[str, str]]:
    """Linhas de `desempates.csv` com decisão (rotulo_final ou justificativa) preenchida.

    Chave (dimensao, full_name, tag_name), na ordem do arquivo; `rotulo_final` canônico.
    Arquivo ausente = nenhuma decisão.
    """
    if not caminho.is_file():
        return {}
    contexto = ARQUIVO_DESEMPATES
    linhas = _ler(caminho, problemas, contexto)
    if not linhas:
        return {}
    faltando = _faltando_colunas(linhas, (*COLUNAS_CHAVE_CASO, *COLUNAS_DECISAO))
    if faltando:
        problemas.append(f"{contexto}: sem a(s) coluna(s) {', '.join(faltando)}")
        return {}

    decisoes: dict[ChaveCaso, dict[str, str]] = {}
    for linha in linhas:
        if not any((linha.get(c) or "").strip() for c in COLUNAS_DECISAO):
            continue
        caso = tuple((linha.get(c) or "").strip() for c in COLUNAS_CHAVE_CASO)
        dimensao, full_name, tag = caso
        local = f"{contexto}, {dimensao} {_descrever((full_name, tag))}"
        if caso in decisoes:
            problemas.append(f"{local}: caso repetido")
            continue
        bruto = linha.get("rotulo_final") or ""
        if dimensao not in DIMENSOES:
            problemas.append(f"{local}: dimensão {dimensao!r} desconhecida "
                             f"(válidas: {', '.join(DIMENSOES)})")
            continue
        final = ""
        if normalizar_rotulo(bruto):
            final = _canonicos(DIMENSOES[dimensao]).get(normalizar_rotulo(bruto))
            if final is None:
                problemas.append(f"{local}, coluna rotulo_final: valor {bruto!r} inválido "
                                 f"(válidos: {', '.join(DIMENSOES[dimensao])})")
                continue
        decisoes[caso] = {
            **{c: linha.get(c) or "" for c in COLUNAS_DESEMPATES},
            "dimensao": dimensao, "full_name": full_name, "tag_name": tag,
            "rotulo_final": final,
        }
    return decisoes


# --- cálculo (puro) ---------------------------------------------------------------------


def _numero(valor: float) -> str:
    texto = f"{valor:.{CASAS_DECIMAIS}f}"
    return texto[1:] if texto.startswith("-") and float(texto) == 0 else texto


def linha_concordancia(dimensao: str, itens: list[tuple[str, ...]], categorias: tuple[str, ...]) -> dict:
    """Linha de `concordancia.csv` de uma dimensão (kappa vazio quando indefinido)."""
    kappa = kappa_fleiss(itens, categorias)
    return {
        "dimensao": dimensao,
        "n_itens": len(itens),
        "n_avaliadores": len(itens[0]),
        "concordancia_observada": _numero(concordancia_observada(itens)),
        "kappa_fleiss": "" if kappa is None else _numero(kappa),
        "interpretacao": interpretar_kappa(kappa),
    }


# --- orquestração (disco) ---------------------------------------------------------------


def gerar_consenso(pasta: Path) -> Resultado:
    """Valida as planilhas de `pasta` e grava concordância, divergências, desempates e consenso.

    Levanta `ErroConsenso` com todos os problemas, sem gravar nada, se a validação falhar.
    """
    pasta = Path(pasta)
    problemas: list[str] = []
    itens = {p.tipo: ler_sorteio(pasta, p, problemas) for p in PLANILHAS}
    rotulos = {
        (p.tipo, a): ler_rotulos(pasta, p, a, itens[p.tipo], problemas)
        for p in PLANILHAS for a in AVALIADORES
    }
    decisoes = ler_desempates(pasta / ARQUIVO_DESEMPATES, problemas)
    if problemas:
        raise ErroConsenso(problemas)

    concordancia, divergencias, desempates = [], [], []
    consensos: dict[str, list[dict]] = {}
    situacao: dict[ChaveCaso, str] = {}  # tipo de divergência atual, para avisos
    pendentes = 0
    for planilha in PLANILHAS:
        linhas_consenso = {chave: dict(zip(planilha.colunas_chave, chave)) for chave in itens[planilha.tipo]}
        for dimensao, valores in planilha.dimensoes.items():
            votos = [
                tuple(rotulos[(planilha.tipo, a)][chave][dimensao] for a in AVALIADORES)
                for chave in itens[planilha.tipo]
            ]
            concordancia.append(linha_concordancia(dimensao, votos, valores))
            for chave, rots in zip(itens[planilha.tipo], votos):
                caso = (dimensao, *chave)
                base = {**dict(zip(COLUNAS_CHAVE_CASO, caso)), **dict(zip(COLUNAS_ROTULOS_AVALIADORES, rots))}
                tipo = tipo_divergencia(rots)
                situacao[caso] = tipo or "unânime"
                if tipo:
                    divergencias.append({**base, "tipo": tipo})
                rotulo, origem = consenso(rots)
                if tipo == DIVERGENCIA_1_1_1:
                    decisao = decisoes.pop(caso, {})
                    final = decisao.get("rotulo_final", "")
                    desempates.append({**base, "rotulo_final": final,
                                       "justificativa": decisao.get("justificativa", "")})
                    if final:
                        rotulo, origem = final, ORIGEM_REUNIAO
                    else:
                        pendentes += 1
                linhas_consenso[chave][dimensao] = rotulo or ""
                linhas_consenso[chave][f"origem_{dimensao}"] = origem
        consensos[planilha.arquivo_consenso] = list(linhas_consenso.values())

    for caso, decisao in decisoes.items():  # decisões cujo caso deixou de ser 1-1-1
        dimensao, full_name, tag = caso
        log.warning(
            "%s: decisão de %s para %s mantida, mas o caso não é mais 1-1-1 (agora: %s); "
            "não aplicada ao consenso", ARQUIVO_DESEMPATES, dimensao, _descrever((full_name, tag)),
            situacao.get(caso, "fora do sorteio"))
        desempates.append(decisao)

    gravar_csv(pasta / ARQUIVO_CONCORDANCIA, COLUNAS_CONCORDANCIA, concordancia)
    gravar_csv(pasta / ARQUIVO_DIVERGENCIAS, COLUNAS_DIVERGENCIAS, divergencias)
    gravar_csv(pasta / ARQUIVO_DESEMPATES, COLUNAS_DESEMPATES, desempates)
    for planilha in PLANILHAS:
        gravar_csv(pasta / planilha.arquivo_consenso, planilha.colunas_consenso,
                   consensos[planilha.arquivo_consenso])
    for linha in concordancia:
        log.info("%s: concordância observada %s, kappa de Fleiss %s (%s)", linha["dimensao"],
                 linha["concordancia_observada"], linha["kappa_fleiss"] or "indefinido",
                 linha["interpretacao"])
    log.info("amostra-ouro: %d divergências (%d casos 1-1-1); arquivos gravados em %s",
             len(divergencias), sum(1 for d in divergencias if d["tipo"] == DIVERGENCIA_1_1_1), pasta)
    return Resultado(pasta, pendentes, len(decisoes))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pipeline.consenso",
        description="Concordância (kappa de Fleiss) e consenso da amostra-ouro (seção 6 do enunciado)",
    )
    parser.add_argument("--config", default="config.yaml", help="caminho do config.yaml")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        config = carregar_config(args.config)
    except ErroConfiguracao as e:
        log.error("%s", e)
        return 2

    try:
        resultado = gerar_consenso(Path(config.dir_saida) / PASTA_AMOSTRA_OURO)
    except ErroConsenso as e:
        log.error("%s", e)
        return 1
    if resultado.pendentes:
        log.warning(
            "%d caso(s) 1-1-1 sem decisão (origem %s no consenso): preencha rotulo_final e "
            "justificativa em %s e rode de novo", resultado.pendentes, ORIGEM_PENDENTE,
            resultado.pasta / ARQUIVO_DESEMPATES)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
