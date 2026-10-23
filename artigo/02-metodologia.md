# 2. Metodologia

> Rascunho em Markdown da seção de Metodologia (Lab03S02, Issue #36). A versão final vai para o template SBC.
> Trechos marcados com `<preencher …>` dependem da coleta completa (#27), da heurística de release corretiva (#28/#34) ou da validação manual (#33) e são completados quando esses resultados existirem.
>
> Revisão pelos três integrantes.

Esta seção descreve a fonte dos dados, a seleção dos repositórios, a coleta, as definições operacionais usadas para aproximar as métricas DORA, o protocolo de validação manual e os métodos estatísticos. Todas as escolhas seguem as definições comuns da disciplina; os parâmetros do estudo (janela, faixas de estrelas, critérios de inclusão, tamanho da amostra e semente aleatória) ficam num único arquivo de configuração versionado (`config.yaml`), e todo o pipeline é executado com um único comando (`python -m pipeline --config config.yaml`).

## 2.1 Fonte de dados

Os dados vêm da API REST do GitHub e, para as datas das tags, da API GraphQL, acessadas por um cliente HTTP próprio (sem bibliotecas prontas de acesso à API). O estudo considera repositórios públicos com mais de 1.000 estrelas que usam GitHub Actions. De cada repositório são coletados:

- **metadados**: estrelas, linguagem principal, data de criação, *default branch* e número de contribuidores;
- **releases**: `tag_name`, `published_at`, `draft` e `prerelease`;
- **tags** e a data de autoria do commit apontado por cada uma (variante da RQ 07);
- **commits entre releases consecutivas**, obtidos pelo endpoint `compare`, com a data de autoria (`commit.author.date`) e a mensagem;
- **workflow runs** do default branch disparados por `push`, com `workflow_id`, `conclusion`, `created_at`, `run_started_at` e `updated_at`.

## 2.2 Janela de observação

A janela de observação tem 12 meses, de **1º de outubro de 2025 a 30 de setembro de 2026** (dias inclusivos, UTC). Só entram nos cálculos releases publicadas e workflow runs criados dentro dela. A janela foi escolhida fechada e anterior à coleta, de modo que releases e runs da janela não mudam entre execuções do pipeline (exceto por exclusões ou edições feitas pelos próprios projetos), o que torna a coleta reprodutível. A janela tem 365 dias, ou seja, ≈ 52,1 semanas.

## 2.3 Seleção dos repositórios

A seleção é feita em etapas de custo crescente, e cada etapa registra quantos repositórios restaram e por que os demais foram descartados (Tabela 1).

1. **Busca de candidatos.** A busca do GitHub devolve no máximo 1.000 resultados por consulta; por isso, ela é fatiada por faixas de estrelas (1.000–1.499, 1.500–1.999, 2.000–2.999, 3.000–4.999, 5.000–9.999, 10.000–19.999, 20.000–49.999 e ≥ 50.000), e as faixas que ainda excedem o teto são subdivididas automaticamente. A consulta inclui forks explicitamente (`fork:true`), para que sua exclusão seja contada na etapa seguinte em vez de ocorrer de forma silenciosa.
2. **Exclusão de forks e repositórios arquivados**, a partir dos campos da própria busca (sem custo de API).
3. **Ordem aleatória.** Os candidatos restantes são embaralhados com semente fixa (42) **antes** de qualquer outro dado ser consultado, e avaliados nessa ordem até que a amostra atinja o tamanho desejado. Os repositórios avaliados formam, assim, uma amostra aleatória simples dos candidatos, e as proporções de descarte das etapas seguintes estimam as da população. Avaliar todos os candidatos custaria uma consulta por repositório a dezenas de milhares de repositórios (dias de cota da API) sem alterar a amostra final.
4. **Uso de GitHub Actions**: repositórios cujo endpoint de workflows informa `total_count = 0` são descartados antes de qualquer outra coleta.
5. **Critério mínimo de inclusão**: pelo menos **5 releases** publicadas (não draft e não pré-release) e pelo menos **50 workflow runs válidos** (Seção 2.5) no default branch, dentro da janela.

**Tabela 1 – Funil de seleção.** As contagens das etapas 1 e 2 são absolutas; as das etapas 4 e 5 referem-se aos repositórios avaliados na ordem aleatória.

| Etapa | Restantes | Descartados | Motivo do descarte |
|---|---:|---:|---|
| Candidatos da busca | 66.219 | – | – |
| Sem fork e não arquivados | 60.083 | 6.136 | forks: 773; arquivados: 5.363 |
| Avaliados em ordem aleatória | 2.338 | 57.745 | não avaliados (amostra completada antes) |
| Acessíveis na API | 2.336 | 2 | erro HTTP definitivo (404: 1; 422: 1) |
| Usam GitHub Actions | 1.346 | 990 | sem workflows |
| ≥ 5 releases na janela | 407 | 939 | menos de 5 releases publicadas |
| ≥ 50 runs válidos na janela | 300 | 107 | menos de 50 runs válidos |
| **Amostra final** | **300** | | |

Dos 2.338 avaliados, 12,8% foram elegíveis. A maior perda ocorre no critério de releases: só 30,2% dos que usam GitHub Actions publicaram pelo menos 5 releases na janela, enquanto 73,7% destes também tinham pelo menos 50 runs válidos. A proporção de elegíveis é próxima à da amostra-piloto de 100 repositórios do Lab03S01 (100 de 771 avaliados, ≈ 13%), cujos 100 repositórios são os primeiros da mesma ordem aleatória e estão contidos na amostra final.

## 2.4 Coleta

O pipeline armazena cada resposta da API em disco (um arquivo JSON comprimido por requisição), de modo que uma coleta interrompida por limite de requisições, falha de rede ou interrupção manual é retomada de onde parou, sem repetir chamadas. O cliente lê os cabeçalhos `X-RateLimit-Remaining` e `X-RateLimit-Reset` e espera a renovação da cota quando ela acaba; respostas 5xx e falhas de rede são repetidas com *backoff* exponencial (1 s, 2 s, 4 s, 8 s…). As requisições são feitas em paralelo por um número fixo de *threads*, e os resultados são gravados na ordem da amostra, de modo que os arquivos gerados não dependem do grau de paralelismo.

Alguns cuidados específicos de cada endpoint:

- **Workflow runs.** Com filtros, a API devolve no máximo 1.000 runs por consulta. Quando a janela inteira tem menos de 1.000 runs, ela é consultada de uma vez; caso contrário, mês a mês, e cada mês que ainda atinge o teto é registrado. Na amostra final, 24 dos 300 repositórios tiveram ao menos um mês saturado, somando 126 meses (5 repositórios ficaram saturados nos 12 meses da janela); nesses repositórios, a contagem de runs pode estar incompleta, e o número de meses saturados acompanha cada repositório no conjunto de dados.
- **Commits de cada release.** Cada release da janela é comparada com a release publicada imediatamente anterior (que pode estar fora da janela), com paginação completa do `compare`. Releases sem release anterior (a primeira da história do repositório) ou cujo `compare` falha (404 por tag apagada ou reescrita, 422 ou erro persistente) ficam fora do cálculo de lead time e são contabilizadas por motivo. Das 11.088 releases principais publicadas na janela, 71 não tinham release anterior, 45 (em 11 repositórios) tiveram `compare` com 404 e 11 (em 1 repositório) falharam com outro erro; outras 2.461 tiveram comparação sem nenhum commit. O lead time é calculado sobre as 8.500 releases restantes, com ao menos um commit.
- **Tags.** A REST não informa a data das tags; a data de cada tag é a data de autoria do commit apontado por ela, obtida pela API GraphQL (seguindo tags anotadas até o commit).
- **Contribuidores.** Contados com `anon=true` a partir do número da última página de `contributors?per_page=1`; quando a API se recusa a listar (históricos muito grandes), o valor fica ausente e o repositório sai apenas das análises desse fator.
- **Idade do repositório.** Dias inteiros entre `created_at` e o fim da janela.

## 2.5 Definições operacionais

Como o GitHub não registra deploys nem falhas em produção, as métricas DORA são aproximadas por *proxies*:

| Conceito | Definição operacional |
|---|---|
| Deploy | Release publicada (`draft = false`, `prerelease = false`), datada por `published_at` |
| Data de um commit | `commit.author.date` |
| Branch | Apenas o *default branch* |
| Runs considerados | `event = push` no default branch |
| Sucesso / falha | `conclusion = success` → sucesso; `failure`, `timed_out`, `startup_failure` → falha; demais valores (`cancelled`, `skipped`, `neutral`, `action_required`, `stale` ou vazio) são ignorados |
| Censura | Medição cujo evento final não ocorre dentro da janela; nunca descartada, sempre contabilizada |

A partir delas, as métricas de cada repositório são:

- **Deployment frequency (RQ 01):** nº de releases da janela ÷ 52,1 semanas, em releases por semana.
- **Lead time for changes (RQ 02), em horas**, em duas variantes. Para cada release R, os commits incluídos são os do `compare` entre a release anterior e R. *(a) por release:* `published_at(R) − data do commit mais antigo de R`, e o valor do repositório é a mediana entre suas releases; *(b) por commit:* cada commit contribui com `published_at(R) − data do commit`, e o valor do repositório é a mediana de todos os commits de todas as releases.
- **Change failure rate (RQ 03), como fração**, em duas variantes. *(a) proxy de CI:* runs com falha ÷ (falhas + sucessos). *(b) proxy de entrega:* uma release falhou se for seguida, em até 7 dias, por uma **release corretiva**; o CFR é o nº de releases que falharam ÷ nº de releases avaliadas. Releases publicadas nos últimos 7 dias da janela não podem ser avaliadas e ficam fora do denominador (censura). A heurística usada no dataset e em todas as análises apresentadas é a **v1**: uma release principal é corretiva quando alguma mensagem de commit contém a palavra inteira *fix*, *revert* ou *hotfix* (sem distinção de caixa), ou quando apenas o patch aumenta entre tags SemVer estáveis com o mesmo major/minor (prefixo `v` e metadados de build opcionais). As versões v2 e v3 foram avaliadas posteriormente na amostra-ouro (Seção 2.7), mas não foram aplicadas ao dataset nem às análises desta entrega.
- **Tempo de recuperação (RQ 04), em horas.** Dentro de cada workflow, as execuções válidas são ordenadas por `created_at`. Um episódio de falha começa na primeira falha após um sucesso e termina no próximo sucesso do mesmo workflow; sua duração é `updated_at` do sucesso − `run_started_at` da primeira falha. Falhas anteriores ao primeiro sucesso da janela não abrem episódio, porque seu início é desconhecido. Quando um *re-run* faz o `run_started_at` da falha ficar posterior ao fim do episódio, usa-se o `created_at` da falha. Episódios que não terminam até o fim da janela são **censurados**: entram na mediana com a duração até o fim da janela (um limite inferior), e a proporção de censurados é reportada por repositório. O valor do repositório é a mediana dos episódios de todos os seus workflows.

## 2.6 Classificação DORA e análise de sensibilidade

Cada métrica é classificada em Elite, High, Medium ou Low pelos cortes fixos adotados na disciplina (Tabela 2), em que "1 por mês" corresponde a 12 ÷ (365,25 / 7) ≈ 0,23 release por semana.

**Tabela 2 – Faixas de desempenho DORA usadas no estudo.**

| Métrica | Elite | High | Medium | Low |
|---|---|---|---|---|
| Deployment frequency | ≥ 7/semana | ≥ 1 e < 7/semana | ≥ 1/mês e < 1/semana | < 1/mês |
| Lead time (mediana) | < 1 dia | 1 dia a < 1 semana | 1 semana a < 30 dias | ≥ 30 dias |
| Change failure rate | ≤ 15% | > 15% e ≤ 30% | > 30% e ≤ 45% | > 45% |
| Tempo de recuperação (mediana) | < 1 hora | 1 hora a < 1 dia | 1 dia a < 1 semana | ≥ 1 semana |

A classificação geral atribui 4, 3, 2 e 1 pontos a Elite, High, Medium e Low e toma a mediana das quatro notas, arredondada para baixo. Quando uma métrica não pode ser calculada (por exemplo, tempo de recuperação de um repositório sem nenhuma falha), ela é ignorada e a mediana é tomada sobre as demais, desde que restem pelo menos três; com duas ou menos, o repositório fica sem classificação geral. Descartar todo repositório com alguma métrica ausente enviesaria a amostra, porque a ausência de tempo de recuperação ocorre justamente nos repositórios mais estáveis. O número de repositórios classificados com três métricas e sem classificação é reportado.

Para a RQ 07, a classificação é repetida sob diferentes combinações de definições operacionais: três combinações, registradas em `config.yaml`: **C1** (referência) usa a release como unidade de deploy, o lead time por release (a) e o CFR por proxy de CI (a); **C2** usa release e pré-release, o lead time por commit (b) e o CFR por proxy de entrega (b); **C3** usa a tag, o lead time (b) e o CFR (a). O tempo de recuperação é o mesmo nas três. Na variante por tags, a data de cada deploy é a data de autoria do commit apontado pela tag, porque a API não informa quando a tag foi criada. A unidade de deploy altera, na prática, só a frequência: a comparação de commits (API *compare*) foi coletada apenas entre releases principais, de modo que o lead time e o CFR (b) de C2 e C3 continuam calculados sobre as releases principais. A diferença entre as combinações vem, portanto, sobretudo das variantes (a) e (b) das duas métricas, e esse limite é retomado nas ameaças à validade.

## 2.7 Validação manual (amostra-ouro)

Para estimar o quanto os proxies e a heurística de release corretiva concordam com o julgamento humano, foi construída uma amostra-ouro:

1. **Sorteio.** 60 repositórios são sorteados da amostra final com semente fixa (42), após ordenar a amostra por nome, de forma que o sorteio não dependa da ordem dos arquivos. De cada repositório sorteado, 5 releases da janela (não draft e não pré-release) são sorteadas com uma semente derivada da semente global e do nome do repositório, totalizando 300 releases. Em 2 delas não há release anterior (a primeira release do repositório), e a planilha não traz o link de comparação; nesses casos, o avaliador decide pelas *release notes*.
2. **Rotulagem independente.** Os três integrantes rotulam, cada um na sua planilha, sem consultar os demais e sem ver a saída da heurística: (i) o **tipo do projeto** (biblioteca/framework, aplicação/serviço, ferramenta CLI ou outro); (ii) se as releases do repositório **representam entregas reais ao usuário** (sim, não ou incerto); e (iii) para cada uma das 5 releases, se ela é **corretiva** (sim ou não), a partir das *release notes* e dos commits. As planilhas são geradas automaticamente com links para a página do repositório, de cada release e da comparação com a release anterior. Em monorepos, a release anterior pode pertencer a outro pacote, e a comparação mistura commits de pacotes diferentes; nesses casos, os avaliadores se apoiam nas *release notes*.
3. **Concordância.** A concordância entre os três avaliadores é medida, em cada dimensão, pelo kappa de Fleiss, que desconta a concordância esperada por acaso, interpretado segundo Landis e Koch (1977). Quando todos os rótulos de uma dimensão caem na mesma categoria, o kappa é indefinido e é reportado como tal. No tipo do projeto, a concordância observada foi de 85,0 % e κ = 0,845; nas releases corretivas, de 88,3 % e κ = 0,828, ambas na faixa "quase perfeita". Nas entregas reais, os três avaliadores marcaram "sim" nos 60 repositórios: a concordância é total, mas o kappa é indefinido, e a dimensão não distingue os repositórios da amostra.
4. **Consenso.** Itens com os três rótulos iguais recebem esse rótulo; itens com dois rótulos iguais recebem o da maioria; itens com três rótulos diferentes (possíveis apenas no tipo do projeto e nas entregas reais) são decididos em reunião do grupo, e a decisão e sua justificativa ficam registradas no repositório. No tipo do projeto, 51 repositórios tiveram rótulos unânimes, 8 foram decididos por maioria e 1 (`s3ql/s3ql`) recebeu três rótulos diferentes e foi decidido em reunião como ferramenta CLI, porque o uso se dá por comandos de linha (`mount.s3ql`, `fsck.s3ql`, `mkfs.s3ql`); nas entregas reais, os 60 foram unânimes; nas releases, 265 foram unânimes e 35 decididas por maioria, resultando em 103 corretivas e 197 não corretivas.
5. **Avaliação da heurística (#34).** Depois de concluídos os rótulos e o consenso, foram avaliadas 300 releases de 60 repositórios, com 103 corretivas e 197 não corretivas no consenso. A classe positiva é a release corretiva; precisão, *recall* e F1 foram calculados com `precision_recall_fscore_support(average="binary", pos_label=True, zero_division=0)`, do scikit-learn 1.5.2. Os commits foram obtidos do arquivo `commits-s02.csv.gz` da release `commits-s02` deste repositório e lidos em fluxo, sem alterar os rótulos humanos. As três versões usaram exatamente as mesmas entradas (hash registrado em `output/validacao_heuristica/`).

**Tabela 3 – Todas as versões avaliadas da heurística corretiva.**

| Versão | Regra e motivo do refinamento | Precisão | Recall | F1 |
|---|---|---:|---:|---:|
| v1 | Regra inicial: qualquer mensagem com *fix/revert/hotfix* ou aumento de patch SemVer. A presença de uma correção isolada e patches de manutenção geraram muitos falsos positivos. | 0,3755 | 0,9515 | 0,5385 |
| v2 | Maioria estrita de títulos corretivos entre commits informativos, excluindo merges e manutenção explícita; patch apenas sem commits. Melhorou a precisão, mas perdeu correções descritas sem palavras-chave. | 0,6667 | 0,4466 | 0,5349 |
| v3 | Mantém a maioria estrita quando há funcionalidades explícitas; sem elas, aceita título corretivo ou aumento de patch no mesmo namespace. Amplia os marcadores de manutenção e reconhece tags prefixadas. | 0,6818 | 0,7282 | **0,7042** |

A v3 atingiu F1 ≥ 0,70 na amostra-ouro, sem arredondamento na decisão (F1 = 0,704225352112676), mas **não foi adotada nas análises desta entrega**. Foram 75 verdadeiros positivos, 35 falsos positivos, 28 falsos negativos e 162 verdadeiros negativos; a heurística marcou 110 releases como corretivas. Há 17 releases sem commits disponíveis, mantidas na avaliação: essa contagem não distingue comparações vazias das indisponíveis. Os resultados completos, comparações por release e código exato de cada versão estão preservados no [relatório da validação](../output/validacao_heuristica/relatorio.md).

**Decisão para esta entrega.** Por restrição de prazo, o grupo mantém o dataset, as tabelas, os gráficos e as análises já produzidos com a **v1**. Aplicar v2 ou v3 exigiria recalcular o CFR (b) nos repositórios, regenerar o dataset e as análises afetadas (RQ03, RQ05, RQ06 e RQ07) e revisar os resultados e a discussão; não há tempo disponível para concluir esse ciclo antes da entrega. As versões refinadas ficam registradas como experimentos posteriores de validação, sem atribuir seu desempenho aos resultados existentes. A versão efetivamente usada (v1) obteve precisão de **0,3755**, recall de **0,9515** e F1 de **0,5385**, abaixo da meta de 0,70, com 163 falsos positivos na amostra-ouro. Essa limitação pode inflar a identificação de releases corretivas e afeta a interpretação do CFR (b), de suas associações e da análise de sensibilidade. O F1 de 0,7042 da v3 não valida os valores calculados com a v1.

O refinamento e a avaliação usaram a mesma amostra-ouro, sem conjunto de teste independente; portanto, o F1 pode ser otimista para outros projetos. A meta foi atingida por pequena margem e permanecem 63 erros. Títulos podem descrever o objetivo de forma incompleta, palavras-chave podem confundir funcionalidades e correções, e mudanças apenas em dependências podem resolver defeitos reais sem serem reconhecidas. Em monorepos, a cronologia global pode comparar pacotes distintos; exigir prefixos iguais evita usar essas tags como evidência de patch, mas não elimina a mistura de commits. A validação mede concordância com o consenso humano sobre releases corretivas, sem comprovar falhas em produção.

O tipo do projeto obtido no consenso é usado como fator na RQ 06 (restrito aos 60 repositórios rotulados), e os resultados da validação apoiam a discussão das ameaças à validade.

## 2.8 Análise estatística

As distribuições das métricas de repositórios de software costumam ser muito assimétricas; por isso, todas as métricas são resumidas por **mediana e intervalo interquartil (IQR)**, e só são usados métodos não paramétricos:

- **RQ 05:** correlação bilateral de Spearman (ρ, p-valor aproximado e n) entre deployment frequency e cada variante do CFR. Os pares completos são selecionados separadamente, sem imputação, e os p-valores não são ajustados entre as duas variantes. As dispersões usam frequência em escala logarítmica, pois todas as frequências são positivas; o CFR é exibido em percentual, preservando a fração no cálculo. A aproximação do p-valor exige cautela para a amostra de 300 repositórios, menor que as >500 observações indicadas pela documentação do SciPy para maior precisão.
- **RQ 06:** comparação de seis variantes (frequência, lead time a/b, CFR a/b e recuperação) entre grupos de quatro fatores: estrelas, contribuidores, idade e tipo de projeto. Os três fatores numéricos são agrupados por quartis antes das exclusões por métrica, sem separar empates; cortes repetidos são removidos. Tipo de projeto usa as categorias de consenso presentes no dataset, incluindo `outro`, restritas aos 60 repositórios rotulados. Ausências são excluídas por fator × métrica, sem imputação; cada grupo precisa de pelo menos cinco observações válidas. Usa-se Kruskal-Wallis para três ou mais grupos (ε² = H / (n − 1)) ou, com dois grupos, Mann-Whitney bilateral assintótico com correção de empates e continuidade (δ de Cliff = 2U₁/(n₁n₂)−1, com grupos em ordem lexicográfica). Os p-valores de todos os testes calculáveis são corrigidos juntos por Holm, com α = 0,05; a execução real tem 24 testes viáveis. Reportam-se n, mediana, Q1, Q3 e IQR por grupo, estatísticas, p-valores brutos e corrigidos e tamanhos de efeito. Não há testes post hoc; testes inviáveis preservam o motivo e não recebem p-valor inventado. Limites, membros e exclusões ficam nas saídas reproduzíveis da análise.
- **RQ 07:** para cada par de combinações de definições, a proporção de repositórios que mudam de categoria geral (separando mudanças para categorias adjacentes e saltos de duas ou mais) e o kappa de Cohen com ponderação linear, que penaliza menos as trocas entre categorias adjacentes, interpretado pelas faixas de Landis e Koch. Um repositório sem categoria geral em alguma das duas combinações fica fora da proporção e do kappa do par e é contado à parte; cada par tem uma matriz de transição entre categorias. Para localizar o que move a categoria geral, repete-se a comparação em cada métrica (frequência, lead time e CFR).

As análises são feitas em Python com pandas, SciPy, statsmodels e scikit-learn, a partir dos CSVs gerados pelo pipeline; cada coluna desses arquivos está descrita no dicionário de dados do repositório (`output/dicionario_dados.md`).

## Referências

- Forsgren, N., Humble, J. e Kim, G. (2018). *Accelerate: The Science of Lean Software and DevOps*. IT Revolution Press.
- DORA. *DORA's software delivery metrics: the four keys*. https://dora.dev/guides/dora-metrics-four-keys/
- Landis, J. R. e Koch, G. G. (1977). The measurement of observer agreement for categorical data. *Biometrics*, 33(1), 159–174.
- Romano, J. et al. (2006). Appropriate statistics for ordinal level data: Should we really be using t-test and Cohen's d for evaluating group differences on the NSSE and other surveys? *Annual Meeting of the Florida Association of Institutional Research*.
