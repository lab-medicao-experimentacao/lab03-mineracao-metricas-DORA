# Instruções para IA

Antes de qualquer tarefa, leia e siga **[DIRETRIZES.md](./DIRETRIZES.md)** (regras, contratos de dados, estrutura e fluxo de Git).
O enunciado oficial é **[03 - Mineração de Métricas DORA.md](./03%20-%20Mineração%20de%20Métricas%20DORA.md)** — em caso de conflito, o enunciado vence.

Lembretes críticos:
- Todo commit referencia a Issue (`#N`). Não commitar/abrir PR sem pedido do integrante.
- Proibido usar bibliotecas de acesso à API do GitHub (PyGithub etc.). Token só via `GITHUB_TOKEN`.
- `metricas/` é puro (sem rede) e testado: `pytest --cov=metricas --cov-fail-under=80`.
- Sprint atual: **S02**. Issues, donos, dependências e passo a passo por integrante estão nas DIRETRIZES, seções 6.4 a 6.8.
- Amostra-ouro: por decisão do grupo com o professor, a IA pode preencher a planilha do avaliador que pedir (`output/amostra_ouro/rotulos_<X>_*.csv`). Nunca abrir as planilhas dos outros avaliadores antes do consenso, nunca usar a heurística de release corretiva (#28) como insumo e nunca usar `--forcar` sem pedido.
- Não editar módulo de outro integrante sem pedido (o dono de cada módulo está na seção 3 das DIRETRIZES).
