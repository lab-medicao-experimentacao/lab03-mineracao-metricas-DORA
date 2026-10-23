# RQ06 — Características associadas ao desempenho DORA

Entrada SHA-256: `a10317d0576780d6321fbe8ad9475b27c7b227f827c9eef69aa1e3e491e30f22`. SciPy 1.14.1; statsmodels 0.14.4.

Fatores: estrelas, contribuidores, idade e tipo de projeto. As seis variantes são analisadas, incluindo CFR (b), cuja interpretação considera a validação da versão usada no dataset (#34). Holm usa uma única família de todos os testes calculáveis; α = 0,05. O mínimo é de cinco observações válidas em cada grupo. Testes inviáveis ficam sem p-valor ou rejeição, com motivo explícito.

| Fator | Métrica | n | Teste | Estatística | p bruto | p Holm | Efeito | Rejeita Holm | Situação |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| stars | frequencia_semana | 300 | kruskal_wallis | 3.21458 | 0.359709 | 1 | 0.0107511 | não | calculado |
| stars | lead_time_release_horas | 300 | kruskal_wallis | 14.5222 | 0.002274 | 0.038658 | 0.0485693 | sim | calculado |
| stars | lead_time_commit_horas | 300 | kruskal_wallis | 6.85865 | 0.0765423 | 0.841965 | 0.0229386 | não | calculado |
| stars | cfr_ci | 300 | kruskal_wallis | 0.733556 | 0.865284 | 1 | 0.00245336 | não | calculado |
| stars | cfr_entrega | 299 | kruskal_wallis | 5.75008 | 0.124423 | 1 | 0.0192956 | não | calculado |
| stars | recuperacao_mediana_horas | 272 | kruskal_wallis | 0.338883 | 0.952557 | 1 | 0.00125049 | não | calculado |
| contributors | frequencia_semana | 300 | kruskal_wallis | 8.14726 | 0.0430642 | 0.516771 | 0.0272484 | não | calculado |
| contributors | lead_time_release_horas | 300 | kruskal_wallis | 70.5355 | 3.27786e-15 | 7.53908e-14 | 0.235905 | sim | calculado |
| contributors | lead_time_commit_horas | 300 | kruskal_wallis | 43.2235 | 2.20624e-09 | 4.19185e-08 | 0.14456 | sim | calculado |
| contributors | cfr_ci | 300 | kruskal_wallis | 5.18723 | 0.15859 | 1 | 0.0173486 | não | calculado |
| contributors | cfr_entrega | 299 | kruskal_wallis | 30.1255 | 1.29866e-06 | 2.33758e-05 | 0.101092 | sim | calculado |
| contributors | recuperacao_mediana_horas | 272 | kruskal_wallis | 9.96802 | 0.0188399 | 0.263759 | 0.0367824 | não | calculado |
| idade_dias | frequencia_semana | 300 | kruskal_wallis | 44.602 | 1.12418e-09 | 2.24836e-08 | 0.149171 | sim | calculado |
| idade_dias | lead_time_release_horas | 300 | kruskal_wallis | 74.2166 | 5.33326e-16 | 1.27998e-14 | 0.248216 | sim | calculado |
| idade_dias | lead_time_commit_horas | 300 | kruskal_wallis | 55.8539 | 4.51362e-12 | 9.4786e-11 | 0.186802 | sim | calculado |
| idade_dias | cfr_ci | 300 | kruskal_wallis | 0.434341 | 0.933061 | 1 | 0.00145265 | não | calculado |
| idade_dias | cfr_entrega | 299 | kruskal_wallis | 69.2062 | 6.31268e-15 | 1.38879e-13 | 0.232236 | sim | calculado |
| idade_dias | recuperacao_mediana_horas | 272 | kruskal_wallis | 13.1283 | 0.00436727 | 0.0698764 | 0.0484438 | não | calculado |
| tipo_projeto | frequencia_semana | 60 | kruskal_wallis | 4.02549 | 0.258725 | 1 | 0.0682287 | não | calculado |
| tipo_projeto | lead_time_release_horas | 60 | kruskal_wallis | 12.294 | 0.00644108 | 0.0966162 | 0.208372 | não | calculado |
| tipo_projeto | lead_time_commit_horas | 60 | kruskal_wallis | 9.19379 | 0.0268223 | 0.348689 | 0.155827 | não | calculado |
| tipo_projeto | cfr_ci | 60 | kruskal_wallis | 1.61582 | 0.655808 | 1 | 0.0273868 | não | calculado |
| tipo_projeto | cfr_entrega | 60 | kruskal_wallis | 4.79647 | 0.187322 | 1 | 0.081296 | não | calculado |
| tipo_projeto | recuperacao_mediana_horas | 57 | kruskal_wallis | 2.34574 | 0.503814 | 1 | 0.0418883 | não | calculado |

## Medianas e IQR por grupo

| Fator | Métrica | Grupo | n | Ausentes | Mediana | Q1 | Q3 | IQR | Unidade |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| stars | frequencia_semana | Q1 | 75 | 0 | 0.383562 | 0.191781 | 0.680822 | 0.489041 | releases/semana |
| stars | frequencia_semana | Q2 | 75 | 0 | 0.306849 | 0.172603 | 0.786301 | 0.613699 | releases/semana |
| stars | frequencia_semana | Q3 | 75 | 0 | 0.306849 | 0.153425 | 0.565753 | 0.412329 | releases/semana |
| stars | frequencia_semana | Q4 | 75 | 0 | 0.364384 | 0.230137 | 0.757534 | 0.527397 | releases/semana |
| stars | lead_time_release_horas | Q1 | 75 | 0 | 72.18 | 18.9851 | 520.823 | 501.838 | horas |
| stars | lead_time_release_horas | Q2 | 75 | 0 | 146.502 | 8.55389 | 816.591 | 808.037 | horas |
| stars | lead_time_release_horas | Q3 | 75 | 0 | 206.906 | 38.3446 | 959.495 | 921.15 | horas |
| stars | lead_time_release_horas | Q4 | 75 | 0 | 431.977 | 98.8039 | 1050.44 | 951.638 | horas |
| stars | lead_time_commit_horas | Q1 | 75 | 0 | 136.005 | 27.229 | 465.038 | 437.809 | horas |
| stars | lead_time_commit_horas | Q2 | 75 | 0 | 194.126 | 28.1845 | 684.262 | 656.077 | horas |
| stars | lead_time_commit_horas | Q3 | 75 | 0 | 148.804 | 45.4254 | 562.699 | 517.274 | horas |
| stars | lead_time_commit_horas | Q4 | 75 | 0 | 346.261 | 67.7217 | 1067.48 | 999.761 | horas |
| stars | cfr_ci | Q1 | 75 | 0 | 0.0588235 | 0.0177101 | 0.146485 | 0.128775 | fração 0–1 |
| stars | cfr_ci | Q2 | 75 | 0 | 0.0743274 | 0.0264147 | 0.15161 | 0.125195 | fração 0–1 |
| stars | cfr_ci | Q3 | 75 | 0 | 0.0572687 | 0.0327228 | 0.120578 | 0.0878552 | fração 0–1 |
| stars | cfr_ci | Q4 | 75 | 0 | 0.0599251 | 0.0257504 | 0.16328 | 0.137529 | fração 0–1 |
| stars | cfr_entrega | Q1 | 74 | 1 | 0.222222 | 0.139163 | 0.560455 | 0.421292 | fração 0–1 |
| stars | cfr_entrega | Q2 | 75 | 0 | 0.25 | 0 | 0.478277 | 0.478277 | fração 0–1 |
| stars | cfr_entrega | Q3 | 75 | 0 | 0.178571 | 0 | 0.402778 | 0.402778 | fração 0–1 |
| stars | cfr_entrega | Q4 | 75 | 0 | 0.1875 | 0.0717949 | 0.406763 | 0.334968 | fração 0–1 |
| stars | recuperacao_mediana_horas | Q1 | 63 | 12 | 5.53306 | 0.728611 | 22.8781 | 22.1495 | horas |
| stars | recuperacao_mediana_horas | Q2 | 70 | 5 | 3.86486 | 0.970972 | 11.6495 | 10.6785 | horas |
| stars | recuperacao_mediana_horas | Q3 | 70 | 5 | 3.39792 | 0.866042 | 23.1369 | 22.2709 | horas |
| stars | recuperacao_mediana_horas | Q4 | 69 | 6 | 5.04069 | 1.20292 | 17.7047 | 16.5018 | horas |
| contributors | frequencia_semana | Q1 | 75 | 0 | 0.441096 | 0.220548 | 0.872603 | 0.652055 | releases/semana |
| contributors | frequencia_semana | Q2 | 75 | 0 | 0.268493 | 0.153425 | 0.719178 | 0.565753 | releases/semana |
| contributors | frequencia_semana | Q3 | 75 | 0 | 0.345205 | 0.172603 | 0.594521 | 0.421918 | releases/semana |
| contributors | frequencia_semana | Q4 | 75 | 0 | 0.306849 | 0.153425 | 0.517808 | 0.364384 | releases/semana |
| contributors | lead_time_release_horas | Q1 | 75 | 0 | 23.4371 | 2.28139 | 105.64 | 103.359 | horas |
| contributors | lead_time_release_horas | Q2 | 75 | 0 | 146.502 | 27.7014 | 672.669 | 644.967 | horas |
| contributors | lead_time_release_horas | Q3 | 75 | 0 | 280.643 | 97.0824 | 931.774 | 834.691 | horas |
| contributors | lead_time_release_horas | Q4 | 75 | 0 | 753.907 | 177.388 | 1887.17 | 1709.79 | horas |
| contributors | lead_time_commit_horas | Q1 | 75 | 0 | 47.1875 | 8.40514 | 254.272 | 245.867 | horas |
| contributors | lead_time_commit_horas | Q2 | 75 | 0 | 157.82 | 25.5272 | 456.339 | 430.812 | horas |
| contributors | lead_time_commit_horas | Q3 | 75 | 0 | 234.383 | 72.3968 | 638.095 | 565.698 | horas |
| contributors | lead_time_commit_horas | Q4 | 75 | 0 | 488.881 | 176.709 | 2091.01 | 1914.3 | horas |
| contributors | cfr_ci | Q1 | 75 | 0 | 0.0765766 | 0.027032 | 0.15581 | 0.128778 | fração 0–1 |
| contributors | cfr_ci | Q2 | 75 | 0 | 0.0537383 | 0.0180461 | 0.0954906 | 0.0774445 | fração 0–1 |
| contributors | cfr_ci | Q3 | 75 | 0 | 0.0573951 | 0.0240838 | 0.134972 | 0.110888 | fração 0–1 |
| contributors | cfr_ci | Q4 | 75 | 0 | 0.0751143 | 0.0314487 | 0.17029 | 0.138841 | fração 0–1 |
| contributors | cfr_entrega | Q1 | 74 | 1 | 0.422222 | 0.185144 | 0.663265 | 0.478121 | fração 0–1 |
| contributors | cfr_entrega | Q2 | 75 | 0 | 0.2 | 0 | 0.459781 | 0.459781 | fração 0–1 |
| contributors | cfr_entrega | Q3 | 75 | 0 | 0.2 | 0 | 0.354247 | 0.354247 | fração 0–1 |
| contributors | cfr_entrega | Q4 | 75 | 0 | 0.125 | 0 | 0.327381 | 0.327381 | fração 0–1 |
| contributors | recuperacao_mediana_horas | Q1 | 67 | 8 | 1.92278 | 0.559097 | 11.194 | 10.6349 | horas |
| contributors | recuperacao_mediana_horas | Q2 | 65 | 10 | 3.50014 | 0.913472 | 20.0821 | 19.1686 | horas |
| contributors | recuperacao_mediana_horas | Q3 | 70 | 5 | 5.73243 | 1.00042 | 22.8975 | 21.8971 | horas |
| contributors | recuperacao_mediana_horas | Q4 | 70 | 5 | 5.89028 | 1.46743 | 43.5778 | 42.1103 | horas |
| idade_dias | frequencia_semana | Q1 | 75 | 0 | 0.652055 | 0.345205 | 1.18904 | 0.843836 | releases/semana |
| idade_dias | frequencia_semana | Q2 | 75 | 0 | 0.345205 | 0.191781 | 0.79589 | 0.60411 | releases/semana |
| idade_dias | frequencia_semana | Q3 | 75 | 0 | 0.287671 | 0.172603 | 0.489041 | 0.316438 | releases/semana |
| idade_dias | frequencia_semana | Q4 | 75 | 0 | 0.210959 | 0.134247 | 0.383562 | 0.249315 | releases/semana |
| idade_dias | lead_time_release_horas | Q1 | 75 | 0 | 25.9264 | 3.04986 | 71.5863 | 68.5364 | horas |
| idade_dias | lead_time_release_horas | Q2 | 75 | 0 | 169.288 | 25.1301 | 536.778 | 511.648 | horas |
| idade_dias | lead_time_release_horas | Q3 | 75 | 0 | 341.282 | 117.401 | 922.823 | 805.422 | horas |
| idade_dias | lead_time_release_horas | Q4 | 75 | 0 | 793.121 | 142.458 | 2157.15 | 2014.69 | horas |
| idade_dias | lead_time_commit_horas | Q1 | 75 | 0 | 38.475 | 7.54715 | 113.7 | 106.153 | horas |
| idade_dias | lead_time_commit_horas | Q2 | 75 | 0 | 174.154 | 30.6042 | 522.032 | 491.428 | horas |
| idade_dias | lead_time_commit_horas | Q3 | 75 | 0 | 319.99 | 133.958 | 970.643 | 836.684 | horas |
| idade_dias | lead_time_commit_horas | Q4 | 75 | 0 | 448.089 | 147.211 | 1275.05 | 1127.84 | horas |
| idade_dias | cfr_ci | Q1 | 75 | 0 | 0.0631068 | 0.0286707 | 0.14393 | 0.115259 | fração 0–1 |
| idade_dias | cfr_ci | Q2 | 75 | 0 | 0.0655738 | 0.0220236 | 0.122848 | 0.100825 | fração 0–1 |
| idade_dias | cfr_ci | Q3 | 75 | 0 | 0.0657439 | 0.0272859 | 0.143257 | 0.115971 | fração 0–1 |
| idade_dias | cfr_ci | Q4 | 75 | 0 | 0.0580247 | 0.019295 | 0.164286 | 0.144991 | fração 0–1 |
| idade_dias | cfr_entrega | Q1 | 74 | 1 | 0.529825 | 0.253676 | 0.713235 | 0.459559 | fração 0–1 |
| idade_dias | cfr_entrega | Q2 | 75 | 0 | 0.166667 | 0 | 0.394444 | 0.394444 | fração 0–1 |
| idade_dias | cfr_entrega | Q3 | 75 | 0 | 0.1875 | 0.0453297 | 0.379808 | 0.334478 | fração 0–1 |
| idade_dias | cfr_entrega | Q4 | 75 | 0 | 0 | 0 | 0.273958 | 0.273958 | fração 0–1 |
| idade_dias | recuperacao_mediana_horas | Q1 | 71 | 4 | 1.81333 | 0.67625 | 6.52069 | 5.84444 | horas |
| idade_dias | recuperacao_mediana_horas | Q2 | 67 | 8 | 3.74194 | 1.14146 | 25.4804 | 24.339 | horas |
| idade_dias | recuperacao_mediana_horas | Q3 | 69 | 6 | 6.25611 | 1.41083 | 23.1601 | 21.7493 | horas |
| idade_dias | recuperacao_mediana_horas | Q4 | 65 | 10 | 6.16917 | 1.01639 | 43.7743 | 42.7579 | horas |
| tipo_projeto | frequencia_semana | aplicação/serviço | 20 | 0 | 0.287671 | 0.134247 | 0.441096 | 0.306849 | releases/semana |
| tipo_projeto | frequencia_semana | biblioteca/framework | 25 | 0 | 0.383562 | 0.230137 | 0.747945 | 0.517808 | releases/semana |
| tipo_projeto | frequencia_semana | ferramenta CLI | 8 | 0 | 0.210959 | 0.167808 | 0.35 | 0.182192 | releases/semana |
| tipo_projeto | frequencia_semana | outro | 7 | 0 | 0.268493 | 0.210959 | 0.776712 | 0.565753 | releases/semana |
| tipo_projeto | lead_time_release_horas | aplicação/serviço | 20 | 0 | 729.485 | 210.282 | 1383.32 | 1173.04 | horas |
| tipo_projeto | lead_time_release_horas | biblioteca/framework | 25 | 0 | 192.169 | 61.1068 | 280.643 | 219.537 | horas |
| tipo_projeto | lead_time_release_horas | ferramenta CLI | 8 | 0 | 948.15 | 461.746 | 1417.07 | 955.328 | horas |
| tipo_projeto | lead_time_release_horas | outro | 7 | 0 | 8.05889 | 0.1225 | 215.9 | 215.777 | horas |
| tipo_projeto | lead_time_commit_horas | aplicação/serviço | 20 | 0 | 548.44 | 355.57 | 1692.06 | 1336.49 | horas |
| tipo_projeto | lead_time_commit_horas | biblioteca/framework | 25 | 0 | 100.769 | 22.6438 | 448.089 | 425.446 | horas |
| tipo_projeto | lead_time_commit_horas | ferramenta CLI | 8 | 0 | 626.698 | 209.334 | 1365.16 | 1155.82 | horas |
| tipo_projeto | lead_time_commit_horas | outro | 7 | 0 | 244.255 | 70.5635 | 612.701 | 542.137 | horas |
| tipo_projeto | cfr_ci | aplicação/serviço | 20 | 0 | 0.078203 | 0.0174916 | 0.145648 | 0.128157 | fração 0–1 |
| tipo_projeto | cfr_ci | biblioteca/framework | 25 | 0 | 0.0948905 | 0.0248963 | 0.184466 | 0.15957 | fração 0–1 |
| tipo_projeto | cfr_ci | ferramenta CLI | 8 | 0 | 0.0518289 | 0.0425453 | 0.0659121 | 0.0233668 | fração 0–1 |
| tipo_projeto | cfr_ci | outro | 7 | 0 | 0.0327021 | 0.00735294 | 0.153583 | 0.14623 | fração 0–1 |
| tipo_projeto | cfr_entrega | aplicação/serviço | 20 | 0 | 0.15 | 0 | 0.256944 | 0.256944 | fração 0–1 |
| tipo_projeto | cfr_entrega | biblioteca/framework | 25 | 0 | 0.3 | 0 | 0.388889 | 0.388889 | fração 0–1 |
| tipo_projeto | cfr_entrega | ferramenta CLI | 8 | 0 | 0.118462 | 0 | 0.205556 | 0.205556 | fração 0–1 |
| tipo_projeto | cfr_entrega | outro | 7 | 0 | 0.357143 | 0.201465 | 0.442222 | 0.240757 | fração 0–1 |
| tipo_projeto | recuperacao_mediana_horas | aplicação/serviço | 19 | 1 | 5.245 | 1.18444 | 11.0263 | 9.84187 | horas |
| tipo_projeto | recuperacao_mediana_horas | biblioteca/framework | 25 | 0 | 14.5483 | 2.45444 | 44.3786 | 41.9242 | horas |
| tipo_projeto | recuperacao_mediana_horas | ferramenta CLI | 8 | 0 | 8.89694 | 2.91326 | 21.1806 | 18.2673 | horas |
| tipo_projeto | recuperacao_mediana_horas | outro | 5 | 2 | 3.96333 | 1.13972 | 21.6612 | 20.5215 | horas |

## Método e limites

Quartis calculados uma vez por fator, antes de excluir métricas ausentes. Empates permanecem juntos; cortes repetidos são removidos (`qcut`, `duplicates='drop'`). Com quatro intervalos os nomes são Q1–Q4; com menos são G1–Gk. Intervalos são abertos à esquerda e fechados à direita, exceto o primeiro, que inclui o mínimo. `limites_grupos.csv` e `agrupamentos.csv` registram limites e membros. Tipo de projeto usa as categorias do consenso presentes no dataset; ausências não são imputadas. `exclusoes.csv` discrimina ausências por fator × métrica.

Kruskal-Wallis compara três ou mais grupos e reporta ε² = H/(n−1); não identifica quais pares diferem. Não há testes post hoc nesta análise. Dois grupos usam Mann-Whitney bilateral, aproximação assintótica com correção de empates e continuidade, e δ = 2U₁/(n₁n₂)−1. A ordem dos grupos é lexicográfica, registrada em `testes.csv`; δ positivo indica valores maiores no primeiro grupo. Limites de |δ|: <0,147 desprezível; <0,33 pequeno; <0,474 médio; demais grande. Não se atribuem faixas arbitrárias ao ε².

As métricas usam as unidades do dataset (horas, releases/semana e frações). Diferenças nas distribuições não demonstram causalidade nem que um grupo é superior em todas as métricas. Grupos pequenos, desbalanceamento, empates, ausências e seleção de projetos populares limitam a inferência. Não significância não demonstra equivalência. Consulte a validação da versão usada no dataset em `output/validacao_heuristica/relatorio.md` (#34) e a metodologia do artigo; refinamentos exigem regenerar o dataset e repetir toda a família de testes.

Fontes: [Kruskal-Wallis](https://docs.scipy.org/doc/scipy-1.14.1/reference/generated/scipy.stats.kruskal.html), [Mann-Whitney](https://docs.scipy.org/doc/scipy-1.14.1/reference/generated/scipy.stats.mannwhitneyu.html), [Holm](https://www.statsmodels.org/v0.14.4/generated/statsmodels.stats.multitest.multipletests.html).
