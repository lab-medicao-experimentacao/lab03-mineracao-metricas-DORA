# 1. Introdução

> Rascunho em Markdown da seção de Introdução (Lab03S01, Issue #13). A versão final vai para o template SBC.
> **As hipóteses abaixo foram escritas antes da coleta de qualquer dado** e não devem ser editadas depois de vê-los; a comparação hipótese × resultado é feita na Discussão.
>
> Divisão: A → RQ 01, RQ 06, RQ 07 · B → RQ 02, RQ 05 · C → RQ 03, RQ 04. Revisão pelos três.

As métricas DORA (*DevOps Research and Assessment*) — *deployment frequency*, *lead time for changes*, *change failure rate* e tempo de recuperação — tornaram-se a referência de mercado para medir o desempenho de entrega de software [Forsgren, Humble e Kim 2018]. Elas foram concebidas para equipes que colocam mudanças em produção e são coletadas, nos relatórios anuais do DORA, por meio de questionários respondidos pelas próprias equipes.

Em projetos open-source, não há "produção" nem registro explícito de "falha em produção". O que existe são artefatos públicos: *releases*, *commits* e execuções de *workflows* de CI/CD. Este trabalho minera esses artefatos em repositórios populares do GitHub que usam GitHub Actions e calcula **aproximações** (*proxies*) das quatro métricas: uma release publicada faz o papel de deploy, e uma execução de CI que falhou faz o papel de falha.

Como os proxies podem não medir o que as métricas originais medem, o estudo tem dois objetivos: (i) descrever o desempenho DORA desses repositórios e investigar fatores associados a ele; e (ii) avaliar o quanto essas conclusões dependem das definições operacionais escolhidas. Para isso, respondemos às questões de pesquisa a seguir. Para cada uma, registramos uma hipótese informal — o que esperamos encontrar e por quê — antes de observar os dados.

## Questões de pesquisa e hipóteses

**RQ 01. Qual a frequência de deploys dos repositórios populares que usam CI/CD?**

*Hipótese:* esperamos que a mediana da frequência de deploys fique na faixa **Medium** (de uma release por mês a menos de uma por semana), com distribuição fortemente assimétrica à direita. Projetos open-source populares costumam publicar releases em ciclos planejados (mensais ou por marco), e não a cada mudança integrada, porque cada release implica changelog, versionamento e compatibilidade para os usuários. Esperamos poucos repositórios **Elite** (≥ 7 por semana), concentrados em projetos com publicação automatizada (por exemplo, uma release por *merge* gerada por ferramenta), que serão os valores extremos da distribuição. Também esperamos que a faixa **Low** seja menos comum do que na população geral de repositórios, pois o critério de inclusão (≥ 5 releases na janela, ou seja, ≈ 0,1 por semana) já remove os projetos que quase não publicam releases — um viés de seleção a ser discutido nas ameaças à validade.

**RQ 02. Qual o tempo entre um commit e seu respectivo deploy?**

*Hipótese:* esperamos que a mediana do lead time por commit (variante b) seja menor do que a mediana por release (variante a) na maioria dos repositórios. A variante (a) toma o commit mais antigo de cada release e, portanto, cresce bastante quando uma mudança antiga espera vários ciclos até ser publicada; na variante (b), esse commit é apenas uma observação entre todas as mudanças entregues. Também esperamos uma distribuição assimétrica, com poucos repositórios acumulando tempos muito altos em releases que reúnem longos períodos de trabalho.

**RQ 03. Qual a taxa de falha das mudanças entregues por esses repositórios?**

*Hipótese:* `<C preenche>`

**RQ 04. Qual o tempo de recuperação após uma execução de CI/CD com falha?**

*Hipótese:* `<C preenche>`

**RQ 05. Repositórios com maior frequência de deploy apresentam maior ou menor taxa de falha?**

*Hipótese:* esperamos correlação de Spearman fraca entre frequência de releases e CFR, com resultados possivelmente diferentes para as duas variantes de CFR. Publicar mais releases não implica, por si só, aumentar a fração de execuções de CI com falha; os projetos podem automatizar testes e revisão antes da publicação. Já o CFR baseado em releases corretivas depende do padrão de versionamento e da rapidez com que correções são publicadas, de modo que a mesma frequência pode se relacionar de outra forma com esse proxy. Por isso, não esperamos que os dois coeficientes indiquem necessariamente a mesma direção ou intensidade.

**RQ 06. Quais características dos repositórios estão associadas a um melhor desempenho DORA?**

*Hipótese:* esperamos que as características ligadas ao **processo** do projeto (tipo do projeto e número de contribuidores) estejam mais associadas ao desempenho do que as ligadas à **visibilidade** (estrelas), e que os efeitos, quando existirem, sejam de tamanho pequeno a médio. Em particular:

- **Tipo do projeto:** bibliotecas e frameworks devem ter menor frequência de deploy e maior lead time do que aplicações/serviços e ferramentas CLI, porque cada release de uma biblioteca afeta projetos dependentes e tende a ser mais cuidadosamente agrupada e versionada. Como esse fator é rotulado manualmente apenas na amostra de validação (60 repositórios), as comparações por tipo terão menos poder estatístico do que as demais.
- **Número de contribuidores:** repositórios com mais contribuidores devem ter maior frequência de deploy e menor tempo de recuperação, pois há mais mudanças entrando e mais pessoas disponíveis para corrigir uma falha de CI. Quanto ao CFR (a), que considera apenas execuções disparadas por *push* no default branch — e, portanto, mudanças já integradas —, não esperamos diferença clara: projetos maiores integram mais mudanças, mas tendem a filtrá-las melhor na revisão de *pull requests*.
- **Idade do repositório:** repositórios mais antigos devem ter frequência menor e processo mais estável (CFR menor) do que os mais novos, que ainda estão em fase de desenvolvimento acelerado.
- **Popularidade (estrelas):** esperamos pouca ou nenhuma diferença, porque a amostra já é composta apenas de repositórios populares, o que reduz a variação desse fator.

Como serão feitos pelo menos 12 testes, esperamos que parte das diferenças que pareceriam significativas isoladamente deixe de sê-lo após a correção de Holm.

**RQ 07. O quanto a classificação DORA de um repositório depende da definição operacional escolhida?**

*Hipótese:* esperamos que a classificação seja **sensível** à definição operacional, com uma parcela considerável dos repositórios (da ordem de um terço) mudando de categoria geral entre a combinação de referência (C1) e as alternativas, e concordância apenas moderada entre as classificações (kappa ponderado entre 0,4 e 0,6). As mudanças devem ser, na maioria, para categorias **adjacentes** (por exemplo, High → Medium), e não saltos como Elite → Low. Esperamos esse efeito porque:

- incluir pré-releases ou usar tags como unidade de deploy aumenta a frequência dos projetos que publicam versões *alpha/beta/rc* ou criam tags sem release, empurrando-os para categorias melhores;
- a variante (b) do lead time (por commit) tende a ser menor do que a (a) (por release), que é dominada pelo commit mais antigo, o que melhora a categoria de lead time;
- o CFR (a) mede falha de pipeline de CI e o CFR (b) mede releases corretivas; são fenômenos diferentes, e esperamos baixa correspondência entre as categorias que cada um produz.

Por outro lado, a classificação geral é a mediana das quatro categorias, o que deve amortecer a mudança em uma única métrica; por isso esperamos que a categoria de cada métrica mude mais do que a classificação geral.

## Referências

- Forsgren, N., Humble, J. e Kim, G. (2018). *Accelerate: The Science of Lean Software and DevOps*. IT Revolution Press.
- DORA. *DORA's software delivery metrics: the four keys*. https://dora.dev/guides/dora-metrics-four-keys/
