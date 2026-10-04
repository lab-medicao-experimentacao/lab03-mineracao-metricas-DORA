"""Carrega e valida o config.yaml do pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import yaml

VARIAVEL_TOKEN = "GITHUB_TOKEN"


class ErroConfiguracao(ValueError):
    """config.yaml ausente, incompleto ou inconsistente."""


@dataclass(frozen=True)
class FaixaEstrelas:
    min: int
    max: int | None  # None = sem limite superior

    def consulta(self) -> str:
        """Qualificador para a Search API (ex.: 'stars:1000..1499' ou 'stars:>=50000')."""
        if self.max is None:
            return f"stars:>={self.min}"
        return f"stars:{self.min}..{self.max}"


@dataclass(frozen=True)
class Janela:
    inicio: datetime  # inclusivo, 00:00 UTC do dia inicial
    fim: datetime     # exclusivo, 00:00 UTC do dia seguinte ao dia final

    @property
    def semanas(self) -> float:
        """Duração da janela em semanas (≈ 52,1 para 12 meses)."""
        return (self.fim - self.inicio) / timedelta(weeks=1)

    def contem(self, instante: datetime) -> bool:
        return self.inicio <= instante < self.fim

    def filtro_created(self) -> str:
        """Valor do parâmetro `created` da API (AAAA-MM-DD..AAAA-MM-DD, inclusivo)."""
        ultimo_dia = (self.fim - timedelta(days=1)).date()
        return f"{self.inicio.date().isoformat()}..{ultimo_dia.isoformat()}"


@dataclass(frozen=True)
class Config:
    janela: Janela
    faixas_estrelas: tuple[FaixaEstrelas, ...]
    excluir_forks: bool
    excluir_arquivados: bool
    min_releases: int
    min_runs: int
    tamanho_amostra: int
    semente: int
    dir_cache: Path
    dir_processados: Path
    dir_saida: Path


def carregar_config(caminho: str | Path) -> Config:
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroConfiguracao(f"arquivo de configuração não encontrado: {caminho}")
    try:
        with caminho.open(encoding="utf-8") as f:
            bruto = yaml.safe_load(f) or {}
    except (yaml.YAMLError, ValueError) as e:  # ValueError: data impossível, ex. 2026-02-30
        raise ErroConfiguracao(f"config.yaml inválido: {e}") from e

    try:
        bruto = _secao(bruto, "config.yaml")
        janela = _ler_janela(_secao(bruto["janela"], "janela"))
        selecao = _secao(bruto["selecao"], "selecao")
        faixas_brutas = selecao["faixas_estrelas"]
        if not isinstance(faixas_brutas, list):
            raise ErroConfiguracao("selecao.faixas_estrelas deve ser uma lista")
        faixas = tuple(_ler_faixa(_secao(f, "faixa de estrelas")) for f in faixas_brutas)
        inclusao = _secao(bruto["inclusao"], "inclusao")
        amostra = _secao(bruto["amostra"], "amostra")
        caminhos = _secao(bruto["caminhos"], "caminhos")
        config = Config(
            janela=janela,
            faixas_estrelas=faixas,
            excluir_forks=_booleano(selecao["excluir_forks"], "selecao.excluir_forks"),
            excluir_arquivados=_booleano(selecao["excluir_arquivados"], "selecao.excluir_arquivados"),
            min_releases=_inteiro(inclusao["min_releases"], "inclusao.min_releases"),
            min_runs=_inteiro(inclusao["min_runs"], "inclusao.min_runs"),
            tamanho_amostra=_inteiro(amostra["tamanho"], "amostra.tamanho"),
            semente=_inteiro(amostra["semente"], "amostra.semente"),
            dir_cache=Path(caminhos["cache"]),
            dir_processados=Path(caminhos["processados"]),
            dir_saida=Path(caminhos["saida"]),
        )
    except KeyError as e:
        raise ErroConfiguracao(f"chave obrigatória ausente no config: {e}") from e

    _validar(config)
    return config


def ler_token() -> str:
    """Lê o token do GitHub da variável de ambiente (nunca do repositório)."""
    token = os.environ.get(VARIAVEL_TOKEN, "").strip()
    if not token:
        raise ErroConfiguracao(
            f"defina a variável de ambiente {VARIAVEL_TOKEN} com um token do GitHub"
        )
    return token


def _ler_janela(bruto: dict) -> Janela:
    inicio = _para_date(bruto["inicio"])
    fim = _para_date(bruto["fim"])
    return Janela(
        inicio=datetime.combine(inicio, time.min, tzinfo=timezone.utc),
        fim=datetime.combine(fim + timedelta(days=1), time.min, tzinfo=timezone.utc),
    )


def _para_date(valor: object) -> date:
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError as e:
        raise ErroConfiguracao(f"data inválida (use AAAA-MM-DD): {valor!r}") from e


def _ler_faixa(bruto: dict) -> FaixaEstrelas:
    maximo = bruto["max"]  # obrigatório; null explícito = sem limite superior
    return FaixaEstrelas(
        min=_inteiro(bruto["min"], "faixa.min"),
        max=None if maximo is None else _inteiro(maximo, "faixa.max"),
    )


def _secao(valor: object, nome: str) -> dict:
    if not isinstance(valor, dict):
        raise ErroConfiguracao(f"{nome} deve ser um mapeamento (chave: valor), recebido {valor!r}")
    return valor


def _inteiro(valor: object, nome: str) -> int:
    # bool é subclasse de int em Python: `true` não pode virar 1 em silêncio
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErroConfiguracao(f"{nome} deve ser um número inteiro, recebido {valor!r}")
    return valor


def _booleano(valor: object, nome: str) -> bool:
    if not isinstance(valor, bool):
        raise ErroConfiguracao(f"{nome} deve ser true ou false, recebido {valor!r}")
    return valor


def _validar(config: Config) -> None:
    if config.janela.fim <= config.janela.inicio:
        raise ErroConfiguracao("janela.fim deve ser posterior a janela.inicio")
    if not config.faixas_estrelas:
        raise ErroConfiguracao("selecao.faixas_estrelas não pode ser vazia")
    for faixa in config.faixas_estrelas:
        if faixa.min < 0 or (faixa.max is not None and faixa.max < faixa.min):
            raise ErroConfiguracao(f"faixa de estrelas inválida: {faixa}")
    for anterior, seguinte in zip(config.faixas_estrelas, config.faixas_estrelas[1:]):
        if anterior.max is None or seguinte.min <= anterior.max:
            raise ErroConfiguracao("faixas de estrelas devem ser crescentes e não sobrepostas")
        if seguinte.min != anterior.max + 1:
            raise ErroConfiguracao(
                f"lacuna entre faixas de estrelas: {anterior.max + 1}..{seguinte.min - 1} nunca seria buscada"
            )
    if config.min_releases < 1 or config.min_runs < 1 or config.tamanho_amostra < 1:
        raise ErroConfiguracao("limites de inclusão e tamanho da amostra devem ser positivos")
