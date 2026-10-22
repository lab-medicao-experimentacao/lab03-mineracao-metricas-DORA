# 3. Resultados

> Rascunho em Markdown da seção de Resultados (Lab03S03, Issue #51). A versão final vai para o template SBC.
> Divisão: A → RQ 01 a RQ 04 e classificação C1 (#48) · B → RQ 05 (#46) e RQ 06 (#47) · C → RQ 07 (#49) e RQ 08 (#50). Revisão pelos três.
> Todo número vem de um arquivo de `output/analises/`; os números das RQ 01 a 04 vêm de `output/analises/rq01_rq04/` sobre `output/metricas_repos.csv` (#35). Nenhum valor é digitado sem a saída correspondente.

Todas as métricas são resumidas por mediana e intervalo interquartil (IQR), calculados sobre os repositórios com valor; a quantidade de repositórios sem valor é informada em cada tabela. As tabelas e figuras desta seção para as RQ 01 a RQ 04 são geradas por `python -m analises.rq01_rq04 --config config.yaml` (`output/analises/rq01_rq04/`).

## 3.1 RQ 01: frequência de deploys

| Métrica | n | Mediana | Q1 | Q3 | IQR | Mínimo | Máximo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Frequência (releases/semana) | 300 | 0,35 | 0,17 | 0,70 | 0,52 | 0,10 | 33,64 |

A mediana é de 0,35 release por semana, cerca de 1,5 release por mês. Metade dos repositórios publica entre 0,17 e 0,70 release por semana (de 0,7 a 3 releases por mês). A distribuição é fortemente assimétrica à direita: só 46 repositórios (15,3 %) publicam ao menos uma release por semana, e o máximo, `bluesky-social/atproto`, publicou 1.754 releases na janela (33,6 por semana). O mínimo, 0,10, corresponde ao piso do critério de inclusão (5 releases em 52 semanas).

Nas categorias DORA, 157 repositórios (52,3 %) são Medium, 97 (32,3 %) Low, 45 (15,0 %) High e apenas 1 (0,3 %) Elite (`bluesky-social/atproto`). A Figura `rq01_frequencia.png` mostra a distribuição com os cortes das categorias.

## 3.2 RQ 02: lead time

| Variante | n | Mediana (h) | Q1 (h) | Q3 (h) | IQR (h) | Mínimo (h) | Máximo (h) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| (a) por release | 300 | 187,51 | 25,71 | 840,06 | 814,35 | 0,00 | 83.120,66 |
| (b) por commit | 300 | 188,55 | 34,09 | 677,05 | 642,96 | 0,01 | 56.327,19 |

As medianas das duas variantes são praticamente iguais, cerca de 7,8 dias (a) e 7,9 dias (b), pouco acima do corte de uma semana entre High e Medium. A dispersão é menor na variante (b): o intervalo interquartil vai de 1,1 a 35,0 dias em (a) e de 1,4 a 28,2 dias em (b). As duas distribuições têm cauda longa: o máximo, `phpseclib/phpseclib`, passa de 9 anos em (a) e de 6 anos em (b).

Comparando repositório a repositório, o lead time por commit (b) é menor que o por release (a) em 183 dos 300 repositórios (61,0 %), igual em 1 e maior em 116. A mediana da razão (b)/(a) é 0,72. A Figura `rq02_lead_time.png` mostra as duas variantes em escala logarítmica.

## 3.3 RQ 03: taxa de falha das mudanças

| Variante | n | Ausentes | Mediana | Q1 | Q3 | IQR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| (a) proxy de CI | 300 | 0 | 6,05 % | 2,47 % | 14,31 % | 11,83 % |
| (b) proxy de entrega | 299 | 1 | 40,00 % | 16,67 % | 66,43 % | 49,77 % |

As duas variantes contam histórias diferentes. No proxy de CI (a), a mediana é de 6,05 % de execuções com falha, e 228 repositórios (76,0 %) ficam na faixa Elite (≤ 15 %). No proxy de entrega (b), a mediana é de 40,0 %, e a dispersão é muito maior.

No CFR (b), foram avaliadas 10.796 releases, das quais 7.131 (66,1 % no agregado) foram seguidas por uma release corretiva em até 7 dias; 292 releases, publicadas nos últimos 7 dias da janela, foram censuradas. Um repositório não tem CFR (b) porque todas as suas releases foram censuradas. `<preencher após #34: F1 da heurística usada>` A Figura `rq03_cfr.png` compara as duas variantes.

## 3.4 RQ 04: tempo de recuperação

| Métrica | n | Ausentes | Mediana (h) | Q1 (h) | Q3 (h) | IQR (h) | Máximo (h) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tempo de recuperação | 272 | 28 | 4,19 | 0,95 | 21,51 | 20,56 | 3.958,31 |

A mediana do tempo de recuperação é de 4,2 horas, e metade dos repositórios se recupera entre 1 hora e 21,5 horas. Foram observados 9.862 episódios de falha. Só 1,32 % deles foram censurados, isto é, não tiveram sucesso até o fim da janela e entram na mediana com o tempo decorrido até lá; a mediana da proporção censurada por repositório é zero; 80 repositórios têm ao menos um episódio censurado. Os 28 repositórios sem nenhum episódio ficam sem valor nesta métrica: em 19 deles, nenhuma execução válida falhou na janela.

A Figura `rq04_recuperacao.png` mostra a distribuição em escala logarítmica, com os cortes DORA.

## 3.5 Classificação DORA de referência (C1)

A combinação C1 usa a release publicada como unidade de deploy, o lead time por release (a) e o CFR por proxy de CI (a), além do tempo de recuperação. Cada repositório recebe uma categoria por métrica e uma categoria geral (mediana dos pontos, arredondada para baixo, com no mínimo três métricas com valor).

| Categoria | Frequência | Lead time (a) | CFR (a) | Recuperação | Geral |
| --- | ---: | ---: | ---: | ---: | ---: |
| Elite | 1 (0,3 %) | 72 (24,0 %) | 228 (76,0 %) | 72 (24,0 %) | 24 (8,0 %) |
| High | 45 (15,0 %) | 75 (25,0 %) | 45 (15,0 %) | 139 (46,3 %) | 126 (42,0 %) |
| Medium | 157 (52,3 %) | 71 (23,7 %) | 13 (4,3 %) | 38 (12,7 %) | 115 (38,3 %) |
| Low | 97 (32,3 %) | 82 (27,3 %) | 14 (4,7 %) | 23 (7,7 %) | 35 (11,7 %) |
| Sem classificação | 0 | 0 | 0 | 28 (9,3 %) | 0 |

Na categoria geral, 126 repositórios (42,0 %) são High, 115 (38,3 %) Medium, 35 (11,7 %) Low e 24 (8,0 %) Elite (Figura `c1_distribuicao.png`). Todos os 300 recebem categoria geral: 272 com as quatro métricas e 28 com três (sem tempo de recuperação). A classificação calculada aqui coincide, nos 300 repositórios e nas cinco colunas, com a gravada no dataset da #35, que foi implementada de forma independente.

## 3.6 RQ 05: frequência de deploy × taxa de falha

`<B preenche (#46)>`

## 3.7 RQ 06: características associadas ao desempenho

`<B preenche (#47)>`

## 3.8 RQ 07: sensibilidade à definição operacional

As três combinações (C1, C2 e C3, definidas na Seção 2.6) foram comparadas par a par por `python -m analises.rq07_sensibilidade --config config.yaml` (`output/analises/rq07/`). Todos os 300 repositórios receberam categoria geral nas três combinações, então nenhum foi excluído dos pares.

| Unidade de deploy | n | Mediana (por semana) | Q1 | Q3 | IQR |
| --- | ---: | ---: | ---: | ---: | ---: |
| Release (C1) | 300 | 0,35 | 0,17 | 0,70 | 0,52 |
| Release + pré-release (C2) | 300 | 0,38 | 0,19 | 0,82 | 0,63 |
| Tag (C3) | 300 | 0,47 | 0,21 | 0,93 | 0,72 |

| Categoria geral | C1 | C2 | C3 |
| --- | ---: | ---: | ---: |
| Elite | 24 (8,00 %) | 4 (1,33 %) | 21 (7,00 %) |
| High | 126 (42,00 %) | 65 (21,67 %) | 135 (45,00 %) |
| Medium | 115 (38,33 %) | 188 (62,67 %) | 121 (40,33 %) |
| Low | 35 (11,67 %) | 43 (14,33 %) | 23 (7,67 %) |

| Par | Comparados | Mudaram | Melhoraram | Pioraram | Adjacentes | Saltos | κ ponderado | Interpretação |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C1 × C2 | 300 | 146 (48,67 %) | 27 | 119 | 130 | 16 | 0,34 | razoável |
| C1 × C3 | 300 | 72 (24,00 %) | 44 | 28 | 71 | 1 | 0,70 | substancial |
| C2 × C3 | 300 | 127 (42,33 %) | 123 | 4 | 122 | 5 | 0,44 | moderada |

"Melhoraram" e "pioraram" comparam a categoria da segunda combinação do par com a da primeira. A imensa maioria das mudanças é para uma categoria vizinha: 130 de 146 em C1 × C2, 71 de 72 em C1 × C3 e 122 de 127 em C2 × C3. Os 22 saltos de duas ou mais categorias ocorrem sobretudo entre C1 e C2 (16). As matrizes de transição estão na Figura `transicao_pares.png`, e a distribuição por combinação, na Figura `distribuicao_combinacoes.png`.

| Par | Métrica | Mudaram | Melhoraram | Pioraram |
| --- | --- | ---: | ---: | ---: |
| C1 × C2 | Frequência | 17 (5,67 %) | 17 | 0 |
| C1 × C2 | Lead time | 123 (41,00 %) | 65 | 58 |
| C1 × C2 | CFR | 224 (74,92 %), de 299 | 19 | 205 |
| C1 × C3 | Frequência | 41 (13,67 %) | 41 | 0 |
| C1 × C3 | Lead time | 123 (41,00 %) | 65 | 58 |
| C1 × C3 | CFR | 0 (0,00 %) | 0 | 0 |
| C2 × C3 | Frequência | 26 (8,67 %) | 26 | 0 |
| C2 × C3 | Lead time | 0 (0,00 %) | 0 | 0 |
| C2 × C3 | CFR | 224 (74,92 %), de 299 | 205 | 19 |

A tabela por métrica mostra de onde vem a mudança da categoria geral. A frequência só muda para melhor e em poucos repositórios (5,67 % ao incluir pré-releases e 13,67 % ao usar tags). A troca do lead time por release (a) pelo lead time por commit (b) muda a categoria de 41,00 % dos repositórios, quase metade para cada lado. A troca do CFR de CI (a) pelo CFR de entrega (b) muda a categoria de 74,92 % dos repositórios (299 com CFR (b)), e em 205 deles para pior.
