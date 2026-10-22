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
| Amostra-ouro: sorteio e planilhas (#29) | `config.yaml → amostra_ouro` (`tamanho: 60`, `releases_por_repo: 5`, `semente: 42`). Repositórios: `repos.csv` ordenado por `full_name` e `sample(n=60, random_state=42)` (independe da ordem do arquivo). Releases: deploys da janela (não draft, não pré-release, `releases_publicadas`), 5 por repositório com `random.Random("42:<full_name>")`; com menos de 5, todas + aviso. Cada release leva `url_release`, `tag_anterior` (mesma regra do lead time em `commits.py`: release principal publicada imediatamente antes, por `published_at` e tag, podendo ser de antes da janela) e `url_compare`. Planilhas por avaliador **sem nenhuma saída da heurística**; com rótulo ou observação preenchidos não são sobrescritas sem `--forcar`. *Atenção (monorepos):* a anterior pode ser de outro pacote (ex.: `@x/a@1.0` → `@x/b@2.0`), então o `compare` mistura pacotes; o avaliador deve se apoiar nas release notes. O sorteio é refeito quando a amostra final crescer para 300 (#27); só então as planilhas são versionadas | A (#29) — validar com o grupo |
| Amostra-ouro: concordância e consenso (#33) | Kappa de Fleiss por dimensão (`tipo_projeto`, `entregas_reais` em 60 repositórios; `corretiva` em 300 releases) com `aggregate_raters` + `fleiss_kappa` (statsmodels), usando como categorias **todos** os valores válidos da dimensão; kappa indefinido (todos os rótulos numa só categoria) é reportado como `indefinido`, nunca 0 ou 1. Interpretação de Landis & Koch com faixas fechadas à direita (0,20 = leve; 0,2000001 = razoável). **Protocolo de desempate:** 3 iguais → `unanime`; 2×1 → maioria simples (`maioria`); 1-1-1 (só em `tipo_projeto` e `entregas_reais`) → decidido em reunião do grupo e registrado em `output/amostra_ouro/desempates.csv` (`rotulo_final` + `justificativa`; `reuniao`). Decisões preenchidas nunca são apagadas ao regerar. `python -m pipeline.consenso`; ver README | A (#33) — validar com o grupo |
| Contribuidores com `anon=true` | Conta também autores sem conta no GitHub (só e-mail); o mesmo autor com e-mails diferentes conta mais de uma vez | A (#4) — enunciado manda `anon=true` |

A janela vive **apenas em `config.yaml`** — nunca hard-coded.

**Decisões operacionais da #28:** como o enunciado não exige sucessão imediata,
adotamos qualquer corretiva com publicação estritamente posterior e distância ≤ 7 dias;
uma release intermediária não encerra a busca. Cada release avaliada conta no máximo uma
falha. A antecessora usada para classificar cada candidata é a principal imediatamente
anterior por `(published_at, tag_name)`. O intervalo dos últimos 7 dias começa em
`fim_janela - 7 dias`, inclusive (fim exclusivo); todas as releases nele são censuradas,
mesmo se já houver correção observada. Essas convenções têm testes e não atribuem uma
correção específica a um defeito. Monorepos continuam seguindo a cronologia global, sem
inferir pacotes; essa limitação deve ser discutida na validação. Os detalhes da heurística
ficam nas docstrings de `metricas/cfr.py` e só devem ser consultados pelos avaliadores
após concluírem a rotulagem independente.

---

## 2. Stack e ambiente

- **Python 3.12**, ambiente virtual em `.venv/` (`python -m venv .venv`).
- Dependências em `requirements.txt` (versões fixadas com `==`):
  - S01: `requests`, `pyyaml`, `pandas`, `pytest`, `pytest-cov`
  - S02+: `scipy`, `statsmodels`, `scikit-learn`, `matplotlib`/`seaborn`, `pymannkendall` (bônus). Cada uma entra no `requirements.txt` (com `==`) só quando o código passar a usá-la; `statsmodels==0.14.4` entrou na #33; `scikit-learn==1.5.2` é usado na avaliação da heurística
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
│   ├── amostra_ouro.py        # sorteio e planilhas da validação manual (#29) [A]
│   ├── consenso.py            # kappa de Fleiss, desempates e consenso (#33) [A]
│   ├── validacao_heuristica.py # avaliação offline e histórico de versões [B]
│   ├── dataset.py             # dataset final por repositório, offline (#35) [C]
│   ├── releases.py            # releases e tags                     [B]
│   ├── commits.py             # compare entre releases              [B]
│   └── workflow_runs.py       # runs da janela (por mês se ≥ 1.000) [C]
├── metricas/                  # cálculo PURO (sem rede) — alvo da cobertura
│   ├── frequencia.py          # deployment frequency (RQ01)         [A]
│   ├── classificacao.py       # faixas Elite/High/Medium/Low        [A]
│   ├── lead_time.py           # variantes (a) e (b) (RQ02)          [B]
│   ├── cfr.py                 # CFR (a) [C]; CFR (b) [B, S02]
│   ├── concordancia.py        # kappa de Fleiss e consenso por maioria (#33) [A]
│   ├── validacao.py           # precisão, recall, F1 e contagens [B]
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

# metricas/cfr.py [B, S02, #28]
def release_corretiva(release: Release, anterior: Release | None, commits: list[Commit]) -> bool
    # heurística da release corretiva; usada pelo CFR (b) e comparada ao consenso na #34 (P/R/F1)
def cfr_entrega(releases: list[Release], commits_por_release: dict[str, list[Commit]],
                fim_janela: datetime) -> dict
    # {cfr (fração 0–1 | None), n_avaliadas, n_falharam, n_censuradas}; R falhou se seguida em ≤ 7 dias
    # por release corretiva; releases dos últimos 7 dias da janela = censuradas (fora do denominador)
    # Entrada já restrita ao início da janela; fim_janela exclusivo. Filtra drafts, pré-releases,
    # datas ausentes e publicações >= fim. Ordena por (published_at, tag_name), sem mutar a entrada.
    # n_avaliadas + n_censuradas = nº de releases principais publicadas recebidas antes de fim.
    # Nenhuma avaliável => cfr = None; avaliáveis sem falha => cfr = 0.0.

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
| `output/amostra_ouro/` | A (#29) | `sorteio_repos.csv`, `sorteio_releases.csv`, `rotulos_<A\|B\|C>_repos.csv`, `rotulos_<A\|B\|C>_releases.csv` e `LEIAME.md` (`python -m pipeline.amostra_ouro`); `concordancia.csv`, `divergencias.csv`, `desempates.csv`, `consenso_repos.csv` e `consenso_releases.csv` (`python -m pipeline.consenso`, #33); ver README |
| `output/metricas_repos.csv` | C (#35) | uma linha por repositório da amostra: metadados da RQ 06, frequência, lead time (a) e (b), CFR (a) e (b), recuperação, contagens de censura/ignoradas e classificação DORA (`python -m pipeline.dataset`, offline); colunas em `COLUNAS_DATASET` |
| `output/dicionario_dados.md` | todos (consolida C no S02) | nome, tipo, unidade, fórmula/origem de cada coluna |

### 5.5 Avaliação da heurística (dono: B)

`metricas.validacao.avaliar_classificacao(reais: list[bool], previstos: list[bool]) -> dict`
é pura; `True` representa uma release corretiva. Retorna `n_itens`,
`n_corretivas_reais`, `n_corretivas_previstas`, `vp`, `fp`, `fn`, `vn` (contagens),
`precisao`, `recall`, `f1` (frações 0–1) e `situacao`.
Usa `precision_recall_fscore_support(average="binary", pos_label=True, zero_division=0)`.
Entradas vazias, comprimentos diferentes ou valores não booleanos são erros.
`F1_MINIMO = 0.70` fica em `metricas/validacao.py`: `atingiu_meta` se F1 ≥ meta,
`refinar` abaixo dela; `sem_positivos` se o consenso não tiver corretivas (sem
evidência para validar essa classe, com métricas de denominador zero registradas como 0).

`pipeline/validacao_heuristica.py` [B] oferece
`python -m pipeline.validacao_heuristica --config config.yaml --versao v1 --descricao "Versão inicial"`.
Não usa API ou token. Exige sorteios, seis planilhas completas e consensos coerentes,
antes de executar a heurística. Lê releases e commits dos CSVs processados, preserva
a antecessora fora da janela e associa os itens por `(full_name, tag_name)`.
Commits indisponíveis entram como lista vazia e são contabilizados em `n_sem_commits`;
essa contagem não distingue compare vazio de compare não calculável.

As saídas versionadas ficam em `<caminhos.saida>/validacao_heuristica/`:
`historico.csv` agrega versões; `<versao>/resultado.json` registra descrição,
métricas, hashes dos dados e código, versão do scikit-learn e meta;
também registra `n_repositorios` (inteiro), `janela_inicio` e
`janela_fim_exclusivo` (datas ISO 8601 UTC). `<versao>/codigo.json` preserva
o código exato da heurística, do cálculo das métricas e do comando.
`relatorio.md` reúne todas as tentativas em uma tabela para o artigo, com
contagens de erros, limitações e aviso quando os dados mudam entre versões.
`<versao>/comparacao.csv` contém `full_name`, `tag_name`, `corretiva_consenso`,
`corretiva_prevista` (`sim`/`não`), `acertou`, `sem_commits` (booleanos).
Uma versão registrada não pode ser reutilizada com resultado, dados, código,
dependência ou descrição diferentes; repetir entradas idênticas é idempotente.
O README explica as colunas e os códigos de saída. Refinamentos e seus F1 devem
ser relatados no artigo; não há refinamento automático nem resultados inventados.

---

## 6. Sprints

> Sprint 1 (Lab03S01, 5 pontos): seções 6.1 a 6.3. Sprint 2 (Lab03S02, 5 pontos): seções 6.4 a 6.8.

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

### 6.4 Sprint 2: critérios de aceite (enunciado, seção 10)

- [ ] Amostra final com **≥ 300 repositórios** após os filtros, com `output/funil.csv` e `output/repos.csv` atualizados.
- [ ] Métricas calculadas em **todas as variantes obrigatórias**: frequência; lead time (a) e (b); CFR (a) e (b); recuperação com censura.
- [ ] Dataset final em CSV + **dicionário de dados** (`output/dicionario_dados.md`).
- [ ] **Validação manual:** amostra-ouro de 60 repositórios, rótulos independentes dos 3, kappa de Fleiss, consenso e precisão/recall/F1 da heurística de release corretiva (F1 ≥ 0,70 ou refinamento documentado).
- [ ] Artigo: **seção de metodologia** completa (`artigo/02-metodologia.md`).
- [ ] Cada integrante é Assignee de ≥ 1 Issue **com código commitado** (a rotulagem sozinha não conta como código).

### 6.5 Sprint 2: Issues (milestone `S02`)

| # | Issue | Assignee | Depende de | Situação em 13/10/2026 |
|---|---|---|---|---|
| 27 | Coleta completa: amostra final ≥ 300 | **C** | nenhuma | a fazer |
| 28 | CFR (b) + heurística de release corretiva + testes | **B** | nenhuma | a fazer |
| 29 | Amostra-ouro: sorteio de 60 repos e planilhas | **A** | 27 (para o sorteio final) | **feito** (PR #37); refazer o sorteio após a #27 |
| 30 / 31 / 32 | Rotulagem independente: avaliador A / B / C | A / B / C | 29 rodado sobre os 300 | a fazer |
| 33 | Kappa de Fleiss e consenso | **A** | 30–32 (para os números) | código pronto (PR #39); roda quando houver rótulos |
| 34 | Precisão/recall/F1 da heurística × consenso | **B** | 28, 33 | a fazer |
| 35 | Dataset de métricas por repositório + dicionário de dados | **C** | 27, 28 | a fazer |
| 36 | Artigo: metodologia | todos | 27, 33, 34 | rascunho (PR #38) com `<preencher …>` |

Caminho crítico: **#27 → #29 (re-sorteio) → #30–#32 → #33 → #34 → #36**. A #27 é a mais urgente, porque sem ela ninguém começa a rotular.

### 6.6 Sprint 2: o que cada integrante precisa fazer

**C (gnvr29): #27, #35, #32**
1. **#27:** em `config.yaml`, `amostra.tamanho: 300`; rodar `python -m pipeline --config config.yaml`. Os 100 do S01 continuam como prefixo da ordem sorteada e o cache local é reaproveitado. Estimativa: 20 a 30 mil requisições REST, ou seja, 4 a 7 h de cota (3 a 5 h com o cache do S01). Deixar rodando à noite; `Ctrl+C` e rodar de novo retoma. Commitar `output/funil.csv`, `output/repos.csv` e `output/candidatos.csv`; conferir `runs_meses_saturados.csv` e `releases_sem_compare.csv` e registrar as contagens na Issue (vão para a metodologia).
2. **Compartilhar o cache** (`data/cache/` compactado) com o grupo como anexo de uma release do repositório (ex.: tag `cache-s02`) ou por link do Drive. **Não** versionar no Git, por causa do tamanho e da replicação cruzada.
3. **Avisar o grupo** quando a #27 terminar, para A refazer o sorteio da amostra-ouro (#29).
4. **#35:** aplicar `metricas/` à amostra e gerar o CSV final por repositório (todas as variantes, contagens de censura e de releases ignoradas, metadados da RQ 06) + `output/dicionario_dados.md`. Depende do CFR (b) de B (#28).

**B (JoaquimGCVS): #28, #34, #31**
1. **#28:** implementar a heurística de release corretiva e o CFR (b) em `metricas/cfr.py`, seguindo a proposta de contrato da seção 5.3 (se mudar algo, atualizar o contrato). TDD com os exemplos do enunciado (`v2.3.0 → v2.3.1` falhou; `v2.4.0 → v2.5.0` não). **Não mostrar a heurística a ninguém antes de os três terminarem a rotulagem**, nem rodá-la sobre a amostra-ouro antes disso.
2. **#34:** depois do consenso (#33), comparar `release_corretiva` com a coluna `corretiva` de `output/amostra_ouro/consenso_releases.csv` usando `precision_recall_fscore_support`. Se o F1 ficar abaixo de 0,70, refinar e reavaliar; registrar cada versão e seu F1 (vai para a metodologia).
3. **Monorepos:** a release "anterior" pode ser de outro pacote (ver a decisão da #29 na seção 1). Isso afeta o lead time (B); avaliar se é preciso tratar e levar ao grupo.

**A (VitorCostaVianna): #29, #33, #30, #36**
1. Após a #27: rodar `python -m pipeline.amostra_ouro --config config.yaml` sobre os 300, commitar `output/amostra_ouro/` (sorteio, 6 planilhas vazias e LEIAME) e avisar B e C.
2. Após a rotulagem: rodar `python -m pipeline.consenso --config config.yaml`, conduzir a reunião dos casos `1-1-1` (`desempates.csv`), commitar as saídas e preencher kappa e consenso na metodologia.
3. Consolidar a metodologia (#36) com os números de C e o F1 de B.

**Todos: rotulagem (#30, #31, #32).** Ver 6.7.

### 6.7 Rotulagem da amostra-ouro: passo a passo (cada avaliador)

1. Depois que A commitar as planilhas sobre os 300 repositórios, faça `git pull` e abra **só a sua** planilha: `output/amostra_ouro/rotulos_<X>_repos.csv` e `rotulos_<X>_releases.csv` (X = A, B ou C). Leia o `output/amostra_ouro/LEIAME.md`.
2. Rotule **sem consultar os colegas e sem ver a heurística** (#28): nem o código, nem a saída. Não abra as planilhas dos outros.
3. Preencha:
   - `_repos` (60 linhas): `tipo_projeto` ∈ {`biblioteca/framework`, `aplicação/serviço`, `ferramenta CLI`, `outro`} e `entregas_reais` ∈ {`sim`, `não`, `incerto`}, lendo o README e a página de releases (`url_repo`, `url_releases`).
   - `_releases` (300 linhas): `corretiva` ∈ {`sim`, `não`}, lendo as release notes (`url_release`) e os commits desde a anterior (`url_compare`).
   - `observacoes`: texto livre e opcional, para casos duvidosos.
4. Salve como **CSV UTF-8** (Google Planilhas: Arquivo → Fazer download → CSV; Excel: "CSV UTF-8 (delimitado por vírgulas)"). O "CSV" comum do Excel não é UTF-8 e é recusado; `;` como separador é aceito.
5. Commite só o seu arquivo, na sua Issue (ex.: `docs(rotulos): rótulos do avaliador B (#31)`), em PR próprio. Não edite planilhas de outro avaliador.
6. Com os três PRs mergeados, A roda o consenso (#33). Os casos `1-1-1` são decididos em reunião e registrados em `desempates.csv`.

### 6.8 Comandos da Sprint 2

```bash
python -m pipeline --config config.yaml               # coleta / funil / amostra (C, #27)
python -m pipeline.amostra_ouro --config config.yaml  # sorteio + planilhas (A, #29); --forcar descarta rótulos
python -m pipeline.consenso --config config.yaml      # kappa, divergências, desempates, consenso (A, #33)
python -m pipeline.dataset --config config.yaml       # dataset final de métricas por repositório (C, #35)
pytest --cov=metricas --cov-fail-under=80             # antes de qualquer PR
```

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
- Merge do PR por **squash** (`gh pr merge --squash`). O título do PR vira o commit na `main`, então ele também leva `(#N)`.

## 8. GitHub Projects

- Quadro: GitHub Projects da organização `lab-medicao-experimentacao` (projeto nº 3, `lab03-metricas-DORA`).
- Colunas (campo Status): **Backlog → Ready → In progress → In review → Done**. Issue sem dependência pendente vai para Ready; ao abrir o PR, para In review; ao mergear, para Done.
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
9. **Amostra-ouro (S02):** por decisão do grupo com o professor, a IA pode preencher a planilha do avaliador que pedir (`output/amostra_ouro/rotulos_<X>_*.csv`). Nunca abrir as planilhas dos outros avaliadores antes do consenso, nunca usar a saída da heurística de release corretiva (#28) como insumo e nunca rodar `amostra_ouro --forcar` sem pedido explícito, porque ele descarta rótulos. Nunca commitar rótulos sintéticos de teste fora de `tests/`.
10. Não abrir Issues nem registrar o link do Projects sem pedido do integrante.
11. Ao delegar a subagentes, dividir a Issue em tarefas de escopo fechado (contrato/API exata, arquivos que podem ser tocados, critérios de aceite, relatório curto), em vez de um agente que faz tudo.
12. Antes de começar, conferir na seção 6.5 a situação das Issues da sprint e quem é o dono de cada uma.

## 11. Definition of Done (qualquer Issue de código)

- [ ] Código segue a estrutura e os contratos deste documento
- [ ] Testes escritos e passando localmente e no CI
- [ ] Cobertura de `metricas/` ≥ 80 %
- [ ] Sem segredo, sem dados de `data/` no commit
- [ ] Commits referenciam a Issue; PR com `Closes #N` revisado por outro integrante
- [ ] README / dicionário de dados atualizados se algo novo for gerado
- [ ] Cartão movido para Done no Projects
