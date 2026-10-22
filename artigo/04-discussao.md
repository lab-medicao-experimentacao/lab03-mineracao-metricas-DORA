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

Há dois motivos para tratar o valor da variante (b) com cautela. Primeiro, a heurística marca como corretiva qualquer release com um commit cuja mensagem contenha *fix*, *revert* ou *hotfix*. Em releases com muitos commits, isso tende a acontecer quase sempre, e no agregado 66,1 % das releases avaliadas são seguidas por uma corretiva em até 7 dias. Na amostra-ouro, o consenso dos avaliadores classificou como corretivas 34,3 % das releases sorteadas. Os dois números não são diretamente comparáveis, porque o CFR (b) conta a release que antecede a corretiva, mas a diferença sugere que a heurística marca corretivas demais. A precisão medida na #34 dirá o quanto `<preencher após #34: precisão, recall e F1, e se a heurística foi refinada>`. Segundo, a janela de 7 dias favorece repositórios que publicam com frequência: quem publica várias vezes por semana quase sempre tem uma release seguinte nesse prazo, e basta que ela seja corretiva. Essa relação mecânica entre frequência e CFR (b) é retomada na RQ 05 (Seção 4.6). A censura pesa pouco: 292 releases (2,6 % das 10.796 avaliadas mais as censuradas), e um único repositório, `egoist/mygo`, fica sem CFR (b) por ter publicado todas as releases nos últimos 7 dias da janela.

## 4.4 RQ 04: tempo de recuperação

*Hipótese (introdução):* `<preencher: hipótese de C, escrita antes dos dados>`

A mediana de 4,2 horas indica que, na maior parte dos repositórios, um workflow que falha volta a passar no mesmo dia. Isso combina com a natureza do proxy: a "recuperação" é o próximo sucesso do mesmo workflow, que muitas vezes vem de uma nova execução ou de um *push* que corrige um teste, e não da correção de um incidente em produção. A censura quase não afeta a mediana: 1,32 % dos episódios terminaram sem sucesso na janela, e a mediana da proporção censurada por repositório é zero. Como os episódios censurados entram com o tempo decorrido até o fim da janela, que é um limite inferior do tempo real, a mediana tende levemente para baixo nos 80 repositórios com algum episódio censurado.

Os 28 repositórios sem episódio ficam sem valor nesta métrica, em vez de receberem zero. Em 19 deles nenhuma execução válida falhou; atribuir zero os tornaria Elite por ausência de evidência e misturaria "não falhou" com "recuperou instantaneamente". Eles continuam na classificação geral com as três métricas restantes.

## 4.5 Classificação de referência (C1)

A categoria geral se concentra em High (42,0 %) e Medium (38,3 %), com 8,0 % Elite e 11,7 % Low. As métricas puxam em direções opostas. Pontuando Elite = 4, High = 3, Medium = 2 e Low = 1, a média é 3,62 no CFR (a), 2,96 na recuperação, 2,46 no lead time (a) e 1,83 na frequência. O CFR por proxy de CI empurra os repositórios para cima e a frequência os empurra para baixo, de modo que 24 repositórios chegam a Elite geral embora só um seja Elite em frequência. Como o CFR (a) é a métrica mais favorável e a variante (b) dá valores muito maiores, a escolha da variante tende a mudar bastante a classificação geral, o que a RQ 07 avalia (Seção 4.7). A regra de três métricas afeta 28 repositórios (9,3 %), todos sem tempo de recuperação; os outros 272 são classificados com as quatro.

## 4.6 RQ 05 e RQ 06

`<B preenche (#46, #47)>`

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
