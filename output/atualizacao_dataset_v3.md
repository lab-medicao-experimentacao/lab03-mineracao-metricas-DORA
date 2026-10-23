# Atualização do dataset com a heurística v3 (#34)

Em 22/10/2026, o dataset dos 300 repositórios e as análises afetadas foram regenerados offline com a **v3** de `metricas.cfr.release_corretiva`. A execução usa os mesmos CSVs da coleta e os mesmos consensos; não há nova coleta nem alteração dos rótulos. Esta atualização substitui a decisão anterior de manter a v1 por restrição de prazo.

A v3 obteve precisão **0,6818**, recall **0,7282** e F1 **0,7042** na amostra-ouro. O código de CFR usado coincide integralmente com o preservado em [`validacao_heuristica/v3/codigo.json`](validacao_heuristica/v3/codigo.json). As três avaliações e suas previsões permanecem preservadas. Refinamento e avaliação usaram a mesma amostra, o que pode tornar o desempenho otimista para outros projetos.

## Comandos executados

```bash
python -m pipeline.dataset --config config.yaml
python -m analises.rq01_rq04 --config config.yaml
python -m analises.rq05 --entrada output/metricas_repos.csv --coluna-frequencia frequencia_semana --saida output/analises/rq05 --escala-x log
python -m analises.rq06 --entrada output/metricas_repos.csv --saida output/analises/rq06
python -m analises.rq07_sensibilidade --config config.yaml
```

## Conferência da atualização

- Foram preservados os mesmos 300 repositórios e sua ordem.
- Somente `cfr_entrega` e `n_releases_falharam` mudaram, em 200 repositórios. Todas as outras colunas permaneceram idênticas, incluindo contagens de censura, metadados, lead times, frequência, CI, recuperação e classificação C1.
- Há 10.796 releases avaliadas e 292 censuradas. As identidades de contagem e os limites das frações foram conferidos.
- A correlação de entrega foi conferida diretamente com `spearmanr`; a família completa de 24 testes foi recalculada e Holm foi conferido por ordenação dos p-valores e máximos acumulados.
- A RQ06 conserva oito testes significativos após Holm; os p-valores corrigidos foram atualizados também para as métricas cujo valor não mudou.

| Indicador | Dataset com v1 | Dataset com v3 |
|---|---:|---:|
| Mediana de CFR (b) | 40,00 % | 20,00 % |
| Releases seguidas por corretiva em até 7 dias | 7.131 | 4.979 |
| Spearman: frequência × CFR (b), n = 299 | 0,7655 | 0,6520 |
| Mudança de categoria geral C1 × C2 | 48,67 % | 41,67 % |
| Mudança de categoria geral C2 × C3 | 42,33 % | 32,67 % |

Os resultados e a discussão do artigo foram atualizados com as novas tabelas, figuras e limitações. A classificação de referência C1 continua usando CFR de CI (a); a v3 afeta CFR (b) e, portanto, a combinação C2 da sensibilidade.

## Identificação dos artefatos

- Dataset anterior (v1): `d24f38c59e5d36f229130a1ae6542f519889d11a69f8fcebb46cd10f95b8c81c`.
- Dataset atualizado (v3): `a10317d0576780d6321fbe8ad9475b27c7b227f827c9eef69aa1e3e491e30f22`.
- Código da avaliação v3 (registro #34): `267b3683c3684905b8a0cb8bb6fa4e5f1b35239326f0b2de369d73acd594b6c1`.
- Código de CFR aplicado: `737a3e32e94feabb7fcdaad7217a56a14c932bb9e040687d6a984634375cb155`.
- Código da consolidação do dataset: `463146b7489871eb0f691309ff64a150c9fac10cfae61e33065bb0471a9e4ec8`.

Os manifestos da RQ06 e o relatório da RQ05 identificam o mesmo dataset atualizado por SHA-256. O arquivo `commits.csv` permanece local e ignorado pelo Git.

| Entrada local | SHA-256 |
|---|---|
| `config.yaml` | `9cb78605f00b1e99dd3dc78b48a866d4b6d22d458652d4e3baeff27791926050` |
| `output/repos.csv` | `8107a0519761139d6c0e8f130180b31ff0fac6803d8267e73ae80f95daecfbe1` |
| `data/processed/commits.csv` | `826bd2abc282c0a3f8aa5e651b83234a45f679e65ec0b11ce0f909289242329f` |
| `data/processed/releases.csv` | `fca9b64dc9d81bdaa1aa7722732249d85d3f8fb227052a778f04c10c18338140` |
| `data/processed/releases_sem_compare.csv` | `a591a3c1ce5b062661646d201ead18609bb74408e3b0b2cdd4078c6695dd28aa` |
| `data/processed/runs.csv` | `16e9c6bc8b0075368e0cfe3c8499a0fe685dba38aeb473ab02e44a93645cfd90` |
| `data/processed/runs_meses_saturados.csv` | `0bbdb738cd6a6ed7a78656afba6e4c3535769dc750ca48573c0c4808db3cf5b5` |
| `data/processed/tags.csv` | `b3aecc7efec95d0a3b3afbfa3c15b4d83d7df0a58290573d48eb3805a23b66f8` |
| `output/amostra_ouro/consenso_repos.csv` | `3c0daea26a16d77a426647100ae4f510b10fa5912047b340a2f41cf4bf0a668f` |
