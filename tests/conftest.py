import textwrap
from pathlib import Path

import pytest

CONFIG_VALIDO = """
janela:
  inicio: 2025-10-01
  fim: 2026-09-30
selecao:
  faixas_estrelas:
    - {min: 1000, max: 1999}
    - {min: 2000, max: null}
  excluir_forks: true
  excluir_arquivados: true
inclusao:
  min_releases: 5
  min_runs: 50
amostra:
  tamanho: 100
  semente: 42
caminhos:
  cache: {tmp}/cache
  processados: {tmp}/processed
  saida: {tmp}/output
"""


@pytest.fixture
def escrever_config(tmp_path):
    """Escreve um config.yaml em tmp_path; aceita substituições de texto no YAML válido."""

    def _escrever(substituicoes: dict[str, str] | None = None) -> Path:
        texto = textwrap.dedent(CONFIG_VALIDO).replace("{tmp}", tmp_path.as_posix())
        for antigo, novo in (substituicoes or {}).items():
            assert antigo in texto, f"trecho não encontrado no config de teste: {antigo}"
            texto = texto.replace(antigo, novo)
        caminho = tmp_path / "config.yaml"
        caminho.write_text(texto, encoding="utf-8")
        return caminho

    return _escrever
