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

Alternativa: crie um arquivo `.env` na pasta de onde o comando é executado (a raiz do
repositório) com a linha `GITHUB_TOKEN=ghp_...`. O `.env` está no `.gitignore` e é lido
pelo próprio pipeline (sem dependência extra); uma variável já definida no ambiente tem
precedência sobre o arquivo.

Execute o pipeline com um único comando:

```bash
python -m pipeline --config config.yaml
```

A execução busca os candidatos, aplica o funil e coleta metadados, releases, tags, commits e workflow runs só da amostra. Rodar de novo reaproveita o cache em `data/cache`. Com `--funil-completo`, o funil avalia todos os candidatos (custo máximo de cota, mesma amostra).

Os parâmetros do estudo (janela de observação, faixas de estrelas, critérios de inclusão, tamanho da amostra e semente) ficam em [`config.yaml`](./config.yaml).

| Pasta | Conteúdo | Versionada? |
|---|---|---|
| `data/cache/` | respostas cruas da API (permite retomar a coleta) | não |
| `data/processed/` | CSVs intermediários | não |
| `output/` | funil de seleção, dataset final e dicionário de dados | sim |

O `GitHubClient` (`pipeline/github_client.py`) grava cada resposta da API em
`data/cache/<aa>/<sha256>.json.gz` (JSON comprimido com gzip; a gravação é atômica, então
um `Ctrl+C` no meio não deixa arquivo pela metade); ao rodar de novo, o que já foi
baixado não é requisitado outra vez. Ele espera a renovação da cota quando
`X-RateLimit-Remaining` chega a 0 (ou a API responde 403/429 de limite, inclusive o
secundário: `Retry-After` ou 60 s, 120 s, 240 s…) e repete erros 5xx e falhas de rede com
espera de 1 s, 2 s, 4 s, 8 s… Para recomeçar do zero, apague `data/cache/`.

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
As datas das tags vêm da API GraphQL (1 ponto por 100 tags, em vez de uma chamada REST
por tag). Releases da janela cujo `compare` não pôde ser calculado (primeira release da
história, 404 de tag apagada/reescrita, 422 ou 5xx persistente) ficam em
`data/processed/releases_sem_compare.csv` (`full_name`, `tag_name`, `motivo`), e os meses
de runs que bateram o teto de 1.000 resultados, em `data/processed/runs_meses_saturados.csv`.

## Testes

```bash
pytest --cov=metricas --cov-report=term-missing --cov-fail-under=80
```

Os testes também rodam no GitHub Actions a cada push (`.github/workflows/testes.yml`).
