# Dicionário de dados

Documenta todas as colunas dos CSVs finais e intermediários do pipeline (enunciado, seção 7;
DIRETRIZES, seção 5.4). Para cada coluna: nome, tipo, unidade e fórmula ou origem na API do
GitHub. O arquivo principal para as análises é [`metricas_repos.csv`](./metricas_repos.csv).

## Convenções

- **Janela de observação:** `config.yaml → janela` (2025-10-01 a 2026-09-30, fechada em dias). Nas
  fórmulas, `inicio` é 00:00 UTC do primeiro dia (inclusivo) e `fim` é 00:00 UTC do dia seguinte
  ao último (exclusivo). A janela tem 365 dias ≈ 52,14 semanas.
- **Datas e horas:** texto ISO 8601 em UTC com deslocamento (`2025-11-08T12:00:00+00:00`).
- **Booleanos:** `True` ou `False`. **Vazio** = valor ausente (`None`): a métrica não pôde ser
  calculada por falta de dados, e nunca significa zero.
- **Unidades:** lead time e tempo de recuperação em **horas**; frequência em **releases/semana**;
  CFR e proporções como **fração entre 0 e 1**; idade em **dias**.
- **Tipos:** `texto`, `inteiro`, `decimal`, `data`, `booleano`.
- **Release principal (deploy):** `draft = false` e `prerelease = false`, com `published_at` na
  janela. Runs válidos: `event = push`, branch igual ao `default_branch` e `conclusion` de
  sucesso ou falha (`success` → sucesso; `failure`, `timed_out`, `startup_failure` → falha; o
  resto é ignorado).
- **Estatística:** valores por repositório já são medianas (lead time, recuperação); as análises
  entre repositórios usam mediana e IQR.

---

## `output/metricas_repos.csv` (dono: C, #35)

Uma linha por repositório da amostra final, na ordem de `repos.csv`. Gerado offline por
`python -m pipeline.dataset --config config.yaml` a partir de `output/repos.csv` e de
`data/processed/`. As métricas são calculadas pelas funções puras de `metricas/`.

### Identificação e metadados (RQ 06)

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | `owner/repo`. Chave do repositório em todos os CSVs. |
| `default_branch` | texto | - | `default_branch` do repositório. Só esse branch conta. |
| `language` | texto | - | Linguagem principal (`language` do `GET /search/repositories`). Vazio se a API não informa. |
| `stars` | inteiro | estrelas | `stargazers_count` na data da busca. |
| `contributors` | inteiro | pessoas | Nº da última página de `GET /repos/{r}/contributors?per_page=1&anon=true` (inclui autores anônimos). Vazio quando a API recusa a listagem (403, histórico grande demais). |
| `created_at` | data | - | `created_at` do repositório. |
| `idade_dias` | inteiro | dias | `floor(janela.fim − created_at)` em dias inteiros. |
| `tipo_projeto` | texto | - | Consenso da amostra-ouro (`consenso_repos.csv`): `biblioteca/framework`, `aplicação/serviço`, `ferramenta CLI` ou `outro`. **Preenchido só nos 60 repositórios da amostra-ouro**, e vazio nos demais (e em todos enquanto o consenso não for gerado). |
| `entregas_reais` | texto | - | Consenso da amostra-ouro: `sim`, `não` ou `incerto`. Mesma cobertura de `tipo_projeto`. |

### RQ 01: frequência de deploys

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `n_releases` | inteiro | releases | Releases principais publicadas na janela (`GET /repos/{r}/releases`, `published_at`). |
| `n_prereleases` | inteiro | releases | Pré-releases (não draft) publicadas na janela. Não entram na métrica principal; servem à variante da RQ 07. |
| `frequencia_semana` | decimal | releases/semana | `n_releases ÷ (365 / 7)`. |
| `frequencia_prerelease_semana` | decimal | releases/semana | Variante de unidade de deploy da RQ 07 (release + pré-release): `(n_releases + n_prereleases) ÷ (365 / 7)`. |
| `n_tags` | inteiro | tags | Tags do repositório (`tags.csv`) cujo commit apontado tem `commit.author.date` na janela. A API não dá a data de criação da tag; usa-se a data do commit. |
| `frequencia_tag_semana` | decimal | tags/semana | Variante de unidade de deploy da RQ 07 (tag): `n_tags ÷ (365 / 7)`. |

