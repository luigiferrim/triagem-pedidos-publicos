# Decisão: triagem de pedidos com IA

## O problema

Hoje, 8,5% dos pedidos de acesso à informação federais chegam ao órgão errado. O reencaminhado leva 4 dias a mais e sempre tem o prazo prorrogado. Nos 10 órgãos federais estudados, 68 de cada 1.000 pedidos são reencaminhados. **Numa prefeitura é pior:** em São Paulo, 123 de cada 1.000 pedidos de 2024 foram transferidos para outro órgão.

## O que testamos

Quatro formas de escolher o órgão a partir do texto do pedido: regras com palavras-chave, um modelo estatístico clássico e dois modelos de IA da Anthropic (Claude Haiku e Claude Sonnet). Os testes usaram pedidos reais, separados antes de qualquer ajuste, e cada regra foi congelada antes de ser medida em pedidos novos.

| | Acerta (teste de 2025) | Custo por 1.000 pedidos |
|---|---|---|
| Regras | 74% | ≈ 0 |
| Modelo clássico | 89% | ≈ 0 |
| Claude Haiku | 91% (empate com o clássico) | US$ 0,15 |
| **Claude Sonnet** | **95%** | US$ 2,83 |

## A decisão

**O Claude Sonnet encaminha sozinho quando está seguro. Quando não está, o pedido vai para uma pessoa.**

Medido em 1.200 pedidos novos de março a outubro de 2026, com a regra congelada:

| Por 1.000 pedidos dos 10 órgãos | Hoje | **Com a IA, mar–out/2026** | Histórico: jan+fev/2026 |
|---|---|---|---|
| Encaminhados sem pessoa | 0 | **855** | 861 |
| Para uma pessoa | — | **145** | 139 |
| Destino errado na parte automática | 68 reencaminhados | **cerca de 16 (entre 10 e 25)** + erros da triagem humana | 11 |
| Erro entre os encaminhados sem pessoa | — | **1,85%** (1,2% a 2,9%) | 1,28% |
| Custo de API | 0 | US$ 2,83 | US$ 2,54 |

- **A meta de 1% não foi atingida, e recalibrar não resolveu.** A regra recalibrada com janeiro e fevereiro errou 1,78%. A promessa honesta é um erro entre 1% e 2%, que oscila de mês a mês: de 0,8% a 4,0% num mês.
- **Um único solicitante pesou.** Um lote de 158 pedidos quase iguais fez 5 dos 19 erros, numa resposta defensável. Sem ele, o erro fica em 1,37%, e nenhum alerta dispara.
- **Numa prefeitura, a mesma regra errou mais.** Em São Paulo, a IA acertou 88,6% sem abstenção. Com a regra, encaminhou 78% sem pessoa, com 2,05% de erro (no teste federal equivalente, 0,94%), cerca de 16 erros por 1.000 contra 123 trocas de órgão hoje. Um limiar ajustado para SP com só 299 pedidos foi instável (2,37%).
- **Sem enviar texto a um serviço externo,** o modelo clássico, com a mesma lógica, cobriu 67% no federal em janeiro de 2026 (1,5% de erro) e só 37% em SP (1,6%), onde havia menos pedidos antigos para treinar.

## Riscos

- **Erros com confiança alta existem.** A regra de segurança não pega esses erros. Em SP, os 8 erros automáticos foram todos assim, a maioria com rótulo discutível (classificação preliminar, não revisada).
- **O erro varia de um mês para outro.** O limiar precisa de acompanhamento mensal. Antes de reagir a um alerta, é preciso ver se os erros se concentram num só solicitante.
- **Privacidade.** Nos 1.570 textos enviados e auditados até janeiro de 2026, a máscara deixou passar nome de pessoa em 7 (0,45%, limite inferior). Depois, 4 textos foram com a matrícula SIAPE visível; a máscara já cobre esse caso. Antes de usar com dados reais: máscara revisada e contrato com o fornecedor.
- **O erro da triagem humana não foi medido.** Sem ele, o ganho líquido é uma estimativa.

## Próximo passo: um mês de piloto em sombra numa prefeitura

**Em sombra quer dizer que nada muda no fluxo.** A IA sugere um órgão para cada pedido, mas a sugestão fica escondida do servidor, que decide como sempre. Assim, mede-se a IA e mede-se o servidor sem que um influencie o outro.

| Etapa | O que acontece | Quem |
|---|---|---|
| **Antes (2 semanas)** | Pôr no prompt quem cuida de quê na prefeitura, inclusive unidades e empresas municipais. Revisar a máscara numa amostra. Fechar a política de dados (contrato com o fornecedor, ou o modelo local). **Registrar antes** as métricas e o critério de decisão. | Prefeitura (ouvidoria, TI, jurídico) e equipe do projeto |
| **Semanas 1 a 4** | A IA roda em todo pedido novo e grava a sugestão, o trecho, o motivo e a certeza. O servidor triagem normalmente. | Servidores da triagem, sem trabalho extra |
| **Fim do mês** | Um servidor experiente revisa uma amostra dos casos em que IA e triagem discordaram. Calcula-se cada medida abaixo. | Equipe do projeto e um servidor revisor |

**O que o piloto mede:**
1. o erro de destino de hoje (pedidos transferidos depois da triagem);
2. o erro do servidor da triagem;
3. a cobertura e o erro da IA em cada ponto de corte;
4. quantos pedidos não são de nenhum órgão da prefeitura.

**Critério para ligar o encaminhamento automático (a registrar antes):** escolher o ponto de corte com folga, de modo que o erro da IA, já no limite de cima do intervalo de 95%, fique abaixo do erro do servidor. Um mês pode não bastar: nos 10 órgãos de SP, foram 4.288 pedidos de acesso à informação em 2025, cerca de 360 por mês, e o dev de SP, com 299, não bastou. Ou o piloto inclui também as demandas de ouvidoria e protocolo, ou se estende até ter alguns milhares de pedidos.

**Depois de ligar:** acompanhamento mensal, com o alerta de dois meses somados, a checagem de concentração por solicitante e o agrupamento de pedidos quase idênticos para o servidor decidir uma vez por lote.

**Custo da IA no piloto:** cerca de US$ 2,6 a 2,8 por 1.000 pedidos.

*Números: `results/manchete.json`, `results/marco9_comparacao.json` e os demais `results/*.json`. Detalhes: README.md. Para não técnicos: COMO_FUNCIONA.md.*
