# 4. Discussão

> Rascunho em Markdown da seção de Discussão (Lab03S03, Issue #51). A versão final vai para o template SBC.
> Divisão igual à dos Resultados: A → RQ 01 a RQ 04 (#48) · B → RQ 05 e RQ 06 · C → RQ 07 e RQ 08. Revisão pelos três.
> Cada subseção confronta a hipótese da introdução com os resultados da seção 3; trechos `<preencher …>` dependem dos números da #35.

## 4.1 RQ 01: frequência de deploys

*Hipótese (introdução):* mediana na faixa Medium, distribuição assimétrica à direita, poucos Elite concentrados em publicação automatizada e Low menos comum por causa do critério de inclusão (≥ 5 releases na janela).

`<preencher após #35: a hipótese se confirma? Quais repositórios formam a cauda Elite e por quê?>`

O critério de inclusão impõe um piso de cerca de 0,1 release por semana, o que limita, por construção, a proporção de repositórios Low; esse viés de seleção é retomado nas ameaças à validade.

## 4.2 RQ 02: lead time

*Hipótese (introdução):* a variante por commit (b) fica abaixo da variante por release (a) na maioria dos repositórios, porque a (a) é determinada pelo commit mais antigo de cada release.

`<preencher após #35: proporção de repositórios com (b) < (a), razão b/a e exemplos de releases em que um commit antigo domina a variante (a)>`

A data usada é `commit.author.date`, que *rebases* e *squash merges* podem deslocar; o efeito sobre as duas variantes é discutido nas ameaças à validade.

## 4.3 RQ 03: taxa de falha das mudanças

*Hipótese (introdução):* `<preencher: hipótese de C, escrita antes dos dados>`

`<preencher após #35/#34: diferença entre falha de pipeline (a) e falha percebida na entrega (b); efeito da precisão/recall da heurística sobre o CFR (b); peso das releases censuradas>`

## 4.4 RQ 04: tempo de recuperação

*Hipótese (introdução):* `<preencher: hipótese de C, escrita antes dos dados>`

`<preencher após #35: o que a mediana e a proporção de episódios censurados indicam; repositórios sem episódio de falha e a decisão de mantê-los fora da mediana da RQ 04>`

## 4.5 Classificação de referência (C1)

`<preencher após #35: como a categoria geral se distribui e quais métricas puxam a classificação para cima ou para baixo; quantos repositórios dependem da regra de três métricas>`

## 4.6 RQ 05 e RQ 06

`<B preenche (#46, #47)>`

## 4.7 RQ 07 e RQ 08

`<C preenche (#49, #50)>`
