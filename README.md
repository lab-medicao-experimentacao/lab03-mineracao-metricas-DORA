# Lab03 — Mineração de Métricas DORA

Pipeline que coleta dados públicos de repositórios open-source no GitHub (releases, commits e workflow runs do GitHub Actions) e calcula aproximações das quatro métricas DORA.

- Enunciado: [`03 - Mineração de Métricas DORA.md`](./03%20-%20Mineração%20de%20Métricas%20DORA.md)
- Diretrizes do grupo (para integrantes e IAs): [`DIRETRIZES.md`](./DIRETRIZES.md)

## Requisitos

- Python 3.12 ou mais recente
- Um token do GitHub ([como criar](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)). Para dados públicos, um token sem escopos já basta.

## Instalação

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

## Execução

Defina o token **apenas** como variável de ambiente (nunca o coloque no repositório):

```bash
# Linux/macOS
export GITHUB_TOKEN=ghp_...
# Windows (PowerShell)
$env:GITHUB_TOKEN = "ghp_..."
```

Execute o pipeline com um único comando:

```bash
python -m pipeline --config config.yaml
```

Os parâmetros do estudo (janela de observação, faixas de estrelas, critérios de inclusão, tamanho da amostra e semente) ficam em [`config.yaml`](./config.yaml).

| Pasta | Conteúdo | Versionada? |
|---|---|---|
| `data/cache/` | respostas cruas da API (permite retomar a coleta) | não |
| `data/processed/` | CSVs intermediários | não |
| `output/` | funil de seleção, dataset final e dicionário de dados | sim |

Os coletores de releases e commits exportam `data/processed/releases.csv`
(`full_name`, `tag_name`, `published_at`, `draft`, `prerelease`),
`data/processed/tags.csv` (`full_name`, `tag_name`, `commit_sha`, `commit_date`)
e `data/processed/commits.csv` (`full_name`, `tag_name`, `sha`,
`author_date`, `message`). As datas são gravadas em ISO 8601 UTC. Releases
anteriores à janela são preservadas para servir de base ao cálculo de lead time.

## Testes

```bash
pytest --cov=metricas --cov-report=term-missing --cov-fail-under=80
```

Os testes também rodam no GitHub Actions a cada push (`.github/workflows/testes.yml`).
