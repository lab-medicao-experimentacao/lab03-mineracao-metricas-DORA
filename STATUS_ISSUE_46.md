# Status da Issue #46 — RQ05

A análise foi executada sobre `output/metricas_repos.csv`, com 300 repositórios.
Código, testes e resultados reais foram revisados para registro no grupo de três
commits locais da #46, conforme aprovação do integrante. Não houve push ou PR.

## Entregas disponíveis

- Script offline `analises/rq05.py`, com duas correlações bilaterais de Spearman,
  validação das entradas e tratamento de ausências e variáveis constantes.
- Seis arquivos reais em `output/analises/rq05/`: correlações, pares, exclusões,
  duas dispersões PNG e relatório com hash da entrada e versão do SciPy.
- Resultados integrados à Seção 3.6 de `artigo/03-resultados.md` e discussão
  da RQ05 na Seção 4.6 de `artigo/04-discussao.md`, confrontando a hipótese.
- README, método e dicionário das saídas documentados em `analises/rq05.md`.

## Reprodução

```bash
python -m analises.rq05 --entrada output/metricas_repos.csv \
  --coluna-frequencia frequencia_semana --saida output/analises/rq05 --escala-x log
```

| Variante | n | ρ | p-valor aproximado |
|---|---:|---:|---:|
| CFR (a), CI | 300 | 0,058530 | 0,312303 |
| CFR (b), entrega | 299 | 0,765456 | 8,258862 × 10⁻⁵⁹ |

`egoist/mygo` é excluído somente do CFR (b), por ausência dessa métrica:
todas as suas releases foram censuradas no dataset. Não houve imputação.
As dispersões usam escala horizontal logarítmica, válida porque todas as
frequências são positivas; a escala não altera a correlação.

## Validação executada

- 34 testes da RQ05 passaram.
- O conteúdo exato preparado para os commits da #46 foi exportado para um
  diretório isolado, sem o código ou os testes da #47: **842 testes passaram**,
  com **100% em `metricas/`** e **98% em `analises/rq05.py`**.
- Após implementar também a RQ06 (#47), a suíte completa passou com
  **870 testes**, **100% de cobertura em `metricas/`** e **99% em `analises/rq06.py`**.
- Coeficientes conferidos independentemente por correlação de Pearson dos
  postos médios; p-valores conferidos pela distribuição t com n−2 graus de liberdade.
- A exclusão de `egoist/mygo` foi conferida contra as contagens de censura do dataset.
- Os seis arquivos da RQ05 e os sete da RQ06 foram gerados novamente em
  diretórios temporários, com bytes idênticos aos resultados locais.
- Os dois gráficos da RQ05 foram inspecionados visualmente.
- `git diff --check` passou.

Comando da suíte final:

```bash
pytest --cov=metricas --cov=analises.rq06 --cov-report=term-missing --cov-fail-under=80 -q
```

Ambiente de execução desta sessão: `/tmp/dora-issue34-venv`, com as dependências
fixadas de `requirements.txt`. O ambiente é temporário; a instalação padrão
continua sendo a documentada no README. Os avisos emitidos são de depreciação
do Pyparsing usado pelo Matplotlib, sem falhas.

## Pendências

- [ ] Incorporar precisão, recall e F1 da #34 à interpretação de CFR (b).
  A execução da #34 está bloqueada neste ambiente pela ausência dos CSVs
  processados `releases.csv` e `commits.csv`; o cache local contém apenas `.gitkeep`.
  Não foi encontrado pacote em Releases do repositório.
- [ ] Se a heurística for refinada e o dataset regenerado, repetir as análises.
- [ ] Revisão de outro integrante e CI antes da integração.
- [ ] Push, PR e atualização do Projects somente quando solicitados.

A #46 não deve ser considerada integralmente encerrada enquanto a interpretação
do proxy de entrega continuar dependente da #34. Os resultados estatísticos
atuais são reais, com essa limitação explícita no artigo.
