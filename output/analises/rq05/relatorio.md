# RQ05 — Frequência de deploy × taxa de falha

SHA-256 do CSV de entrada: `d24f38c59e5d36f229130a1ae6542f519889d11a69f8fcebb46cd10f95b8c81c`.

Colunas (repositório, frequência, CFR a, CFR b): `full_name, frequencia_semana, cfr_ci, cfr_entrega`.
SciPy: 1.14.1. Teste bilateral `scipy.stats.spearmanr`.

| Variante | n total | n usado | Excluídos | ρ | p-valor | Situação |
|---|---:|---:|---:|---:|---:|---|
| cfr_ci | 300 | 300 | 0 | 0.0585299 | 0.312303 | calculado |
| cfr_entrega | 300 | 299 | 1 | 0.765456 | 8.25886e-59 | calculado |

## Leitura dos resultados

Para `cfr_ci`, maior frequência acompanhou maior CFR (associação positiva): ρ=0.0585299, p=0.312303, n=300.

Para `cfr_entrega`, maior frequência acompanhou maior CFR (associação positiva): ρ=0.765456, p=8.25886e-59, n=299.

A hipótese prévia espera associação fraca, possivelmente distinta entre os proxies. Compare a magnitude e o sinal dos dois coeficientes com essa hipótese; o p-valor isolado não mede força de associação. Amostras diferentes por ausência de dados também podem contribuir para diferenças entre os coeficientes.

ρ positivo indica que maior frequência acompanha maior CFR; ρ negativo indica que maior frequência acompanha menor CFR. Um coeficiente próximo de zero indica pouca associação monotônica observada, sem demonstrar ausência de relações não monotônicas. Nenhum desses resultados estabelece causalidade.

O CFR (a) mede falhas de CI; o CFR (b) usa releases corretivas como proxy de falhas de entrega. Versionamento e cadência de correções podem afetar o segundo. A interpretação de CFR (b) precisa incorporar a validação da #34. Esses proxies não comprovam, por si só, a afirmação DORA sobre produção.

## Exclusões e limites

Os pares completos são selecionados separadamente por variante, sem imputação. `exclusoes.csv` lista cada repositório e motivo; `pares.csv` preserva os pontos usados em cada teste e gráfico. No resumo, as contagens sem frequência e sem CFR podem se sobrepor. n < 3 ou variável constante deixa ρ e p indefinidos.

Os p-valores são os aproximados retornados por `spearmanr`, sem ajuste entre as duas variantes. A documentação do SciPy ressalta maior precisão em amostras acima de 500 observações; amostras menores exigem cautela na inferência. A seleção de projetos populares e o uso de proxies limitam a generalização.

Escala horizontal dos gráficos: `log`. Na escala symlog, a região entre 0 e 1 release/semana é linear e os valores maiores são logarítmicos; zeros são preservados. Na escala log, zero é recusado. A escala é apenas visual e não transforma os valores usados em Spearman.

Fonte: [SciPy — spearmanr](https://docs.scipy.org/doc/scipy-1.14.1/reference/generated/scipy.stats.spearmanr.html).

![CFR de CI](dispersao_cfr_ci.png)

![CFR de entrega](dispersao_cfr_entrega.png)
