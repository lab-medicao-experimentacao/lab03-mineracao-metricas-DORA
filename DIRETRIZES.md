# Diretrizes do Projeto — Lab03: Mineração de Métricas DORA

> **Leitura obrigatória** para todo integrante e para toda IA (Claude, Copilot, Cursor, ChatGPT…) que trabalhe neste repositório.
> O enunciado oficial está em [`03 - Mineração de Métricas DORA.md`](./03%20-%20Mineração%20de%20Métricas%20DORA.md). **Em caso de conflito, o enunciado vence**; abra uma Issue para corrigir este documento.

---

## 0. Regras de ouro (não negociáveis)

1. **Todo commit referencia uma Issue** (`#N` na mensagem). Commit sem Issue **não é considerado na correção**.
2. **Toda Issue tem Assignee** e está no GitHub Projects. Cartões sempre atualizados; respeitar o limite de WIP (seção 8).
3. **Nenhuma biblioteca de acesso à API do GitHub** (PyGithub, ghapi, github3.py, octokit…). Só `requests` + nosso próprio cliente.
4. **O token nunca é commitado.** É lido da variável de ambiente `GITHUB_TOKEN`. `.env` está no `.gitignore`.
5. **Definições operacionais da seção 3 do enunciado são lei.** Não “melhore” uma definição por conta própria — variantes só existem na RQ 07 e devem ser explícitas em `config.yaml`.
6. **Funções de métricas são puras** (sem rede, sem disco) e **têm testes** com fixtures. Cobertura ≥ 80 % em `metricas/`.
7. **Não altere um contrato de dados (seção 5) sem Issue e aviso ao grupo.** Os três integrantes trabalham em paralelo contra esses contratos.
8. **Hipóteses do artigo são escritas antes de ver qualquer dado.**

---

## 1. Decisões em aberto (preencher assim que definidas)

