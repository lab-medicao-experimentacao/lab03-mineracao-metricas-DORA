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

`<C preenche (#49, #50)>`
