# Amostra-ouro — instruções de rotulagem

Gerado por `python -m pipeline.amostra_ouro --config config.yaml` (seção 6 do enunciado, #29).
Sorteio: 60 repositórios de `output/repos.csv` (semente 42) e
5 releases de cada um, entre as publicadas (não draft, não pré-release)
de 2025-10-01 a 2026-09-30.

## Regras

1. Cada avaliador preenche **só a própria planilha** (`rotulos_<letra>_repos.csv` e
   `rotulos_<letra>_releases.csv`), **sem consultar os demais** até todos terminarem.
2. **Não consulte a saída da heurística de release corretiva** (nem o código dela) antes de
   terminar. As planilhas não a trazem de propósito.
3. Use exatamente os valores da tabela abaixo (minúsculas, com acento). Deixe `observacoes`
   para dúvidas e justificativas curtas.
4. Não altere as demais colunas, a ordem das linhas nem o separador (vírgula). Ao salvar pelo
   Excel, mantenha CSV UTF-8 separado por vírgulas; no Google Planilhas, Arquivo → Fazer
   download → CSV.

## Valores válidos

| Coluna | Valores |
|---|---|
| `tipo_projeto` | `biblioteca/framework` · `aplicação/serviço` · `ferramenta CLI` · `outro` |
| `entregas_reais` | `sim` · `não` · `incerto` |
| `corretiva` | `sim` · `não` |

- `tipo_projeto` e `entregas_reais` (planilha `_repos`): leia o README e a página de releases
  (`url_repo`, `url_releases`). `entregas_reais = sim` quando as releases são versões entregues
  a usuários (pacote, binário, deploy); `não` quando são marcos internos, snapshots automáticos
  etc.; `incerto` quando não dá para decidir.
- `corretiva` (planilha `_releases`): `sim` se a release existe principalmente para corrigir
  defeitos; decida lendo as release notes (`url_release`) e os commits desde a release anterior
  (`url_compare`; vazio quando é a primeira release publicada do repositório).

Gerar de novo não apaga planilhas com algum rótulo preenchido (só com `--forcar`).

Com as três planilhas preenchidas, `python -m pipeline.consenso --config config.yaml` calcula a
concordância (kappa de Fleiss) e o consenso; casos 1-1-1 são decididos em reunião em
`desempates.csv` (ver README).
