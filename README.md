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

`coleta.workers` (padrão 4, de 1 a 8) define quantas requisições à API podem estar em voo ao mesmo
tempo no funil e na coleta da amostra; a busca de candidatos é sempre sequencial (30 req/min). A amostra
e os CSVs são os mesmos para qualquer valor (os resultados são gravados na ordem sorteada); use
`workers: 1` para a execução sequencial. O `Ctrl+C` interrompe todas as threads, e rodar o mesmo comando
retoma a partir do cache.

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
espera de 1 s, 2 s, 4 s, 8 s… Com várias threads, a cota é compartilhada: quando acaba, todas
esperam a renovação; um limite secundário pausa todas; as partidas ficam espaçadas em 0,1 s.
Para recomeçar do zero, apague `data/cache/`.

O coletor de workflow runs (`pipeline/workflow_runs.py`) consulta a janela inteira de uma vez
quando ela tem menos de 1.000 runs (push no default branch); senão, um mês por vez, e avisa,
no log, se algum mês atingir o teto de 1.000 resultados da API. Ele exporta `data/processed/runs.csv` (`full_name`, `id`,
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

## Amostra-ouro (validação manual)

Depois do pipeline (que gera `output/repos.csv`), as planilhas de rotulagem da seção 6 do
enunciado são geradas com:

```bash
python -m pipeline.amostra_ouro --config config.yaml
```

O comando sorteia `amostra_ouro.tamanho` (60) repositórios da amostra final com
`df.sort_values("full_name").sample(n=60, random_state=42)` e, de cada um,
`amostra_ouro.releases_por_repo` (5) releases entre as publicadas na janela (não draft, não
pré-release), com `random.Random("42:<full_name>")`. A semente e os tamanhos ficam em
`config.yaml → amostra_ouro`; mesma semente e mesmo `repos.csv` = mesmo sorteio. As releases vêm
do cache em `data/cache` (cerca de uma chamada por repositório sorteado na primeira vez). Saídas em
`output/amostra_ouro/`:

| Arquivo | Conteúdo |
|---|---|
| `sorteio_repos.csv` | `full_name`, `url_repo`, `url_releases`, `linguagem` dos sorteados, na ordem do sorteio |
| `sorteio_releases.csv` | `full_name`, `tag_name`, `published_at`, `url_release` (página da release), `tag_anterior` (release publicada imediatamente antes, a mesma do lead time) e `url_compare` (commits desde ela; vazio se for a primeira) |
| `rotulos_<A\|B\|C>_repos.csv` | um por avaliador: colunas do sorteio + `tipo_projeto`, `entregas_reais`, `observacoes` (vazias) |
| `rotulos_<A\|B\|C>_releases.csv` | um por avaliador: colunas do sorteio + `corretiva`, `observacoes` (vazias) |
| `LEIAME.md` | instruções de rotulagem e valores válidos |

Valores válidos: `tipo_projeto` ∈ {`biblioteca/framework`, `aplicação/serviço`, `ferramenta CLI`,
`outro`}; `entregas_reais` ∈ {`sim`, `não`, `incerto`}; `corretiva` ∈ {`sim`, `não`}. Cada
avaliador preenche só a própria planilha, **sem consultar os demais e sem ver a saída da
heurística de release corretiva** (as planilhas não a trazem). As planilhas são CSV UTF-8 (com
BOM, para o Excel) separado por vírgulas.

Se alguma planilha `rotulos_*.csv` já tiver um rótulo ou observação preenchido, o comando recusa
sobrescrevê-la (código de saída 1, antes de qualquer chamada à API). `--forcar` regrava tudo e
**descarta os rótulos**.

## Testes

```bash
pytest --cov=metricas --cov-report=term-missing --cov-fail-under=80
```

Os testes também rodam no GitHub Actions a cada push (`.github/workflows/testes.yml`).