### RQ 02: lead time

Commits de cada release R vêm de `GET /repos/{r}/compare/{release anterior}...{R}`; o tempo de um
commit é `R.published_at − commit.author.date`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `lead_time_release_horas` | decimal | horas | Variante (a): mediana, entre as releases, de `R.published_at − (data do commit mais antigo incluído em R)`. Vazio sem nenhuma release com commits. |
| `lead_time_commit_horas` | decimal | horas | Variante (b): mediana de `R.published_at − commit.author.date` sobre **todos** os commits de **todas** as releases. |
| `n_releases_lead_time` | inteiro | releases | Releases principais da janela com ao menos um commit calculado (base dos dois lead times). |
| `n_commits_lead_time` | inteiro | commits | Total de commits dessas releases (base da variante b). |
| `n_releases_sem_anterior` | inteiro | releases | Releases ignoradas por não terem release anterior (primeira da história do repositório). Origem: `releases_sem_compare.csv`, motivo `sem_anterior`. |
| `n_releases_compare_404` | inteiro | releases | Releases ignoradas porque o compare respondeu 404 (tag apagada ou reescrita). Motivo `compare_404`. |
| `n_releases_compare_outros` | inteiro | releases | Releases ignoradas por outros erros do compare (422 e demais). Motivos `compare_<status>` diferentes de 404. |

### RQ 03 (a): CFR por proxy de CI

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `cfr_ci` | decimal | fração 0–1 | `n_runs_falha ÷ (n_runs_falha + n_runs_sucesso)`. Vazio sem runs de sucesso ou falha. |
| `n_runs_validos` | inteiro | runs | Runs de sucesso ou falha, `push`, default branch, `created_at` na janela (`GET /repos/{r}/actions/runs`). |
| `n_runs_sucesso` | inteiro | runs | Runs válidos com `conclusion = success`. |
| `n_runs_falha` | inteiro | runs | Runs válidos com `conclusion` em `failure`, `timed_out` ou `startup_failure`. |
| `n_runs_ignorados` | inteiro | runs | Runs coletados com `conclusion` ignorada (`cancelled`, `skipped`, `neutral`, `action_required`, `stale` ou ausente). |
| `n_meses_runs_saturados` | inteiro | meses | Meses da janela em que a consulta de runs bateu o teto de 1.000 resultados da API (`runs_meses_saturados.csv`). Acima de 0, a contagem de runs pode estar incompleta. |

### RQ 03 (b): CFR por proxy de entrega

Uma release falhou se uma **release corretiva** (`metricas.cfr.release_corretiva`) a seguir em até
7 dias. Releases publicadas nos últimos 7 dias da janela são **censuradas** e ficam fora do denominador.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `cfr_entrega` | decimal | fração 0–1 | `n_releases_falharam ÷ n_releases_avaliadas`. Vazio sem releases avaliáveis. |
| `n_releases_avaliadas` | inteiro | releases | Releases principais publicadas até 7 dias antes de `fim` (denominador). |
| `n_releases_falharam` | inteiro | releases | Avaliadas seguidas de uma corretiva em até 7 dias (numerador). |
| `n_releases_censuradas` | inteiro | releases | Releases principais publicadas nos últimos 7 dias da janela (`n_releases_avaliadas + n_releases_censuradas = n_releases`). |

### RQ 04: tempo de recuperação

Por workflow (`workflow_id`), em ordem cronológica: um episódio começa na primeira falha após um
sucesso e termina no próximo sucesso. Tempo do episódio = `updated_at` do sucesso − `run_started_at`
da primeira falha. Episódio sem sucesso até `fim` é **censurado**: conta o tempo decorrido até `fim`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `recuperacao_mediana_horas` | decimal | horas | Mediana dos tempos de todos os episódios de todos os workflows, **incluindo os censurados**. Vazio sem episódios. |
| `n_episodios_recuperacao` | inteiro | episódios | Total de episódios de falha. |
| `prop_episodios_censurados` | decimal | fração 0–1 | `episódios censurados ÷ n_episodios_recuperacao`. Vazio sem episódios. |

### Classificação DORA (combinação de referência)

