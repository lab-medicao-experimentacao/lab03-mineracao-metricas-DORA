# 3. Resultados

> Rascunho em Markdown da seção de Resultados (Lab03S03, Issue #51). A versão final vai para o template SBC.
> Divisão: A → RQ 01 a RQ 04 e classificação C1 (#48) · B → RQ 05 (#46) e RQ 06 (#47) · C → RQ 07 (#49) e RQ 08 (#50). Revisão pelos três.
> Todo número vem de um arquivo de `output/analises/`; trechos `<preencher …>` são completados quando o dataset da #35 existir. Nenhum valor é digitado sem a saída correspondente.

Todas as métricas são resumidas por mediana e intervalo interquartil (IQR), calculados sobre os repositórios com valor; a quantidade de repositórios sem valor é informada em cada tabela. As tabelas e figuras desta seção para as RQ 01 a RQ 04 são geradas por `python -m analises.rq01_rq04 --config config.yaml` (`output/analises/rq01_rq04/`).

## 3.1 RQ 01: frequência de deploys

`<preencher após #35: tabela da RQ 01 de resumo.md (n, mediana, Q1, Q3, IQR em releases/semana)>`

`<preencher após #35: distribuição das categorias de frequência (distribuicao_c1.csv) e figura rq01_frequencia.png>`

## 3.2 RQ 02: lead time

`<preencher após #35: tabela das variantes (a) e (b) em horas (resumo.md), com conversão para dias no texto>`

`<preencher após #35: comparacao_lead_time.csv — em quantos repositórios (b) < (a) e mediana da razão b/a; figura rq02_lead_time.png>`

## 3.3 RQ 03: taxa de falha das mudanças

`<preencher após #35: tabela das variantes (a) proxy de CI e (b) proxy de entrega, em %>`

`<preencher após #35/#34: releases avaliadas, que falharam e censuradas no CFR (b) (censura_e_cobertura.csv); F1 da heurística usada; figura rq03_cfr.png>`

## 3.4 RQ 04: tempo de recuperação

`<preencher após #35: tabela em horas, total de episódios e mediana da proporção censurada; repositórios sem episódio>`

`<preencher após #35: figura rq04_recuperacao.png>`

## 3.5 Classificação DORA de referência (C1)

A combinação C1 usa a release publicada como unidade de deploy, o lead time por release (a) e o CFR por proxy de CI (a), além do tempo de recuperação. Cada repositório recebe uma categoria por métrica e uma categoria geral (mediana dos pontos, arredondada para baixo, com no mínimo três métricas com valor).

`<preencher após #35: distribuição da categoria geral (distribuicao_c1.csv, c1_distribuicao.png) e nº de repositórios com 4, 3 e ≤ 2 métricas>`

## 3.6 RQ 05: frequência de deploy × taxa de falha

`<B preenche (#46)>`

## 3.7 RQ 06: características associadas ao desempenho

`<B preenche (#47)>`

## 3.8 RQ 07: sensibilidade à definição operacional

`<C preenche (#49)>`
