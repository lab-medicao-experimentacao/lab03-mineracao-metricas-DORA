# Instruções para IA

Antes de qualquer tarefa, leia e siga **[DIRETRIZES.md](./DIRETRIZES.md)** (regras, contratos de dados, estrutura e fluxo de Git).
O enunciado oficial é **[03 - Mineração de Métricas DORA.md](./03%20-%20Mineração%20de%20Métricas%20DORA.md)** — em caso de conflito, o enunciado vence.

Lembretes críticos:
- Todo commit referencia a Issue (`#N`). Não commitar/abrir PR sem pedido do integrante.
- Proibido usar bibliotecas de acesso à API do GitHub (PyGithub etc.). Token só via `GITHUB_TOKEN`.
- `metricas/` é puro (sem rede) e testado: `pytest --cov=metricas --cov-fail-under=80`.