Faixas fixas do enunciado (RQ 07) aplicadas a `frequencia_semana`, `lead_time_release_horas` (a),
`cfr_ci` (a) e `recuperacao_mediana_horas`. Valores: `Elite`, `High`, `Medium`, `Low`. Vazio quando a
métrica não existe.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `classe_frequencia` | texto | - | Elite ≥ 7/sem; High ≥ 1/sem; Medium ≥ 1 por mês; Low abaixo disso. |
| `classe_lead_time` | texto | - | Elite < 1 dia; High < 1 semana; Medium < 30 dias; Low ≥ 30 dias. |
| `classe_cfr` | texto | - | Elite ≤ 15%; High ≤ 30%; Medium ≤ 45%; Low > 45%. |
| `classe_recuperacao` | texto | - | Elite < 1 h; High < 1 dia; Medium < 1 semana; Low ≥ 1 semana. |
| `classe_geral` | texto | - | Mediana dos pontos (Elite 4, High 3, Medium 2, Low 1) das métricas disponíveis, arredondada para baixo. Vazio com menos de 3 métricas. |

---

## `output/candidatos.csv` (dono: A)

Todos os candidatos da busca `GET /search/repositories` (fatiada por faixas de estrelas).

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | `full_name`. |
| `default_branch` | texto | - | `default_branch`. |
| `stars` | inteiro | estrelas | `stargazers_count`. |
| `language` | texto | - | `language`. Vazio se ausente. |
| `created_at` | data | - | `created_at`. |
| `fork` | booleano | - | `fork`. |
| `archived` | booleano | - | `archived`. |

## `output/funil.csv` (dono: A)

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `etapa` | texto | - | Nome da etapa do funil de seleção. |
| `n_restantes` | inteiro | repositórios | Repositórios que seguem após a etapa. |
| `n_descartados` | inteiro | repositórios | Repositórios descartados na etapa. |
| `motivo` | texto | - | Critério da etapa e contagem por causa de descarte. |

## `output/repos.csv` (dono: A)

Amostra final (300 repositórios). Colunas de `candidatos.csv` mais `contributors` e `idade_dias`,
cujas definições estão em `metricas_repos.csv`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name`, `default_branch`, `stars`, `language`, `created_at`, `fork`, `archived` | - | - | Como em `candidatos.csv`. |
| `contributors` | inteiro | pessoas | Como em `metricas_repos.csv`. |
| `idade_dias` | inteiro | dias | Como em `metricas_repos.csv`. |

---

## Dados intermediários (`data/processed/`, não versionados)

### `releases.csv` (dono: B)

Todas as releases do repositório (inclusive anteriores à janela, usadas como referência), de
`GET /repos/{r}/releases`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | Repositório. |
| `tag_name` | texto | - | `tag_name` da release. |
| `published_at` | data | - | `published_at`. |
| `draft` | booleano | - | `draft`. |
| `prerelease` | booleano | - | `prerelease`. |

### `tags.csv` (dono: B)

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | Repositório. |
| `tag_name` | texto | - | Nome da tag. |
| `commit_sha` | texto | - | SHA do commit apontado (tags anotadas são seguidas até o commit). API GraphQL. |
| `commit_date` | data | - | `authoredDate` do commit apontado (= `commit.author.date`). |

### `commits.csv` (dono: B)

Commits incluídos em cada release da janela, de `GET /repos/{r}/compare/{anterior}...{tag}`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | Repositório. |
| `tag_name` | texto | - | Release de destino do compare. |
| `sha` | texto | - | `sha` do commit. |
| `author_date` | data | - | `commit.author.date`. |
| `message` | texto | - | `commit.message`, completa (pode ter várias linhas). |

### `releases_sem_compare.csv` (dono: B)

Releases da janela sem commits calculáveis.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | Repositório. |
| `tag_name` | texto | - | Release ignorada no lead time. |
| `motivo` | texto | - | `sem_anterior` (primeira release da história), `compare_404`, `compare_422` ou `compare_<status>` de outro erro. |

### `runs.csv` (dono: C)

Workflow runs da janela, no default branch e com `event = push`, válidos e ignorados.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | Repositório. |
| `id` | inteiro | - | `id` do run. |
| `workflow_id` | inteiro | - | `workflow_id`. |
| `event` | texto | - | `event` (sempre `push`). |
| `head_branch` | texto | - | `head_branch`. |
| `conclusion` | texto | - | `conclusion`. Vazio quando o run não terminou. |
| `classe` | texto | - | `sucesso`, `falha` ou `ignorado`, a partir de `conclusion`. |
| `created_at` | data | - | `created_at`. |
| `run_started_at` | data | - | `run_started_at` (usa `created_at` se ausente). |
| `updated_at` | data | - | `updated_at`. |

### `runs_meses_saturados.csv` (dono: C)

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | Repositório. |
| `periodo` | texto | - | Mês da janela cuja consulta bateu o teto de 1.000 runs (`AAAA-MM-DD..AAAA-MM-DD`). Só cabeçalho = nenhum mês. |

---

## Validação manual (`output/amostra_ouro/`)

### `sorteio_repos.csv` e `rotulos_<A|B|C>_repos.csv` (dono: A, #29)

60 repositórios sorteados de `repos.csv` (semente 42). As planilhas de rótulos repetem as colunas do
sorteio e acrescentam as colunas preenchidas pelo avaliador.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | Repositório sorteado. |
| `url_repo` | texto | - | `https://github.com/{full_name}`. |
| `url_releases` | texto | - | `https://github.com/{full_name}/releases`. |
| `linguagem` | texto | - | `language` do repositório. |
| `tipo_projeto` | texto | - | Rótulo: `biblioteca/framework`, `aplicação/serviço`, `ferramenta CLI` ou `outro` (só nas planilhas de rótulos). |
| `entregas_reais` | texto | - | Rótulo: `sim`, `não` ou `incerto` (só nas planilhas de rótulos). |
| `observacoes` | texto | - | Texto livre e opcional (só nas planilhas de rótulos). |