| Decisão | Valor | Responsável / fonte |
|---|---|---|
| Janela de observação (início/fim) | **`2025-10-01` a `2026-09-30`** (12 meses, dias inclusivos, UTC; em `config.yaml`). Decisão do grupo: o enunciado exige uma janela de 12 meses; esta é fechada e anterior à coleta, então releases e runs da janela não mudam entre execuções (salvo exclusões/edições feitas pelos próprios projetos), o que mantém a coleta reprodutível. Se o professor fixar outras datas, basta trocar o `config.yaml` | Grupo (#1) |
| Integrante A | Vitor Costa Vianna | — |
| Integrante B | `Joaquim` | — |
| Integrante C | `Gabriel Nogueira Vieira Resende` | — |
| Link do GitHub Projects | `<preencher>` | A |
| Excluir forks e repositórios arquivados na busca? | **Sim**, como etapa 2 do funil (custo zero, motivos contados em `funil.csv`), não como filtro escondido na consulta | Grupo (#3/#5) |
| Formato do cache | **Um JSON comprimido (gzip) por requisição** em `data/cache/<aa>/<sha256>.json.gz`, gravado de forma atômica; `.json` antigo continua sendo lido | C (#10) |
| Semente aleatória | `42` (em `config.yaml`, usada em todo sorteio) | Grupo |
| “1 deploy por mês” em releases/semana | `12 ÷ (365,25 / 7) ≈ 0,23` (`metricas/classificacao.py`) | A (#6) |
| Forks na busca: a Search API **omite forks por padrão** (só aparecem com `fork:true`) | **Decidido: a consulta leva `fork:true`** (`stars:A..B fork:true`). Justificativa: sem ele os forks somem em silêncio e a etapa “sem fork” registraria 0 sem tê-los visto; com ele a exclusão fica explícita e contada no funil (transparência do funil, mesma população final). Custo: só algumas páginas de busca a mais | A (#3) |
| `Response.json` no contrato 5.1: atributo ou método? | **Atributo** (corpo já decodificado; `None` se vazio). `Response` também tem `.headers` (só `Link` e `Content-Type`), `.status_code` e `.text`. `pipeline/selecao.py` continua aceitando os dois | C (#2/#10) |
| Funil sob demanda × completo | **Decidido: sob demanda** (padrão de `python -m pipeline`), no S01 e no S02. Os candidatos das etapas 1–2 são embaralhados com a semente **antes** de olhar qualquer dado e avaliados nessa ordem até completar a amostra; os avaliados são, portanto, uma amostra aleatória simples dos candidatos, e as proporções de descarte das etapas 3–5 estimam as da população. Justificativa: o funil completo custaria uma chamada a `/actions/workflows` por candidato (dezenas de milhares) mais releases e runs de todos os que passam, ou seja, dias de cota, sem mudar a amostra; para 300 no S02 basta aumentar `amostra.tamanho`, porque a ordem é a mesma e os 100 do S01 continuam como prefixo (cache reaproveitado). No artigo, o funil é relatado com as contagens absolutas das etapas 1–2 e as das etapas 3–5 “entre N avaliados” (com as proporções). `--funil-completo` continua disponível. *Ameaças (conclusão):* as proporções das etapas 3–5 são estimativas amostrais; a regra de parada no k-ésimo elegível introduz um viés pequeno | A (#5) |
| Classificação geral com métrica sem valor (`None`/NaN) | Ignorar a métrica e tirar a mediana (arredondada p/ baixo) das restantes, **desde que ao menos 3 das 4 tenham valor**; com 2 ou menos, `geral = None` (`MIN_METRICAS_GERAL` em `metricas/classificacao.py`). Motivo: qualquer trio contém ao menos uma métrica de vazão e uma de estabilidade; descartar todo repositório com métrica ausente enviesaria a amostra, porque recuperação `None` = nenhuma falha (os mais estáveis). Reportar, por combinação da RQ07, quantos ficaram com 3 métricas e quantos com `geral = None` | A (#6) — **decidido**: mínimo de 3 métricas |
| Contribuidores quando a API não lista (403 “contributor list is too large”, ex.: `torvalds/linux`) | **Decidido: `contributors = None`** (célula vazia em `repos.csv`) + aviso no log; **contrato 5.2 alterado para `int \| None`**. Na RQ06 o repositório fica fora só do fator “contribuidores” (análise por fator, sem descartá-lo das outras RQs) e o n de cada teste é reportado. Justificativa: imputar um número inventaria dado; descartar o repositório inteiro enviesaria a amostra contra os maiores projetos. *Ameaças (interna/conclusão):* o dado falta de forma não aleatória (só nos históricos muito grandes), o que pode subestimar o quartil superior de contribuidores; reportar quantos são | A (#4) |
| Como o `GitHubClient` (#2) sinaliza HTTP 403/204 | `pipeline/metadados.py` aceita erro como corpo (`{"message": ...}`) ou como exceção com o texto da API (em `str(e)` ou `e.response.text`); 204/corpo vazio → 0 contribuidores. Ajustar quando #2 definir suas exceções. **Definido em #10:** respostas 4xx levantam `ErroHTTP` (`.status_code`, `.response.text`, mensagem da API em `str(e)`); 404/403 (que não é cota) ficam no cache e são repetidos (mesma exceção) sem nova chamada; 204 → `Response.json = None` | A (#4) / C (#2) |
| Tempo de recuperação (RQ04): ordem dos runs, falhas iniciais e re-runs | Ordena por `created_at` (desempate por `id`) dentro de cada `workflow_id`, com runs já filtrados por `run_valido`. Segue a letra do enunciado: episódio começa na primeira falha **após um sucesso**; falhas antes do primeiro sucesso da janela não abrem episódio (início desconhecido). Censurados entram na mediana com o tempo até `fim_janela` (limite inferior) e sua proporção é reportada. Início = `run_started_at` da 1ª falha; se posterior ao fim do episódio (a API redefine `run_started_at` a cada re-run), usa-se o `created_at` da falha | C (#12) — **decidido**: mantida a regra literal do enunciado |
| Mês de workflow runs que bate o teto de 1.000 | Hoje só avisa (log) e registra o período em `RunsColetados.saturados`; o mês segue com os 1.000 runs entregues. Subdividir o mês (semanas/dias) só se o aviso aparecer na coleta real. Janela inteira com menos de 1.000 runs vem numa consulta paginada só (⌈n/100⌉ chamadas em vez de 12+); com 1.000 ou mais, mês a mês como antes (mesmos filtros, mesmos runs) | C (#9) — validar com o grupo |
| Pré-filtro da etapa “≥ 50 runs válidos” do funil | **Decidido: sem atalho por `total_count`.** A soma dos `total_count` por `status` (as 4 conclusões válidas) foi implementada e testada na API real: em 5 de 18 repositórios veio abaixo dos runs listados (até 75 % a menos; o mesmo `total_count` oscilou 1.536 → 1.254 → 1.536 em consultas seguidas), o que descartaria elegíveis e mudaria a amostra. A etapa segue contando os runs listados com `run_valido` (critério de sempre); a economia vem de listar a janela numa consulta quando ela tem menos de 1.000 runs (descartados nesta etapa custam 1 chamada em vez de 12) | A (#9, #5) |
| Concorrência da coleta | **Decidido:** `coleta.workers` (padrão 4, de 1 a 8; 1 = sequencial) threads no funil e nas coletas da amostra; a busca segue sequencial (30 req/min). O `GitHubClient` coordena cota (reservada antes de cada chamada; esgotada, todas esperam), pausas de limite secundário, ritmo de ≤ 600 req/min e ≤ `workers` requisições em voo. Resultados consumidos na ordem sorteada/da amostra: CSVs idênticos aos de `workers: 1` | A (#10) |
| Listagem de runs da API não é estável entre execuções | Na fumaça, a mesma consulta mensal (`created=2025-11-01..2025-11-30`, voyager-crew/voyager) devolveu 57 runs e, minutos depois, 101 (44 runs de 03/11 ausentes na 1ª); em outra, a página 2 repetiu 2 runs e omitiu 2. Afeta a coleta antiga e a nova igualmente; o cache congela uma resposta, então a regeneração a partir dele é reprodutível. *Ameaça (interna):* contagens de runs podem variar levemente entre coletas | A (#9) — validar com o grupo |
| Idade do repositório (`idade_dias`) | `(janela.fim − created_at)` em dias inteiros, arredondado para baixo, com `janela.fim` **exclusivo** (00:00 UTC do dia seguinte ao último dia da janela) — 1 dia a mais que usar o último dia às 00:00 | A (#4) — validar com o grupo |
| Contribuidores com `anon=true` | Conta também autores sem conta no GitHub (só e-mail); o mesmo autor com e-mails diferentes conta mais de uma vez | A (#4) — enunciado manda `anon=true` |

A janela vive **apenas em `config.yaml`** — nunca hard-coded.

---

## 2. Stack e ambiente

- **Python 3.12**, ambiente virtual em `.venv/` (`python -m venv .venv`).
- Dependências em `requirements.txt` (versões fixadas com `==`):
  - S01: `requests`, `pyyaml`, `pandas`, `pytest`, `pytest-cov`
  - S02+: `scipy`, `statsmodels`, `scikit-learn`, `matplotlib`/`seaborn`, `pymannkendall` (bônus)
- Execução única: `python -m pipeline --config config.yaml`
- Testes: `pytest --cov=metricas --cov-report=term-missing --cov-fail-under=80`
- Todas as datas são tratadas como **`datetime` com timezone UTC**. Ao ler da API: `datetime.fromisoformat(s.replace("Z", "+00:00"))`.

---

## 3. Estrutura do repositório

```
.
├── DIRETRIZES.md              # este arquivo
├── README.md                  # como rodar (o grupo replicador só lê isto!)
├── config.yaml                # janela, faixas de estrelas, limites, semente, variantes
├── requirements.txt
├── .github/workflows/testes.yml
├── pipeline/                  # coleta (acessa rede)
│   ├── __main__.py            # orquestra: python -m pipeline --config config.yaml
│   ├── config.py              # carrega/valida config.yaml          [A]
│   ├── github_client.py       # HTTP, paginação, cache, rate limit  [C]
│   ├── selecao.py             # busca de candidatos fatiada         [A]
│   ├── metadados.py           # estrelas, linguagem, contrib., idade[A]
│   ├── funil.py               # filtros + tabela do funil           [A]
│   ├── paralelo.py            # execução concorrente em ordem (#10) [A]
│   ├── releases.py            # releases e tags                     [B]
│   ├── commits.py             # compare entre releases              [B]
│   └── workflow_runs.py       # runs da janela (por mês se ≥ 1.000) [C]
├── metricas/                  # cálculo PURO (sem rede) — alvo da cobertura
│   ├── frequencia.py          # deployment frequency (RQ01)         [A]
│   ├── classificacao.py       # faixas Elite/High/Medium/Low        [A]
│   ├── lead_time.py           # variantes (a) e (b) (RQ02)          [B]
│   ├── cfr.py                 # CFR (a) [C]; CFR (b) [B, S02]
│   └── recuperacao.py         # tempo de recuperação (RQ04)         [C]
├── tests/
│   ├── conftest.py            # fixtures compartilhadas
│   ├── test_frequencia.py, test_classificacao.py, ...
│   └── pipeline/              # testes do pipeline com respostas HTTP mockadas
├── data/                      # NÃO versionado (exceto .gitkeep)
│   ├── cache/                 # respostas cruas da API
│   └── processed/             # CSVs intermediários
├── output/                    # versionado: funil.csv, repos.csv, dicionário de dados
├── analises/                  # notebooks/scripts das RQs (S03)
└── artigo/                    # fontes .tex ou rascunhos .md das seções
```

Regra de dependência: `metricas/` **nunca** importa de `pipeline/`. `pipeline/` só chama a API via `github_client.py`.

---

## 4. Definições operacionais (resumo — fonte: seção 3 do enunciado)

| Item | Regra |
|---|---|
| Janela | 12 meses, `config.yaml → janela.inicio / janela.fim`. Só entram releases e runs **criados dentro** dela. |
| Branch | Apenas `default_branch` do repositório. |
| Deploy | Release com `draft = false` e `prerelease = false`, usando `published_at`. Pré-releases e tags = variantes (RQ 07). |
| Data do commit | `commit.author.date`. |
| Runs válidos | `event = push`, branch = default, e `conclusion` ∈ {success, failure, timed_out, startup_failure}. |
| Sucesso / falha | `success` → sucesso; `failure`, `timed_out`, `startup_failure` → falha; **todo o resto é ignorado**. |
| Inclusão | ≥ **5 releases** e ≥ **50 runs válidos** na janela. |
| Censura | Nunca descartar: marcar como censurado e reportar a contagem/proporção. |
| Estatística | Sempre **mediana e IQR**, nunca média/desvio-padrão. |

Constantes (classes de `conclusion`, limites, faixas DORA) ficam definidas **em um único lugar** (`metricas/__init__.py` ou `config.yaml`) e são importadas — nunca repetidas.

---

## 5. Contratos de dados entre módulos

Estes formatos permitem que A, B e C desenvolvam em paralelo. Os módulos de `pipeline/` produzem exatamente isto; os de `metricas/` consomem exatamente isto.

### 5.1 Cliente HTTP (`pipeline/github_client.py`, dono: C)

```python
class GitHubClient:
    def __init__(self, token: str, cache_dir: Path): ...
        # extensão (#10), só keywords opcionais: max_simultaneas (teto de requisições em voo,
        # = coleta.workers no __main__) e intervalo_minimo (ritmo global entre partidas)
    def cancelar(self) -> None
        # extensão (#10): acorda as esperas e faz toda nova requisição levantar ColetaCancelada (Ctrl+C)
    def get(self, path: str, params: dict | None = None) -> Response
        # Response tem .json (dict|list) e .headers (dict); usa cache; trata rate limit e 5xx
    def get_paginated(self, path: str, params: dict | None = None, item_key: str | None = None) -> list[dict]
        # segue Link rel="next"; item_key para respostas tipo {"total_count":..,"items":[..]}
    def graphql(self, query: str, variables: dict | None = None) -> dict
        # extensão (#10): POST /graphql com o mesmo cache/backoff e cota própria; devolve `data`;
        # `errors` → ErroGraphQL. Usado nas datas das tags (1 ponto por 100 tags, em vez de 1 chamada por tag)
```

Até C entregar a versão completa, existe um **stub mínimo** (sem cache/rate limit) com a mesma assinatura, para A e B não ficarem bloqueados.

### 5.2 Registros (dicts com estas chaves; datas já convertidas para `datetime` UTC)

```python
Repo     = {"full_name": str, "default_branch": str, "stars": int, "language": str | None,
            "created_at": datetime, "contributors": int | None, "fork": bool, "archived": bool}
           # contributors None = a API não lista (403 "too large"); ver seção 1
Release  = {"tag_name": str, "published_at": datetime, "draft": bool, "prerelease": bool}
Commit   = {"sha": str, "author_date": datetime, "message": str}
Run      = {"id": int, "workflow_id": int, "event": str, "head_branch": str,
            "conclusion": str | None, "created_at": datetime,
            "run_started_at": datetime, "updated_at": datetime}
```

### 5.3 Assinaturas das funções de métricas (S01)

```python
# metricas/frequencia.py [A]
def deployment_frequency(releases: list[Release], inicio: datetime, fim: datetime,
                         incluir_prerelease: bool = False) -> float  # releases/semana

# metricas/classificacao.py [A]
def classificar_metrica(nome: str, valor: float | None) -> str | None  # "Elite"|"High"|"Medium"|"Low"
def classificacao_geral(categorias: list[str | None]) -> str | None    # mediana arredondada p/ baixo; ignora None/NaN; None se < 3 métricas
def classificar_repositorio(frequencia, lead_time, cfr, recuperacao) -> dict  # categorias + "geral"

# metricas/lead_time.py [B]
def lead_time_por_release(commits_por_release: dict[str, list[Commit]], releases: list[Release]) -> float | None  # horas
def lead_time_por_commit(commits_por_release: dict[str, list[Commit]], releases: list[Release]) -> float | None   # horas

# metricas/cfr.py [C]
def cfr_ci(runs: list[Run]) -> float | None

# metricas/recuperacao.py [C]
def episodios_recuperacao(runs: list[Run], fim_janela: datetime) -> list[dict]  # {inicio, fim, horas, censurado}
def tempo_recuperacao(runs: list[Run], fim_janela: datetime) -> dict             # {mediana_horas, n_episodios, prop_censurados}
```

Unidades: **lead time e recuperação em horas**, frequência em **releases/semana**, CFR como **fração 0–1**. Retornar `None` quando não houver dados suficientes (nunca `0` “por padrão”).

### 5.4 Arquivos de saída

| Arquivo | Dono | Conteúdo |
|---|---|---|
| `output/candidatos.csv` | A | todos os candidatos da busca + metadados |
| `output/funil.csv` | A | `etapa, n_restantes, n_descartados, motivo` |
| `output/repos.csv` | A | amostra final (100 no S01) com metadados |
| `data/processed/releases.csv`, `tags.csv`, `commits.csv` | B | releases, tags (data do commit apontado) e commits por release |
| `data/processed/releases_sem_compare.csv` | B | releases da janela sem commits calculáveis: `full_name, tag_name, motivo` (`sem_anterior`, `compare_404`, `compare_<status>`) |
| `data/processed/runs.csv` | C | runs válidos e ignorados (com coluna de classe) |
| `data/processed/runs_meses_saturados.csv` | C | `full_name, periodo` dos meses que bateram o teto de 1.000 runs (só cabeçalho = nenhum) |
| `output/dicionario_dados.md` | todos (consolida C no S02) | nome, tipo, unidade, fórmula/origem de cada coluna |

---

## 6. Sprint 1 (Lab03S01 — 5 pontos)

### 6.1 Critérios de aceite da sprint

- [ ] `python -m pipeline --config config.yaml` roda do zero e **retoma** após `Ctrl+C` sem repetir chamadas.
- [ ] Seleção de candidatos + funil registrado em `output/funil.csv`.
- [ ] 100 repositórios elegíveis com releases, commits entre releases e workflow runs na janela.
- [ ] Cache, rate limit (`X-RateLimit-Remaining/Reset`) e backoff exponencial para 5xx.
- [ ] Testes com fixtures (incluindo casos de borda) e cobertura ≥ 80 % em `metricas/`.
- [ ] CI do grupo (`.github/workflows/testes.yml`) verde no `main`.
- [ ] Artigo: introdução com **uma hipótese informal por RQ** (RQ 01–07).
- [ ] Cada integrante é Assignee de ≥ 1 Issue **com código commitado**.

### 6.2 Backlog de Issues sugerido

| # | Issue | Assignee | Depende de |
|---|---|---|---|
| 1 | Esqueleto do repo: estrutura de pastas, `config.yaml`, `config.py`, `requirements.txt`, `__main__.py` vazio, CI `testes.yml`, README inicial | **A** | — |
| 2 | Stub do `GitHubClient` (assinatura da 5.1, sem cache) | **C** | 1 |
| 3 | Seleção de candidatos: busca fatiada por faixas de estrelas (`stars:1000..1500`, …) respeitando o teto de 1.000 resultados/consulta | **A** | 2 |
| 4 | Metadados: estrelas, linguagem, idade (`created_at`), `default_branch`, contribuidores via `?per_page=1&anon=true` + cabeçalho `Link` | **A** | 2 |
| 5 | Funil: filtros em ordem de custo crescente + geração de `funil.csv` + amostra de 100 | **A** | 3, 4, 7, 9 |
| 6 | `metricas/frequencia.py` + `metricas/classificacao.py` + testes | **A** | 1 |
| 7 | Coleta de releases e tags | **B** | 2 |
| 8 | Commits entre releases via `compare` (paginado; registrar 404) | **B** | 7 |
| 9 | Coleta de workflow runs fatiada por mês (alerta se um mês bater 1.000) | **C** | 2 |
| 10 | `GitHubClient` completo: cache em disco, retomada, rate limit, backoff | **C** | 2 |
| 11 | `metricas/lead_time.py` (a) e (b) + testes | **B** | 1 |
| 12 | `metricas/cfr.py` (a) + `metricas/recuperacao.py` + testes | **C** | 1 |
| 13 | Artigo — introdução e hipóteses (A: RQ01, RQ06, RQ07 · B: RQ02, RQ05 · C: RQ03, RQ04) | **todos** (uma sub-Issue por integrante) | — |

### 6.3 Detalhamento do Integrante A

**Issue 1 — Esqueleto (fazer primeiro, desbloqueia todos).** Estrutura da seção 3, `config.yaml` com janela, faixas de estrelas, limites (5 releases / 50 runs), tamanho da amostra (100), semente; `config.py` que valida e converte datas; CI com o YAML da seção 7 do enunciado; README com “como rodar”.

**Issue 3 — Seleção.**
- `GET /search/repositories?q=stars:A..B&sort=stars` para cada faixa definida em `config.yaml`; se uma faixa retornar `total_count > 1000`, **subdividir automaticamente** a faixa.
- Deduplicar por `full_name`. Salvar `output/candidatos.csv`.

**Issue 4 — Metadados.** A busca já traz `stargazers_count`, `language`, `created_at`, `default_branch`, `fork`, `archived`. Só **contribuidores** exige chamada extra (ler o número da última página no `Link`; se não houver `Link`, contar os itens da resposta). Idade em dias = `fim_janela − created_at`.

**Issue 5 — Funil.** Ordem (da etapa mais barata para a mais cara, para economizar cota):
1. Candidatos da busca
2. Sem fork / não arquivados *(se aprovado pelo grupo)*
3. Usa GitHub Actions (`/actions/workflows` com `total_count > 0`)
4. ≥ 5 releases publicadas (não draft, não pré-release) na janela — usa coleta de B
5. ≥ 50 runs válidos no default branch na janela — usa coleta de C
6. Amostra do S01: candidatos processados em **ordem aleatória com a semente do config** até reunir 100 elegíveis

Cada etapa registra quantos saíram e o motivo em `funil.csv`. O funil deve ser regenerável a partir do cache, sem novas chamadas.

**Issue 6 — Frequência e classificação.** Implementar com TDD a partir das tabelas do enunciado (semanas da janela = dias/7 ≈ 52,1). Casos de teste mínimos: limites exatos de cada faixa (ex.: exatamente 7/semana = Elite; exatamente 15 % CFR = Elite), `None` como entrada, exemplo (4, 3, 3, 1) → High, mediana com número par arredondada para baixo (ex.: (4, 3, 2, 1) → mediana 2,5 → Medium).

---

## 7. Fluxo de trabalho no Git

- `main` protegido: só entra por **Pull Request** com CI verde e **revisão de outro integrante**.
- Branch por Issue: `feat/<n>-descricao-curta` (ex.: `feat/3-selecao-candidatos`); correções: `fix/<n>-...`; texto: `docs/<n>-...`.
- Mensagem de commit (Conventional Commits + Issue obrigatória):
  ```
  feat(selecao): fatia busca por faixas de estrelas (#3)
  test(classificacao): casos de limite das faixas DORA (#6)
  ```
- PR com `Closes #N` na descrição, descrição do que foi testado, e sem arquivos de `data/`.
- Commits pequenos e frequentes (a correção avalia a evolução semanal).

## 8. GitHub Projects

- Colunas: **Backlog → To Do (sprint) → In Progress → Review → Done**.
- **WIP:** no máximo **2 Issues “In Progress” por integrante**.
- Toda Issue: Assignee, label (`coleta`, `metricas`, `teste`, `infra`, `artigo`), milestone (`S01`, `S02`, `S03`, `Final`).
- Atualização mínima: **semanal** (mover cartões, comentar progresso). Penalidade de até 10 % da sprint se negligenciado.

## 9. Padrões de código

- Identificadores de domínio em **português** (`metricas`, `releases_validas`, `tempo_recuperacao`); termos técnicos consagrados em inglês podem ficar (`lead_time`, `cfr`, `client`).
- Type hints em funções públicas; docstring curta dizendo **unidade** do retorno.
- Sem `print` para log: usar `logging` (nível INFO para progresso da coleta).
- Nada de valores mágicos espalhados: limites e datas vêm de `config.yaml`.
- Testes de `pipeline/` **não fazem chamadas reais**: mockar o `GitHubClient` ou usar respostas JSON salvas em `tests/fixtures/`.

## 10. Instruções específicas para IAs

Ao trabalhar neste repositório, a IA deve:

1. Ler este arquivo e a seção relevante do enunciado **antes** de escrever código.
2. Perguntar qual Issue está sendo trabalhada se não estiver claro, e usar o número dela nos commits.
3. Respeitar os contratos da seção 5 e o dono de cada módulo; não editar módulo de outro integrante sem pedido explícito.
4. Escrever o teste antes (ou junto) da função em `metricas/`, usando os exemplos numéricos do enunciado como fixtures.
5. Nunca: instalar biblioteca de acesso à API do GitHub; imprimir/commitar o token; fazer coleta real em testes; alterar definições operacionais; inventar valores de janela.
6. Rodar `pytest --cov=metricas --cov-fail-under=80` antes de declarar uma tarefa concluída e mostrar o resultado.
7. Não commitar nem abrir PR sem pedido do integrante responsável.
8. Ao encontrar ambiguidade no enunciado, registrar a dúvida na seção 1 deste arquivo (ou numa Issue) em vez de decidir silenciosamente.

## 11. Definition of Done (qualquer Issue de código)

- [ ] Código segue a estrutura e os contratos deste documento
- [ ] Testes escritos e passando localmente e no CI
- [ ] Cobertura de `metricas/` ≥ 80 %
- [ ] Sem segredo, sem dados de `data/` no commit
- [ ] Commits referenciam a Issue; PR com `Closes #N` revisado por outro integrante
- [ ] README / dicionário de dados atualizados se algo novo for gerado
- [ ] Cartão movido para Done no Projects
