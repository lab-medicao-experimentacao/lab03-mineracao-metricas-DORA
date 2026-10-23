# 4. Discussão

> Rascunho em Markdown da seção de Discussão (Lab03S03, Issue #51). A versão final vai para o template SBC.
> Divisão igual à dos Resultados: A → RQ 01 a RQ 04 (#48) · B → RQ 05 e RQ 06 · C → RQ 07 e RQ 08. Revisão pelos três.
> Cada subseção confronta a hipótese da introdução com os resultados da seção 3; os números das RQ 01 a 04 vêm de `output/analises/rq01_rq04/`.

## 4.1 RQ 01: frequência de deploys

*Hipótese (introdução):* mediana na faixa Medium, distribuição assimétrica à direita, poucos Elite concentrados em publicação automatizada e Low menos comum por causa do critério de inclusão (≥ 5 releases na janela).

A hipótese se confirma em três dos quatro pontos. A mediana, de 0,35 release por semana (cerca de 1,5 por mês), está na faixa Medium, e a distribuição é fortemente assimétrica, com cauda à direita. A faixa Elite tem um único repositório, `bluesky-social/atproto`, um monorepo que publica uma release por pacote (tags como `@atproto/pds@0.5.46`). A frequência dele mede, portanto, publicações de pacotes, e não entregas de um único produto. Os demais repositórios com frequência alta (até cerca de 4,5 releases por semana) ficam em High. Isso sugere que a publicação automatizada a cada *merge* é rara nesta amostra, ou que, quando existe, não chega a uma release por dia.

O quarto ponto não se confirma da forma esperada. A faixa Low reúne 97 repositórios (32,3 %), com mediana de 0,13 release por semana, logo acima do piso de inclusão. Não temos a população geral para comparar, mas a faixa está longe de ser residual: o critério de inclusão corta a cauda inferior, sem esvaziá-la.

O critério de inclusão impõe um piso de cerca de 0,1 release por semana, o que limita, por construção, a proporção de repositórios Low; esse viés de seleção é retomado nas ameaças à validade.

## 4.2 RQ 02: lead time

*Hipótese (introdução):* a variante por commit (b) fica abaixo da variante por release (a) na maioria dos repositórios, porque a (a) é determinada pelo commit mais antigo de cada release.

A hipótese se confirma no nível do repositório, mas com efeito menor do que o esperado. A variante (b) é menor que a (a) em 61,0 % dos repositórios, e a mediana da razão (b)/(a) é 0,72. No agregado, porém, as medianas das duas variantes são quase iguais (7,8 e 7,9 dias), e a variante (b) é menos dispersa (IQR de 1,4 a 28,2 dias, contra 1,1 a 35,0 dias na variante a). O commit mais antigo infla a variante (a) principalmente na cauda. Por exemplo, em `truffleruby/truffleruby` a variante (a) passa de 5 anos e a (b) fica em cerca de 77 dias, o que indica releases que levam commits muito antigos.

Os 116 repositórios em que (b) > (a) mostram o mecanismo oposto. A variante (a) dá o mesmo peso a cada release, e a (b), a cada commit. Quando poucas releases grandes concentram a maior parte dos commits e as demais são rápidas, a mediana por commit fica acima da mediana por release. Esses repositórios têm mais releases com commits calculados (mediana de 23,5, contra 16 na amostra toda). Os valores extremos, como `phpseclib/phpseclib` (mais de 9 anos na variante a), são compatíveis com repositórios que mantêm várias linhas de versão em paralelo, nos quais a release "anterior" pode pertencer a outra linha. Isso é uma limitação da regra de pareamento das releases, retomada nas ameaças à validade.

A data usada é `commit.author.date`, que *rebases* e *squash merges* podem deslocar; o efeito sobre as duas variantes é discutido nas ameaças à validade.

## 4.3 RQ 03: taxa de falha das mudanças

*Hipótese (introdução):* `<preencher: hipótese de C, escrita antes dos dados>`

As duas variantes divergem muito: mediana de 6,05 % no proxy de CI (a), com 76 % dos repositórios Elite, contra 40,0 % no proxy de entrega (b). Medem coisas diferentes. A variante (a) conta execuções de CI com falha, que em projetos com integração contínua costumam ser corrigidas antes de chegar a uma release. A variante (b) conta releases seguidas por uma correção em até 7 dias, uma noção mais próxima da falha percebida pelo usuário.

Há dois motivos para tratar o valor da variante (b) com cautela. Primeiro, a heurística marca como corretiva qualquer release com um commit cuja mensagem contenha *fix*, *revert* ou *hotfix*. Em releases com muitos commits, isso tende a acontecer quase sempre, e no agregado 66,1 % das releases avaliadas são seguidas por uma corretiva em até 7 dias. Na amostra-ouro, o consenso dos avaliadores classificou como corretivas 34,3 % das releases sorteadas. Os dois números não são diretamente comparáveis, porque o CFR (b) conta a release que antecede a corretiva, mas a diferença sugere que a heurística marca corretivas demais. A validação da #34 confirmou essa limitação: a v1, usada nestes resultados, obteve precisão de 0,3755, recall de 0,9515 e F1 de 0,5385, com 163 falsos positivos nas 300 releases da amostra-ouro. A v3 refinada atingiu F1 de 0,7042 apenas na avaliação; por restrição de prazo, não houve recálculo do dataset e das análises, que permanecem com a v1. Portanto, a melhora da v3 não pode ser atribuída aos números apresentados. Segundo, a janela de 7 dias favorece repositórios que publicam com frequência: quem publica várias vezes por semana quase sempre tem uma release seguinte nesse prazo, e basta que ela seja corretiva. Essa relação mecânica entre frequência e CFR (b) é retomada na RQ 05 (Seção 4.6). A censura pesa pouco: 292 releases (2,6 % das 10.796 avaliadas mais as censuradas), e um único repositório, `egoist/mygo`, fica sem CFR (b) por ter publicado todas as releases nos últimos 7 dias da janela.

## 4.4 RQ 04: tempo de recuperação

*Hipótese (introdução):* `<preencher: hipótese de C, escrita antes dos dados>`

A mediana de 4,2 horas indica que, na maior parte dos repositórios, um workflow que falha volta a passar no mesmo dia. Isso combina com a natureza do proxy: a "recuperação" é o próximo sucesso do mesmo workflow, que muitas vezes vem de uma nova execução ou de um *push* que corrige um teste, e não da correção de um incidente em produção. A censura quase não afeta a mediana: 1,32 % dos episódios terminaram sem sucesso na janela, e a mediana da proporção censurada por repositório é zero. Como os episódios censurados entram com o tempo decorrido até o fim da janela, que é um limite inferior do tempo real, a mediana tende levemente para baixo nos 80 repositórios com algum episódio censurado.

Os 28 repositórios sem episódio ficam sem valor nesta métrica, em vez de receberem zero. Em 19 deles nenhuma execução válida falhou; atribuir zero os tornaria Elite por ausência de evidência e misturaria "não falhou" com "recuperou instantaneamente". Eles continuam na classificação geral com as três métricas restantes.

## 4.5 Classificação de referência (C1)

A categoria geral se concentra em High (42,0 %) e Medium (38,3 %), com 8,0 % Elite e 11,7 % Low. As métricas puxam em direções opostas. Pontuando Elite = 4, High = 3, Medium = 2 e Low = 1, a média é 3,62 no CFR (a), 2,96 na recuperação, 2,46 no lead time (a) e 1,83 na frequência. O CFR por proxy de CI empurra os repositórios para cima e a frequência os empurra para baixo, de modo que 24 repositórios chegam a Elite geral embora só um seja Elite em frequência. Como o CFR (a) é a métrica mais favorável e a variante (b) dá valores muito maiores, a escolha da variante tende a mudar bastante a classificação geral, o que a RQ 07 avalia (Seção 4.7). A regra de três métricas afeta 28 repositórios (9,3 %), todos sem tempo de recuperação; os outros 272 são classificados com as quatro.

## 4.6 RQ 05 e RQ 06

### RQ 05: frequência e estabilidade

*Hipótese (introdução):* associação fraca entre frequência de releases e CFR, com possíveis diferenças de direção ou intensidade entre os proxies.

No proxy de CI, a magnitude observada é pequena (ρ = 0,0585, p = 0,3123, n = 300), compatível com a expectativa de associação fraca. O teste não fornece evidência de associação monotônica ao nível de 5%, mas isso não prova independência nem exclui relações não monotônicas. Nesta amostra, publicar com maior frequência não acompanha uma mudança monotônica clara na fração de execuções de CI que falham.

No proxy de entrega, a associação é positiva e de magnitude maior (ρ = 0,7655, p ≈ 8,2589 × 10⁻⁵⁹, n = 299), contrariando a expectativa de associação fraca para essa variante. A hipótese se sustenta, portanto, apenas parcialmente: a diferença entre proxies se manifesta sobretudo na intensidade. Não foi realizado teste formal da diferença entre os dois coeficientes; seus p-valores isolados não respondem a essa pergunta, e as amostras diferem em um repositório.

A associação do CFR (b) com frequência pode refletir, em parte, a própria definição operacional: uma release só conta como falha quando uma corretiva é publicada nos sete dias seguintes. Projetos com maior cadência têm mais oportunidades de apresentar uma release nesse intervalo. Isso é uma explicação possível, não uma causa demonstrada pelos dados. Padrões de versionamento, monorepos, composição das releases e erros da heurística também podem contribuir. A validação da #34 mediu precisão de 0,3755, recall de 0,9515 e F1 de 0,5385 para a v1 usada nesta análise. O excesso de falsos positivos limita a interpretação da associação. Por restrição de prazo, v2 e v3 ficaram como experimentos de validação e não foram aplicadas ao dataset nem a esta análise; não foi medido o efeito dos refinamentos sobre os coeficientes apresentados.

No proxy de CI, observou-se pouca associação monotônica entre frequência e taxa de falha, o que não demonstra equivalência de estabilidade entre projetos nem comprova a afirmação DORA sobre desempenho em produção. A associação positiva de entrega também não demonstra que publicar mais cause falhas: releases e execuções de CI são aproximações, há fatores não controlados, e a amostra reúne apenas projetos populares que passam pelos filtros. A análise observacional não identifica causalidade.

Os dois p-valores são aproximações de `spearmanr`, sem ajuste entre variantes. A [documentação do SciPy](https://docs.scipy.org/doc/scipy-1.14.1/reference/generated/scipy.stats.spearmanr.html) ressalta que essa aproximação tem precisão adequada em amostras muito grandes (>500), acima dos tamanhos usados aqui. As conclusões devem considerar os coeficientes, as dispersões, a seleção amostral e a validade dos proxies, em vez de depender somente de significância estatística.

### RQ 06: características associadas

*Hipótese (introdução):* tipo de projeto e contribuidores mais associados ao desempenho do que estrelas, com diferenças pequenas a médias; mais contribuidores acompanhariam maior frequência e menor recuperação; projetos antigos teriam menor frequência e maior estabilidade.

A hipótese se sustenta parcialmente. Contribuidores diferem sobretudo em lead time: ε² = 0,236 na variante (a), com p de Holm = 7,211e-14. As medianas de lead time (a) crescem de 23,44 (103,36) horas em Q1 para 753,91 (1709,79) horas em Q4 (valores entre parênteses são IQR). A variante (b) também difere após Holm, enquanto frequência e recuperação não preservam significância após o ajuste. A amostra, portanto, não sustenta a previsão de maior frequência e recuperação menor em projetos com mais contribuidores. Comparar as descritivas não estabelece que aumentar contribuidores cause um aumento do lead time; participação, idade, complexidade e organização das releases podem estar relacionadas.

Idade apresenta diferenças na frequência, nas duas variantes de lead time e no CFR (b). A frequência mediana diminui de 0,65 (0,84) para 0,21 (0,25) releases/semana entre o quartil mais novo e o mais antigo, como previsto; o lead time (a) cresce de 25,93 (68,54) para 793,12 (2014,69) horas. O CFR (b) mediano é menor nos mais antigos, mas isso pode acompanhar a menor cadência e o mecanismo de sete dias discutido na RQ05. A hipótese de maior estabilidade nos antigos não é sustentada pelo CFR (a), cujas distribuições não diferem de forma detectável após a correção; a recuperação também perde significância após Holm. Os resultados de entrega usam a v1, cuja baixa precisão foi medida na #34; não incorporam os refinamentos posteriores por restrição de prazo.

Estrelas apresentam uma única diferença após Holm, no lead time (a) (ε² = 0,049, p ajustado = 0,0387). As medianas vão de 72,18 (501,84) a 431,98 (951,64) horas entre Q1 e Q4. Esse efeito observado é menor que os de contribuidores e idade para a mesma métrica, mas não houve teste formal da diferença entre tamanhos de efeito. Nas demais métricas não se detectaram diferenças após Holm, resultado compatível com a expectativa de pouca associação com popularidade nesta amostra já filtrada por estrelas, sem demonstrar equivalência entre quartis.

Nenhuma comparação por tipo de projeto permanece significativa após Holm. Isso não demonstra equivalência entre tipos: são apenas 60 repositórios, com grupos desbalanceados e um mínimo de cinco valores válidos no grupo `outro` para recuperação. Descritivamente, bibliotecas/frameworks têm frequência mediana maior e lead time menor que aplicações e CLI, em direção contrária à hipótese inicial, mas os testes globais corrigidos não permitem concluir que esses grupos diferem. O subconjunto rotulado tem menos poder estatístico do que a amostra completa.

A redução de 13 testes com p bruto < 0,05 para 8 após Holm confirma a importância do ajuste previsto na introdução. Os testes são globais, sem comparações post hoc: não identificam quais pares explicam cada resultado. Os ε² são reportados sem atribuir limites arbitrários de pequeno/médio/grande, e os efeitos e p-valores não isolam confundidores. Grupos com ausências não recebem valores inventados. Projetos populares que atendem ao funil não representam automaticamente outros contextos; a ausência de significância não comprova ausência de relação. Um refinamento do CFR (b) exige regerar o dataset e repetir toda a família de Holm.

## 4.7 RQ 07 e RQ 08

### RQ 07: sensibilidade à definição operacional

*Hipótese (introdução):* uma parcela considerável dos repositórios (da ordem de um terço) muda de categoria geral entre C1 e as alternativas, com concordância apenas moderada (kappa ponderado entre 0,4 e 0,6) e mudanças sobretudo para categorias adjacentes. Esperávamos que pré-releases e tags melhorassem a frequência, que o lead time por commit (b) melhorasse a categoria de lead time e que as duas variantes de CFR correspondessem pouco.

A hipótese se confirma na ordem de grandeza e na direção das mudanças, mas não nos valores de kappa. A classificação é sensível: 48,67 % dos repositórios mudam de categoria entre C1 e C2, 24,00 % entre C1 e C3 e 42,33 % entre C2 e C3, e a média simples dos dois pares com C1 (36,3 %) fica perto do terço esperado. As mudanças são quase todas para categorias vizinhas (130 de 146 em C1 × C2, 71 de 72 em C1 × C3 e 122 de 127 em C2 × C3), e só 22 saltos de duas ou mais categorias aparecem nas 345 mudanças somadas dos três pares. Os kappas ponderados, porém, se espalham por três faixas em vez de ficarem na moderada: 0,34 (razoável) em C1 × C2, 0,70 (substancial) em C1 × C3 e 0,44 (moderada) em C2 × C3. Só um dos três pares cai no intervalo previsto.

Os três motivos da hipótese têm resultados diferentes.

1. **Pré-releases e tags melhoram a frequência, como previsto, mas pouco.** Todas as 17 e as 41 mudanças de categoria de frequência são para melhor, e ainda assim afetam só 5,67 % e 13,67 % dos repositórios. A mediana da frequência sobe de 0,35 para 0,38 (pré-releases) e 0,47 release por semana (tags), sempre abaixo do corte de uma por semana, e por isso a unidade de deploy muda pouco a categoria geral.
2. **O lead time por commit (b) não melhora sistematicamente a categoria.** Dos 123 repositórios que mudam de categoria de lead time ao trocar (a) por (b), 65 melhoram e 58 pioram. Isso é coerente com a RQ 02: (b) é menor que (a) em 61 % dos repositórios, mas as medianas agregadas (cerca de 7,8 e 7,9 dias) ficam coladas ao corte de uma semana entre High e Medium, e uma diferença pequena cruza o corte nos dois sentidos.
3. **A correspondência entre os CFR é baixa, como esperado, e é a maior fonte de sensibilidade.** 74,92 % dos repositórios mudam de categoria de CFR entre (a) e (b), 205 de 224 para pior, porque o CFR (b) tem mediana de 40,0 %, contra 6,05 % no CFR (a) (Seção 3.3).

Essa assimetria explica a forma das comparações. C2 é a combinação que usa o CFR (b), e por isso os pares C1 × C2 e C2 × C3 são os de menor concordância (κ = 0,34 e 0,44) e os de mais mudanças. Em C2, só 4 repositórios (1,33 %) ficam em Elite, contra 24 (8,00 %) em C1, e 188 (62,67 %) ficam em Medium. Já C1 × C3 compartilha o CFR (a), e a diferença se resume à frequência por tag e ao lead time (b), o que dá o maior kappa (0,70). A escolha da variante do CFR, mais do que a da unidade de deploy, é o que decide a classificação geral de um repositório.

**As conclusões das RQ 01 a RQ 06 são robustas?** Em parte.

- **RQ 01 (frequência):** robusta no agregado. A mediana permanece na faixa Medium com pré-releases e com tags, e o efeito das variantes é sempre para cima e pequeno.
- **RQ 02 (lead time):** robusta no agregado, porque as duas variantes têm medianas quase iguais, mas não por repositório: 41,00 % mudam de categoria de lead time.
- **RQ 03 (CFR):** **não** robusta. O proxy de CI põe 228 repositórios (76,0 %) em Elite, e o proxy de entrega põe 134 dos 299 com CFR (b) (44,8 %) em Low. Falar em "taxa de falha" sem dizer qual proxy é enganoso.
- **RQ 04 (recuperação):** não varia entre as combinações, porque só tem uma definição (CI). Sua robustez não foi testada aqui.
- **RQ 05 e RQ 06:** já tratam as duas variantes de CFR separadamente. A sensibilidade medida indica que suas conclusões devem ser lidas variante a variante (Seção 4.6), e que a relação entre frequência e CFR (b) pode ser, em parte, efeito da própria definição (Seção 4.3).

**Limites.** A variante por tag altera só a frequência: o lead time e o CFR (b) não foram recalculados por tag, porque a comparação de commits foi coletada entre releases principais. C3 mede, portanto, "tag para a frequência, release para o resto". A data da tag é a do commit apontado, que pode ser muito anterior à criação da tag; em 150 dos 300 repositórios o número de tags na janela supera o de releases (colunas `n_tags` e `n_releases` do dataset). Por fim, a combinação C2 mistura duas mudanças, pré-releases e variantes (b); como as pré-releases afetam só 5,67 % das categorias de frequência, quase toda a diferença de C2 vem das variantes (b), e a análise só as separa pela tabela por métrica.

### RQ 08 (bônus)

`<preencher: C, #50>`
