# Validação da identificação automática de releases corretivas

A referência é o consenso humano; a classe positiva é a release corretiva. Precisão, recall e F1 são frações de 0 a 1. Denominadores nulos são registrados como 0.

| Versão | Descrição | Releases | Precisão | Recall | F1 | Meta de F1 | Situação |
|---|---|---:|---:|---:|---:|---:|---|
| v1 | Heurística inicial da Issue #28, avaliada com os commits da release commits-s02. | 300 | 0.3755 | 0.9515 | 0.5385 | 0.70 | Refinamento necessário |
| v2 | Maioria estrita de títulos corretivos entre commits informativos; exclui merges e manutenção explícita; patch SemVer apenas sem commits. | 300 | 0.6667 | 0.4466 | 0.5349 | 0.70 | Refinamento necessário |
| v3 | Distingue funcionalidades explícitas: exige maioria corretiva em releases mistas; sem funcionalidades usa título corretivo ou patch no mesmo namespace; amplia identificação de manutenção e tags prefixadas. | 300 | 0.6818 | 0.7282 | 0.7042 | 0.70 | Meta atingida |

Os valores da tabela são arredondados apenas para apresentação. A situação usa o F1 sem arredondamento, preservado nos arquivos de resultado.

## v1

Foram avaliadas 300 releases de 60 repositórios. O consenso identificou 103 corretivas, e a heurística previu 261. Foram 98 verdadeiros positivos, 163 falsos positivos, 5 falsos negativos e 34 verdadeiros negativos.

Há 17 releases sem commits disponíveis na entrada. Elas foram mantidas na comparação. Essa contagem não distingue comparações vazias de comparações indisponíveis.

Janela: `2025-10-01T00:00:00+00:00` até `2026-10-01T00:00:00+00:00` (limite final exclusivo).

Dados: `889238774c7ee9468bcb86c8f245b72ba47bdb0b9b6a4b626f82a54daf5cdeb5`. Código: `dff8a7aa76422f41b27220cd41d042d9a59886e56136bf5a9e97197de9240753`. scikit-learn: `1.5.2`.

[Resultado completo](./v1/resultado.json), [comparação por release](./v1/comparacao.csv) e [código avaliado](./v1/codigo.json).

## v2

Foram avaliadas 300 releases de 60 repositórios. O consenso identificou 103 corretivas, e a heurística previu 69. Foram 46 verdadeiros positivos, 23 falsos positivos, 57 falsos negativos e 174 verdadeiros negativos.

Há 17 releases sem commits disponíveis na entrada. Elas foram mantidas na comparação. Essa contagem não distingue comparações vazias de comparações indisponíveis.

Janela: `2025-10-01T00:00:00+00:00` até `2026-10-01T00:00:00+00:00` (limite final exclusivo).

Dados: `889238774c7ee9468bcb86c8f245b72ba47bdb0b9b6a4b626f82a54daf5cdeb5`. Código: `ae51abb7172638afd91eb09b61ea913329e94019cdb0e4fdd0c73aea625ee8f9`. scikit-learn: `1.5.2`.

[Resultado completo](./v2/resultado.json), [comparação por release](./v2/comparacao.csv) e [código avaliado](./v2/codigo.json).

## v3

Foram avaliadas 300 releases de 60 repositórios. O consenso identificou 103 corretivas, e a heurística previu 110. Foram 75 verdadeiros positivos, 35 falsos positivos, 28 falsos negativos e 162 verdadeiros negativos.

Há 17 releases sem commits disponíveis na entrada. Elas foram mantidas na comparação. Essa contagem não distingue comparações vazias de comparações indisponíveis.

Janela: `2025-10-01T00:00:00+00:00` até `2026-10-01T00:00:00+00:00` (limite final exclusivo).

Dados: `889238774c7ee9468bcb86c8f245b72ba47bdb0b9b6a4b626f82a54daf5cdeb5`. Código: `267b3683c3684905b8a0cb8bb6fa4e5f1b35239326f0b2de369d73acd594b6c1`. scikit-learn: `1.5.2`.

[Resultado completo](./v3/resultado.json), [comparação por release](./v3/comparacao.csv) e [código avaliado](./v3/codigo.json).

## Interpretação e limitações

Um F1 abaixo da meta exige examinar os erros, refinar a heurística e registrar uma nova avaliação. As tentativas anteriores devem ser relatadas, inclusive as que não atingiram a meta. Sem corretivas no consenso, não há evidência para validar a detecção dessa classe.

O refinamento e a reavaliação na mesma amostra podem produzir resultados otimistas para outros projetos. Releases de monorepos podem pertencer a pacotes diferentes, o que limita a interpretação da antecessora cronológica. Os resultados avaliam uma aproximação de release corretiva, sem comprovar incidentes em produção.