### `sorteio_releases.csv` e `rotulos_<A|B|C>_releases.csv` (dono: A, #29)

5 releases principais da janela por repositório sorteado (300 no total).

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | Repositório. |
| `tag_name` | texto | - | Release sorteada. |
| `published_at` | data | - | `published_at`. |
| `url_release` | texto | - | Página da release no GitHub. |
| `tag_anterior` | texto | - | Release principal publicada imediatamente antes (a mesma do lead time). Vazio na primeira. |
| `url_compare` | texto | - | Página `compare` entre `tag_anterior` e `tag_name`. Vazio na primeira. |
| `corretiva` | texto | - | Rótulo: `sim` ou `não` (só nas planilhas de rótulos). |
| `observacoes` | texto | - | Texto livre e opcional (só nas planilhas de rótulos). |

### `consenso_repos.csv` e `consenso_releases.csv` (dono: A, #33)

Gerados por `python -m pipeline.consenso`. Rótulo de consenso por item: unanimidade, maioria simples
ou, nos empates 1-1-1, decisão da reunião registrada em `desempates.csv`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | Repositório. |
| `tag_name` | texto | - | Release (só em `consenso_releases.csv`). |
| `tipo_projeto` | texto | - | Consenso (só em `consenso_repos.csv`). |
| `origem_tipo_projeto` | texto | - | `unanime`, `maioria` ou `reuniao`. |
| `entregas_reais` | texto | - | Consenso (só em `consenso_repos.csv`). |
| `origem_entregas_reais` | texto | - | `unanime`, `maioria` ou `reuniao`. |
| `corretiva` | texto | - | Consenso (só em `consenso_releases.csv`). |
| `origem_corretiva` | texto | - | `unanime`, `maioria` ou `reuniao`. |

### `concordancia.csv` (dono: A, #33)

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `dimensao` | texto | - | `tipo_projeto`, `entregas_reais` ou `corretiva`. |
| `n_itens` | inteiro | itens | Itens rotulados na dimensão. |
| `n_avaliadores` | inteiro | pessoas | Avaliadores por item (3). |
| `concordancia_observada` | decimal | fração 0–1 | Fração de itens com os 3 rótulos iguais (4 casas). |
| `kappa_fleiss` | decimal | -1 a 1 | Kappa de Fleiss (`statsmodels`, 4 casas). Vazio quando indefinido (todos os rótulos numa categoria). |
| `interpretacao` | texto | - | Faixa de Landis & Koch; `indefinido` quando não há kappa. |

