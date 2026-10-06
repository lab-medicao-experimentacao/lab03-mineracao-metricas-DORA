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

O `GitHubClient` (`pipeline/github_client.py`) grava cada resposta da API em
`data/cache/<aa>/<sha256>.json`; ao rodar de novo (ou após `Ctrl+C`), o que já foi
baixado não é requisitado outra vez. Ele espera a renovação da cota quando
`X-RateLimit-Remaining` chega a 0 e repete erros 5xx com espera de 1 s, 2 s, 4 s, 8 s…
Para recomeçar do zero, apague `data/cache/`.

O coletor de workflow runs (`pipeline/workflow_runs.py`) consulta um mês por vez
(push no default branch) e avisa, no log, se algum mês atingir o teto de 1.000
resultados da API. Ele exporta `data/processed/runs.csv` (`full_name`, `id`,
`workflow_id`, `event`, `head_branch`, `conclusion`, `classe`, `created_at`,
`run_started_at`, `updated_at`), em que `classe` é `sucesso`, `falha` ou `ignorado`.

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
