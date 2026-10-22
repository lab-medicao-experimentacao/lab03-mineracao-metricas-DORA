# RQ 07: sensibilidade da classificação DORA

## Combinações

| Combinação | Unidade de deploy | Lead time | CFR |
| --- | --- | --- | --- |
| C1 | release | (a) | (a) |
| C2 | release + pré-release | (b) | (b) |
| C3 | tag | (b) | (a) |

## Frequência de deploys por unidade de deploy (releases ou tags por semana)

| Unidade de deploy | n | Mediana | Q1 | Q3 | IQR |
| --- | ---: | ---: | ---: | ---: | ---: |
| release | 300 | 0,35 | 0,17 | 0,70 | 0,52 |
| release + pré-release | 300 | 0,38 | 0,19 | 0,82 | 0,63 |
| tag | 300 | 0,47 | 0,21 | 0,93 | 0,72 |

## Categoria geral por combinação

| Categoria | C1 | C2 | C3 |
| --- | ---: | ---: | ---: |
| Elite | 24 (8,00 %) | 4 (1,33 %) | 21 (7,00 %) |
| High | 126 (42,00 %) | 65 (21,67 %) | 135 (45,00 %) |
| Medium | 115 (38,33 %) | 188 (62,67 %) | 121 (40,33 %) |
| Low | 35 (11,67 %) | 43 (14,33 %) | 23 (7,67 %) |
| Sem classificação | 0 (0,00 %) | 0 (0,00 %) | 0 (0,00 %) |

## Mudança de categoria geral e kappa ponderado, por par

| Par | Comparados | Excluídos | Mudaram | Melhoraram | Pioraram | Adjacentes | Saltos | κ ponderado | Interpretação |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C1xC2 | 300 | 0 | 146 (48,67 %) | 27 | 119 | 130 | 16 | 0,34 | razoável |
| C1xC3 | 300 | 0 | 72 (24,00 %) | 44 | 28 | 71 | 1 | 0,70 | substancial |
| C2xC3 | 300 | 0 | 127 (42,33 %) | 123 | 4 | 122 | 5 | 0,44 | moderada |

Melhoraram e pioraram contam a categoria da segunda combinação do par em relação à da primeira. Adjacentes mudaram uma categoria; saltos, duas ou mais. Excluídos são os repositórios sem categoria geral em alguma das duas.

## Mudança de categoria por métrica

| Par | Métrica | Comparados | Mudaram | Melhoraram | Pioraram |
| --- | --- | ---: | ---: | ---: | ---: |
| C1xC2 | Frequência | 300 | 17 (5,67 %) | 17 | 0 |
| C1xC2 | Lead time | 300 | 123 (41,00 %) | 65 | 58 |
| C1xC2 | CFR | 299 | 224 (74,92 %) | 19 | 205 |
| C1xC3 | Frequência | 300 | 41 (13,67 %) | 41 | 0 |
| C1xC3 | Lead time | 300 | 123 (41,00 %) | 65 | 58 |
| C1xC3 | CFR | 300 | 0 (0,00 %) | 0 | 0 |
| C2xC3 | Frequência | 300 | 26 (8,67 %) | 26 | 0 |
| C2xC3 | Lead time | 300 | 0 (0,00 %) | 0 | 0 |
| C2xC3 | CFR | 299 | 224 (74,92 %) | 205 | 19 |

## Matriz de transição C1 → C2

Linhas: categoria em C1; colunas: em C2.

| C1 \ C2 | Elite | High | Medium | Low |
| --- | ---: | ---: | ---: | ---: |
| Elite | 2 | 15 | 6 | 1 |
| High | 2 | 37 | 78 | 9 |
| Medium | 0 | 13 | 92 | 10 |
| Low | 0 | 0 | 12 | 23 |

## Matriz de transição C1 → C3

Linhas: categoria em C1; colunas: em C3.

| C1 \ C3 | Elite | High | Medium | Low |
| --- | ---: | ---: | ---: | ---: |
| Elite | 16 | 7 | 1 | 0 |
| High | 5 | 102 | 19 | 0 |
| Medium | 0 | 26 | 88 | 1 |
| Low | 0 | 0 | 13 | 22 |

## Matriz de transição C2 → C3

Linhas: categoria em C2; colunas: em C3.

| C2 \ C3 | Elite | High | Medium | Low |
| --- | ---: | ---: | ---: | ---: |
| Elite | 2 | 2 | 0 | 0 |
| High | 18 | 46 | 1 | 0 |
| Medium | 1 | 83 | 103 | 1 |
| Low | 0 | 4 | 17 | 22 |
