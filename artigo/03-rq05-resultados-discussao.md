# RQ05 — Frequência de deploy e taxa de falha

Os resultados reais estão integrados à [Seção 3.6 de Resultados](03-resultados.md#36-rq-05-frequência-de-deploy--taxa-de-falha) e à [Seção 4.6 de Discussão](04-discussao.md#46-rq-05-e-rq-06). A hipótese original permanece em [`01-introducao.md`](01-introducao.md).

## Reprodução

```bash
python -m analises.rq05 --entrada output/metricas_repos.csv \
  --coluna-frequencia frequencia_semana --saida output/analises/rq05 --escala-x log
```

As estimativas, pares, exclusões e figuras ficam em [`output/analises/rq05/`](../output/analises/rq05/); o relatório registra o hash da entrada e a versão do SciPy. A documentação do comando e das unidades está em [`analises/rq05.md`](../analises/rq05.md).

O dataset e as análises foram regenerados com a v3, validada na #34 (precisão 0,6818; recall 0,7282; F1 0,7042). Na RQ05, o coeficiente de Spearman para CFR (b) passou de 0,7655 com a v1 para 0,6520 com a v3 (p ≈ 1,4183 × 10⁻³⁷; n = 299). A família completa de Holm da RQ06 também foi recalculada. Os achados devem considerar os erros remanescentes e o uso da mesma amostra-ouro para refinamento e avaliação, conforme a metodologia.

## Conferência para a integração ao artigo

A tabela da RQ05 foi conferida contra `correlacoes.csv`, incluindo n,
exclusões, coeficientes e p-valores. As figuras referenciadas existem e os
links para as seções de Resultados e Discussão foram verificados. Os valores
são arredondados apenas na apresentação; o CSV preserva os valores completos.

A conferência também cobriu as tabelas e afirmações da RQ06 contra
`output/analises/rq06/testes.csv` e `descritivas.csv`, incluindo a família de
24 testes, 13 p-valores brutos abaixo de 0,05 e 8 após Holm. As hipóteses
originais não foram alteradas. A ausência de significância não foi tratada
como prova de equivalência entre grupos. A revisão cruzada do grupo continua pendente; a validação da #34 e sua
aplicação ao dataset estão registradas. Esta entrega registra a parte de
RQ05 e RQ06 do integrante B na #51.
