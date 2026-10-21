# Lab03 — Mineração de Métricas DORA

Este projeto estuda como repositórios open-source entregam mudanças e lidam com
falhas. Para isso, coleta releases, commits e execuções do GitHub Actions e usa
esses dados para calcular aproximações das quatro métricas DORA: frequência de
entrega, lead time, taxa de falha das mudanças e tempo de recuperação.

Esses dados são evidências indiretas. Publicar uma release não comprova uma
implantação em produção, assim como uma falha de CI não comprova um problema para
o usuário. A validação manual ajuda a avaliar essas limitações e a comparar a
identificação automática de releases corretivas com o julgamento humano.

O [enunciado do trabalho](./03%20-%20Mineração%20de%20Métricas%20DORA.md) define as
regras do estudo. As [diretrizes do grupo](./DIRETRIZES.md) documentam os contratos
de dados e as decisões de implementação.

## Preparar o ambiente

É necessário ter Python 3.12 ou mais recente e um token do GitHub para consultar
a API. Para a coleta de dados públicos, pode ser usado um token sem escopos.
Consulte as [instruções para criar um token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
se ainda não tiver um.

Na raiz do repositório, crie um ambiente virtual:

```bash
python -m venv .venv
```

Ative esse ambiente com o comando correspondente ao seu sistema.

Linux ou macOS:

```bash
source .venv/bin/activate
```

Windows, no PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Com o ambiente ativo, instale as dependências:

```bash
python -m pip install -r requirements.txt
```

O pipeline lê o token da variável `GITHUB_TOKEN`. Defina-a no terminal em que vai
executar a coleta, substituindo o valor de exemplo pelo seu token.

Linux ou macOS:

```bash
export GITHUB_TOKEN="seu_token"
```

Windows, no PowerShell:

```powershell
$env:GITHUB_TOKEN = "seu_token"
```

Como alternativa, crie um arquivo `.env` na raiz do repositório:

```dotenv
GITHUB_TOKEN=seu_token
```

O pipeline carrega esse arquivo automaticamente. Se a variável já estiver definida
no terminal, ela terá preferência. O `.env` está no `.gitignore`; mantenha o token
fora dos arquivos versionados.

## Configurar e executar a coleta

Os parâmetros do estudo ficam em [config.yaml](./config.yaml). Antes de executar,
confira principalmente a janela de observação e o tamanho da amostra:

| Configuração | O que controla |
|---|---|
| `janela.inicio` e `janela.fim` | Primeiro e último dia do período estudado, ambos inclusivos, em UTC |
| `selecao` | Faixas de estrelas da busca e exclusão de forks e repositórios arquivados |
| `inclusao` | Quantidades mínimas de releases e execuções válidas para um repositório entrar na amostra |
| `amostra.tamanho` | Quantidade de repositórios elegíveis que a coleta busca reunir |
| `amostra.semente` | Valor que torna reproduzível a ordem aleatória dos candidatos |
| `coleta.workers` | Quantidade de requisições simultâneas, de 1 a 8 |
| `caminhos` | Pastas de cache, dados processados e saídas |

A configuração atual usa o período de **1º de outubro de 2025 a 30 de setembro de
2026**, exige pelo menos **5 releases e 50 execuções válidas** por repositório e
está definida para coletar **300 repositórios**, o mínimo da amostra completa do
estudo.

Execute, a partir da raiz do repositório:

```bash
python -m pipeline --config config.yaml
```

O pipeline primeiro busca candidatos e exclui forks e repositórios arquivados.
Depois, avalia os demais em uma ordem aleatória reproduzível: verifica se usam
GitHub Actions e se atendem aos mínimos de releases e execuções válidas na janela.
Essa sequência de filtros é o **funil de seleção**. Cada etapa registra quantos
repositórios permaneceram e quantos foram descartados.

A avaliação para quando encontra a quantidade de repositórios definida na
configuração. Para essa amostra, a execução reúne metadados e salva releases, tags,
commits entre releases e execuções de workflows. O comando de coleta produz os
dados de entrada para os cálculos; ele ainda não exporta um CSV consolidado com
todas as métricas.

Para avaliar todos os candidatos, mesmo depois de completar a amostra, use:

```bash
python -m pipeline --config config.yaml --funil-completo
```

Essa opção mantém a mesma amostra e registra o funil completo, mas pode consumir
muito mais requisições à API.

### Pausas, interrupções e retomada

A coleta pode levar horas e pausar quando atingir os limites de requisições do
GitHub. O cliente acompanha esses limites e espera automaticamente a liberação
da cota. Erros temporários do servidor e falhas de rede são repetidos com
intervalos progressivamente maiores.

As respostas recebidas ficam salvas em `data/cache/`. Se precisar interromper,
pressione `Ctrl+C`; depois, execute o mesmo comando para continuar. As respostas
já disponíveis no cache são reaproveitadas, evitando repetir a coleta. Os arquivos
são gravados de forma atômica para que uma interrupção não deixe uma resposta
parcial no cache. Apagar essa pasta elimina o reaproveitamento e exige novas
consultas ao GitHub.

O padrão de `coleta.workers` é 4. Usar 1 executa a coleta sequencialmente; valores
maiores permitem requisições simultâneas dentro dos limites coordenados pelo
cliente. A ordem dos resultados é preservada, portanto esse ajuste não muda a
amostra nem a ordem dos CSVs para os mesmos dados de entrada.

## Entender os arquivos gerados

Os arquivos são separados conforme sua função no estudo:

| Pasta | Conteúdo | Versionada? |
|---|---|---|
| `data/cache/` | Respostas originais da API, usadas para retomar e reproduzir a coleta | Não |
| `data/processed/` | Dados coletados organizados em CSV para os cálculos | Não |
| `output/` | Resultados de seleção e arquivos da validação manual | Sim |

O cache guarda uma resposta por arquivo JSON comprimido, em
`data/cache/<aa>/<sha256>.json.gz`. O cliente também consegue ler o formato JSON
não comprimido usado anteriormente.

### Seleção e dados coletados

| Arquivo | Como interpretar |
|---|---|
| `output/candidatos.csv` | Repositórios encontrados na busca inicial |
| `output/funil.csv` | Etapas da seleção, com contagens de permanência, descarte e motivos |
| `output/repos.csv` | Amostra selecionada e seus metadados, como estrelas, linguagem, idade e contribuidores |
| `data/processed/releases.csv` | Releases coletadas, com tag, data de publicação e indicação de draft e pré-release |
| `data/processed/tags.csv` | Tags, commits apontados por elas e datas de autoria desses commits |
| `data/processed/commits.csv` | Commits associados a cada release, com SHA, data de autoria e mensagem |
| `data/processed/runs.csv` | Execuções de workflows, com conclusão, datas e classe: `sucesso`, `falha` ou `ignorado` |
| `data/processed/releases_sem_compare.csv` | Releases sem comparação calculável com a anterior e o motivo da ausência |
| `data/processed/runs_meses_saturados.csv` | Repositórios e meses em que a consulta atingiu o teto de 1.000 execuções |

As datas são salvas em ISO 8601 com fuso UTC. Os nomes `full_name` e `tag_name`
identificam, respectivamente, o repositório (`dono/nome`) e a tag de uma release.

Para obter os commits de uma release, o coletor compara sua tag com a da release
principal publicada imediatamente antes. Essa antecessora pode estar fora da
janela, por isso o histórico de releases anteriores também é preservado. A
primeira release da história não tem antecessora; comparações também podem falhar
por tags apagadas ou reescritas, respostas 422 ou erros persistentes do servidor.
Esses casos ficam registrados em `releases_sem_compare.csv` e fora do lead time.

As execuções consideradas nas métricas são as disparadas por `push` no default
branch. `success` indica sucesso; `failure`, `timed_out` e `startup_failure` indicam
falha. As demais conclusões são ignoradas nos cálculos. Quando a consulta da janela
inteira tem 1.000 execuções ou mais, o coletor divide a busca por mês. Se um mês
também atingir o teto da API, ele é registrado em `runs_meses_saturados.csv`; isso
indica uma possível coleta incompleta naquele período.

## Calcular as métricas

As funções em `metricas/` recebem dados já coletados e calculam os resultados sem
acessar rede ou disco. Essa separação permite testar os cálculos com exemplos
pequenos, cujo resultado pode ser conferido à mão.

| Métrica | O que o cálculo representa |
|---|---|
| Frequência de entrega | Quantidade de releases publicadas dividida pelas semanas da janela |
| Lead time por release | Mediana do intervalo entre o commit mais antigo de cada release e sua publicação |
| Lead time por commit | Mediana dos intervalos entre cada commit e a publicação da release que o inclui |
| CFR de CI | Proporção de execuções com falha entre as execuções com sucesso ou falha |
| CFR de entrega | Proporção de releases avaliadas seguidas de uma corretiva em até sete dias |
| Tempo de recuperação | Mediana da duração dos episódios de falha, calculados dentro de cada workflow |

Uma release só entra na definição principal de entrega se estiver publicada,
sem ser draft ou pré-release. O lead time e o tempo de recuperação são expressos
em horas; a frequência, em releases por semana; e o CFR, como fração de 0 a 1.

### CFR de entrega e censura

O CFR de entrega procura sinais de correção depois de cada release. Uma release
é considerada falha se houver uma corretiva publicada depois dela em até sete
dias, inclusive. Uma publicação intermediária não encerra essa busca, e cada
release avaliada conta no máximo uma falha.

As releases dos últimos sete dias da janela ainda não tiveram o período completo
de observação. Por isso, são **censuradas**: ficam contabilizadas separadamente e
fora do denominador, mesmo que uma correção já tenha sido observada. Isso evita
comparar releases com tempos de acompanhamento diferentes.

Por exemplo, se houver 10 releases, 2 censuradas e 2 falhas entre as 8 avaliáveis,
o CFR será `2 / 8 = 0,25`, ou **25%**. Sem releases avaliáveis, o resultado é `None`,
pois não há dados suficientes para calcular a taxa. Com releases avaliáveis e
nenhuma falha, o resultado é `0.0`.

A função `metricas.cfr.cfr_entrega(releases, commits_por_release, fim_janela)`
retorna os seguintes campos:

| Campo | Significado |
|---|---|
| `cfr` | Fração de releases avaliadas consideradas falhas, ou `None` |
| `n_avaliadas` | Quantidade de releases com período completo de observação |
| `n_falharam` | Quantidade de releases avaliadas seguidas de corretiva no prazo |
| `n_censuradas` | Quantidade de releases publicadas nos últimos sete dias |

Ao chamar a função, forneça releases já restritas ao início da janela e commits
agrupados por tag, conforme os contratos das diretrizes. As datas devem ter fuso
UTC. Use `config.janela.fim` como limite final: o carregador de configuração
converte o último dia inclusivo para o início do dia seguinte, exclusivo. Drafts,
pré-releases, registros sem data e publicações nesse limite ou depois dele são
ignorados.

A identificação automática de releases corretivas precisa ser avaliada contra o
consenso humano descrito a seguir. Até os três avaliadores concluírem a rotulagem,
eles não devem consultar o código nem os resultados dessa identificação.

## Validar os dados com a amostra-ouro

A amostra-ouro é um subconjunto avaliado pelos três integrantes de forma
independente. Ela permite verificar se as releases representam entregas reais e
comparar a identificação automática de correções com o julgamento humano.

### Sortear os itens e gerar as planilhas

Faça o sorteio depois de concluir a coleta da amostra final de pelo menos 300
repositórios. O comando lê `output/repos.csv`, seleciona os repositórios e gera
planilhas vazias para cada avaliador:

```bash
python -m pipeline.amostra_ouro --config config.yaml
```

O tamanho do sorteio e a semente ficam em `config.yaml`, na seção `amostra_ouro`.
O padrão é **60 repositórios e 5 releases por repositório**, totalizando 300
releases. Com a mesma amostra e semente, o sorteio é o mesmo: os repositórios são
ordenados por nome antes da seleção, e cada um usa uma semente própria para
sortear suas releases. As releases são obtidas pelo cliente da API, aproveitando
as respostas já disponíveis no cache.

Todos os arquivos dessa etapa ficam em `output/amostra_ouro/`:

| Arquivo | Conteúdo |
|---|---|
| `sorteio_repos.csv` | Repositórios sorteados e links para suas páginas e releases |
| `sorteio_releases.csv` | Releases sorteadas, datas, links e comparação com a release anterior |
| `rotulos_A_repos.csv`, `rotulos_B_repos.csv`, `rotulos_C_repos.csv` | Uma planilha por avaliador para classificar os repositórios |
| `rotulos_A_releases.csv`, `rotulos_B_releases.csv`, `rotulos_C_releases.csv` | Uma planilha por avaliador para classificar as releases |
| `LEIAME.md` | Instruções para preencher as planilhas |

Se um repositório tiver menos releases elegíveis que o solicitado, todas serão
incluídas e o comando emitirá um aviso. O total de releases sorteadas poderá,
nesse caso, ser menor que o planejado.

### Preencher os rótulos de forma independente

Cada avaliador abre somente suas duas planilhas e consulta os links dos projetos,
as release notes e os commits. Os campos aceitam os seguintes valores:

| Campo | O que avaliar | Valores permitidos |
|---|---|---|
| `tipo_projeto` | Natureza principal do repositório | `biblioteca/framework`, `aplicação/serviço`, `ferramenta CLI`, `outro` |
| `entregas_reais` | Se as releases representam entregas ao usuário | `sim`, `não`, `incerto` |
| `corretiva` | Se o objetivo principal da release é corrigir um defeito recente | `sim`, `não` |
| `observacoes` | Dúvidas ou justificativas que ajudem na discussão posterior | Texto livre, opcional |

Os rótulos devem ser preenchidos por cada pessoa sem consultar os colegas, suas
planilhas ou a heurística automática. Em monorepos, a release anterior pode
pertencer a outro pacote; nesse caso, a comparação pode misturar mudanças, e as
release notes ajudam a interpretar a entrega.

Salve as planilhas como **CSV UTF-8**. Elas são geradas com vírgulas e BOM para
facilitar a abertura no Excel; o consenso também aceita arquivos separados por
ponto e vírgula.

Se já houver qualquer rótulo ou observação preenchido, o comando de sorteio
recusa sobrescrever as planilhas e retorna código 1 antes de consultar a API.
A opção `--forcar` descarta os rótulos existentes e só deve ser usada quando houver
uma decisão explícita de refazer o sorteio.

### Calcular a concordância e consolidar o consenso

Com as seis planilhas preenchidas, execute:

```bash
python -m pipeline.consenso --config config.yaml
```

Esse comando trabalha apenas com os arquivos locais. Primeiro, verifica se há
arquivos ausentes, itens faltando, extras ou repetidos, além de rótulos vazios ou
inválidos. Se encontrar erros, lista os problemas e não grava resultados.
Maiúsculas e espaços nas pontas dos valores são tolerados.

Depois da validação, calcula o **kappa de Fleiss** para cada dimensão avaliada.
Essa medida considera a concordância que poderia ocorrer por acaso, ajudando a
interpretar o quanto os avaliadores concordaram. Se todos os rótulos de uma
dimensão estiverem na mesma categoria, o kappa fica indefinido e é salvo vazio.

O consenso segue uma regra comum: três rótulos iguais produzem unanimidade; dois
iguais definem a maioria; três diferentes exigem reunião do grupo. Os casos de
reunião ficam em `desempates.csv`, onde devem ser preenchidos `rotulo_final` e
`justificativa`. Depois, execute novamente o comando para aplicar essas decisões.
As decisões já preenchidas são preservadas nas próximas execuções.

As saídas ficam na mesma pasta das planilhas:

| Arquivo | Conteúdo |
|---|---|
| `concordancia.csv` | Quantidade de itens e avaliadores, fração de unanimidade, kappa e interpretação por dimensão |
| `divergencias.csv` | Itens em que os avaliadores discordaram, seus rótulos e tipo de divergência |
| `desempates.csv` | Decisões e justificativas dos casos com três rótulos diferentes |
| `consenso_repos.csv` | Classificação final dos repositórios e origem de cada decisão |
| `consenso_releases.csv` | Classificação final das releases como corretivas ou não, com a origem da decisão |

O código de saída informa o resultado da execução:

| Código | Significado |
|---|---|
| `0` | Consenso completo |
| `1` | Erro nas planilhas ou nos desempates; nenhum resultado foi gravado |
| `2` | Configuração inválida |
| `3` | Arquivos gerados, mas ainda existem casos sem decisão do grupo |

### Avaliar a identificação automática de correções

Depois de concluir as três rotulagens e gerar o consenso, compare a heurística
automática com as decisões humanas:

```bash
python -m pipeline.validacao_heuristica --config config.yaml --versao v1 --descricao "Versão inicial"
```

O comando funciona sem token e sem rede. Ele lê os sorteios, as seis planilhas e
os dois arquivos de consenso em `output/amostra_ouro/`, além de `releases.csv` e
`commits.csv` em `data/processed/`. Os diretórios seguem os caminhos do
`config.yaml`. Antes de executar a heurística, verifica se as planilhas estão
completas, se o consenso contém os mesmos itens do sorteio e se está coerente com
os votos. Entradas ausentes, rótulos pendentes e releases sorteadas que não estão
nos dados coletados impedem a avaliação e a gravação de resultados.

A comparação é feita por **repositório e tag**, somente para as releases
sorteadas. Para identificar a antecessora de cada uma, o comando usa o histórico
das releases principais, inclusive anteriores à janela, com a mesma ordenação
usada na coleta de commits. Quando não há commits disponíveis para uma release,
ela continua na avaliação com os demais dados; essa ausência é contabilizada
para deixar explícita a limitação.

A classe positiva é a release **corretiva**. A precisão responde quantas das
correções previstas foram confirmadas pelo consenso; o recall responde quantas
das correções do consenso foram encontradas. O F1 combina as duas medidas. Todas
são frações de 0 a 1. Quando um denominador é zero, a medida correspondente é
registrada como `0.0`. Se o consenso não tiver nenhuma corretiva, a execução
registra essa condição e não considera a detecção da classe validada.

Cada execução usa um identificador de versão e uma descrição. As saídas ficam em
`output/validacao_heuristica/`:

| Arquivo | Conteúdo |
|---|---|
| `historico.csv` | Uma linha por versão, com descrição, contagens, precisão, recall, F1 e situação |
| `relatorio.md` | Tabela de todas as versões, contagens de erros e limitações, para apoiar a escrita do artigo |
| `<versao>/resultado.json` | Resultado completo da versão, identificação dos dados e código usados, versão do scikit-learn e meta de F1 |
| `<versao>/codigo.json` | Cópia do código da heurística, do cálculo das métricas e do comando usados nessa avaliação |
| `<versao>/comparacao.csv` | Consenso e previsão para cada release sorteada, indicação de acerto e de ausência de commits |

No histórico, `vp` significa corretivas identificadas corretamente; `fp`, releases
previstas como corretivas que o consenso classificou como não corretivas; `fn`,
corretivas que a heurística não encontrou; e `vn`, não corretivas identificadas
corretamente. `n_itens`, `n_corretivas_reais` e `n_corretivas_previstas` informam o
tamanho da comparação e os totais de positivos de cada lado. `n_sem_commits`
conta as releases avaliadas sem commits disponíveis. As contagens são inteiros;
precisão, recall e F1 são frações.

Os campos `dados_sha256` e `codigo_sha256` identificam as entradas e o código
usados. Repetir a mesma versão com as mesmas entradas, código e descrição não
duplica o registro. Se algum deles mudar, use uma nova versão: os resultados
anteriores são preservados. A comparação por item permite examinar os erros
depois da rotulagem, sem alterar os rótulos humanos.

O relatório inclui todas as tentativas, mesmo as que ficaram abaixo da meta, e
aponta quando elas usaram entradas diferentes. Nesse caso, uma mudança de F1 pode
vir dos dados, além das alterações na heurística. As cópias do código permitem
consultar a implementação exata de cada versão, mesmo depois de novos refinamentos.
O resultado JSON também registra o número de repositórios avaliados e os limites
da janela em UTC.

A meta é **F1 ≥ 0,70**. Abaixo dela, refine a heurística com base nos erros
observados e execute novamente com outra versão e uma descrição do refinamento:

```bash
python -m pipeline.validacao_heuristica --config config.yaml --versao v2 --descricao "Descrição do refinamento realizado"
```

Registre no artigo cada versão avaliada e seu resultado, incluindo tentativas
abaixo da meta. Como os refinamentos usam a mesma amostra-ouro, os resultados
medem o desempenho nessa amostra e podem ser otimistas para outros projetos.

O código de saída permite distinguir os resultados:

| Código | Significado |
|---|---|
| `0` | Avaliação registrada com F1 igual ou superior à meta |
| `1` | Erro nas entradas ou conflito com uma versão já registrada |
| `2` | Argumentos ou configuração inválidos |
| `3` | Avaliação registrada com F1 abaixo da meta; é necessário refinar e reavaliar |
| `4` | Avaliação registrada, mas o consenso não tem corretivas para validar a detecção |

## Gerar o dataset final

Com a coleta concluída (`output/repos.csv` e os arquivos de `data/processed/`), consolide as
métricas de cada repositório com:

```bash
python -m pipeline.dataset --config config.yaml
```

O comando trabalha apenas com arquivos locais: não precisa de `GITHUB_TOKEN` nem faz consultas
à API. Leva alguns segundos, porque lê o `commits.csv` em fluxo, um repositório por vez. Se
faltar releases ou runs de algum repositório de `repos.csv`, ou se um arquivo tiver cabeçalho
inesperado, ele lista o problema e retorna o código 2 sem gravar nada.

O resultado é `output/metricas_repos.csv`, com uma linha por repositório e as seguintes
colunas, todas descritas em [`output/dicionario_dados.md`](./output/dicionario_dados.md):

| Grupo | Colunas |
|---|---|
| Metadados (RQ 06) | `full_name`, `default_branch`, `language`, `stars`, `contributors`, `created_at`, `idade_dias`, `tipo_projeto`, `entregas_reais` |
| Frequência (RQ 01) | `n_releases`, `n_prereleases`, `frequencia_semana` |
| Lead time (RQ 02) | `lead_time_release_horas` (a), `lead_time_commit_horas` (b) e as contagens de releases e commits usados e de releases ignoradas |
| CFR (RQ 03) | `cfr_ci` (a) com as contagens de runs; `cfr_entrega` (b) com releases avaliadas, que falharam e censuradas |
| Recuperação (RQ 04) | `recuperacao_mediana_horas`, `n_episodios_recuperacao`, `prop_episodios_censurados` |
| Classificação DORA | `classe_frequencia`, `classe_lead_time`, `classe_cfr`, `classe_recuperacao`, `classe_geral`, na combinação de referência (lead time e CFR na variante a) |

Valores vazios significam que não havia dados suficientes, e nunca zero. `tipo_projeto` e
`entregas_reais` só vêm preenchidos nos 60 repositórios da amostra-ouro e só depois de
`python -m pipeline.consenso` gerar o `consenso_repos.csv`; os demais ficam vazios. Se esse
arquivo ainda não existe, o comando avisa e segue com essas colunas vazias.

## Executar os testes

Com o ambiente virtual ativo, execute:

```bash
pytest --cov=metricas --cov-report=term-missing --cov-fail-under=80
```

Os testes verificam os cálculos com dados sintéticos e a coleta com respostas
simuladas, sem fazer consultas reais ao GitHub. O comando também mede a cobertura
de `metricas/` e falha se ela ficar abaixo de 80%. Os mesmos testes são executados
no GitHub Actions a cada push e pull request, conforme
[.github/workflows/testes.yml](./.github/workflows/testes.yml).