### `divergencias.csv` e `desempates.csv` (dono: A, #33)

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `dimensao` | texto | - | Dimensão rotulada. |
| `full_name` | texto | - | Repositório. |
| `tag_name` | texto | - | Release (vazio nas dimensões de repositório). |
| `rotulo_A`, `rotulo_B`, `rotulo_C` | texto | - | Rótulo de cada avaliador. |
| `tipo` | texto | - | Só em `divergencias.csv`: `2x1` ou `1-1-1`. |
| `rotulo_final` | texto | - | Só em `desempates.csv`: decisão da reunião para casos `1-1-1` (preenchida à mão). |
| `justificativa` | texto | - | Só em `desempates.csv`: motivo da decisão. |

## Validação da heurística corretiva (`output/validacao_heuristica/`, dono: B, #34)

### `historico.csv` (uma linha por versão avaliada)

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `versao` | texto | - | Identificador da versão da heurística. |
| `descricao` | texto | - | O que mudou nesta versão. |
| `n_itens` | inteiro | releases | Releases do consenso avaliadas. |
| `n_corretivas_reais` | inteiro | releases | Corretivas no consenso. |
| `n_corretivas_previstas` | inteiro | releases | Corretivas apontadas por `release_corretiva`. |
| `vp`, `fp`, `fn`, `vn` | inteiro | releases | Verdadeiros positivos, falsos positivos, falsos negativos, verdadeiros negativos (positivo = corretiva). |
| `precisao` | decimal | fração 0–1 | `vp ÷ (vp + fp)`; 0 se o denominador for 0. |
| `recall` | decimal | fração 0–1 | `vp ÷ (vp + fn)`; 0 se o denominador for 0. |
| `f1` | decimal | fração 0–1 | Média harmônica de precisão e recall. |
| `situacao` | texto | - | `atingiu_meta` (F1 ≥ 0,70), `refinar` ou `sem_positivos`. |
| `n_sem_commits` | inteiro | releases | Releases sem commits na entrada. |
| `dados_sha256` | texto | - | Identificador (hash) dos dados usados. |
| `codigo_sha256` | texto | - | Identificador (hash) do código avaliado. |

### `<versao>/comparacao.csv`

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `full_name` | texto | - | Repositório. |
| `tag_name` | texto | - | Release avaliada. |
| `corretiva_consenso` | texto | - | `sim` ou `não`, do consenso humano. |
| `corretiva_prevista` | texto | - | `sim` ou `não`, da heurística. |
| `acertou` | booleano | - | `corretiva_consenso = corretiva_prevista`. |
| `sem_commits` | booleano | - | A release não tinha commits na entrada. |

## Análises RQ05 e RQ06 (`output/analises/`, dono: B, #46 e #47)

As análises leem `output/metricas_repos.csv` e preservam suas unidades:
frequência em releases/semana, tempos em horas e CFR em fração 0–1.
As categorias de projeto vêm do consenso humano já incorporado ao dataset.
Nenhuma dessas saídas altera os contratos de coleta ou os rótulos.

| Pasta | Saídas | Dicionário de colunas, tipos, unidades e fórmulas |
|---|---|---|
| `rq05/` | `correlacoes.csv`, `pares.csv`, `exclusoes.csv`, `relatorio.md` e duas dispersões PNG | [RQ05 — arquivos gerados e dicionário de dados](../analises/rq05.md#arquivos-gerados-e-dicionário-de-dados): Spearman, p-valor aproximado, n, exclusões por variante e rastreabilidade da entrada |
| `rq06/` | `testes.csv`, `descritivas.csv`, `agrupamentos.csv`, `limites_grupos.csv`, `exclusoes.csv`, `manifesto.json`, `relatorio.md` | [RQ06 — saídas e dicionário de dados](../analises/rq06.md#saídas-e-dicionário-de-dados): n e quartis por grupo, H/U₁, p bruto/Holm, ε²/δ, situações inviáveis e rastreabilidade |

Os comandos de reprodução estão no README e nesses documentos. O CFR (b)
permanece com interpretação provisória até a validação da #34; eventual
refinamento exige regenerar o dataset e repetir as análises.
