# RQ05 — Frequência de deploy e taxa de falha

Os resultados reais estão integrados à [Seção 3.6 de Resultados](03-resultados.md#36-rq-05-frequência-de-deploy--taxa-de-falha) e à [Seção 4.6 de Discussão](04-discussao.md#46-rq-05-e-rq-06). A hipótese original permanece em [`01-introducao.md`](01-introducao.md).

## Reprodução

```bash
python -m analises.rq05 --entrada output/metricas_repos.csv \
  --coluna-frequencia frequencia_semana --saida output/analises/rq05 --escala-x log
```

As estimativas, pares, exclusões e figuras ficam em [`output/analises/rq05/`](../output/analises/rq05/); o relatório registra o hash da entrada e a versão do SciPy. A documentação do comando e das unidades está em [`analises/rq05.md`](../analises/rq05.md).

A RQ05 apresentada usa o dataset calculado com a **v1**. A validação da #34 obteve precisão de 0,3755, recall de 0,9515 e F1 de 0,5385 para essa versão. A v3 atingiu F1 de 0,7042 somente na amostra-ouro. Por restrição de prazo, o grupo mantém o dataset e as análises existentes: aplicar v2 ou v3 exigiria recalcular o CFR (b), regenerar o dataset e reexecutar e revisar as análises afetadas, sem tempo disponível antes da entrega. Os resultados da RQ05 devem ser interpretados com a limitação da v1; o F1 da v3 não se aplica a eles.

## Conferência para a integração ao artigo

A tabela da RQ05 foi conferida contra `correlacoes.csv`, incluindo n,
exclusões, coeficientes e p-valores. As figuras referenciadas existem e os
links para as seções de Resultados e Discussão foram verificados. Os valores
são arredondados apenas na apresentação; o CSV preserva os valores completos.

A conferência também cobriu as tabelas e afirmações da RQ06 contra
`output/analises/rq06/testes.csv` e `descritivas.csv`, incluindo a família de
24 testes, 13 p-valores brutos abaixo de 0,05 e 8 após Holm. As hipóteses
originais não foram alteradas. A ausência de significância não foi tratada
como prova de equivalência entre grupos. A revisão cruzada do grupo continua pendente. A validação da #34 está
registrada, com a limitação da v1 explicitada acima; esta entrega registra a parte de
RQ05 e RQ06 do integrante B na #51.
