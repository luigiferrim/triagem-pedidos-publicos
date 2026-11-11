# Decisão: triagem de pedidos com IA

## O problema

Hoje, 8,5% dos pedidos de acesso à informação federais chegam ao órgão errado. O reencaminhado leva 4 dias a mais e sempre tem o prazo prorrogado. Nos 10 órgãos estudados, 68 de cada 1.000 pedidos são reencaminhados.

## O que testamos

Quatro formas de escolher o órgão a partir do texto do pedido:
- regras com palavras-chave;
- um modelo estatístico clássico;
- dois modelos de IA da Anthropic (Claude Haiku e Claude Sonnet).

Dois testes, com pedidos reais separados antes de qualquer ajuste: 500 de novembro e dezembro de 2025 e, para confirmar, 500 de janeiro de 2026.

| | Acerta (nov–dez/2025) | Acerta (jan/2026) | Acerta (fev/2026) | Custo por 1.000 pedidos |
|---|---|---|---|---|
| Regras | 74% | — | — | ≈ 0 |
| Modelo clássico | 89% | 88% | — | ≈ 0 |
| Claude Haiku | 91% (empate com o clássico) | — | — | US$ 0,15 |
| **Claude Sonnet** | **95%** | **95%** | **93%** | US$ 2,52 a 2,83 |

## A decisão

**O Claude Sonnet encaminha sozinho quando está seguro. Quando não está, o pedido vai para uma pessoa.**

A regra foi congelada e medida em pedidos novos, 500 em janeiro e 500 em fevereiro de 2026. Os dois meses deram resultados diferentes:

| Por 1.000 pedidos dos 10 órgãos | Hoje | **Com a IA, jan+fev/2026** | Janeiro | Fevereiro |
|---|---|---|---|---|
| Encaminhados sem pessoa | 0 | **861** | 866 | 856 |
| Para uma pessoa | — | **139** | 134 | 144 |
| Destino errado na parte automática | 68 reencaminhados | **cerca de 11 (entre 6 a 20)** + erros da triagem humana | 6 | 16 |
| Dias de atraso somados | 274 | cerca de 44 + erros da triagem humana | 24 | 64 |

- **Erro da parte automática:** 1,28% em janeiro e fevereiro somados (pode variar de 0,7% a 2,3%); 0,69% em janeiro e 1,87% em fevereiro. **A regra erra cerca de 1% a 2% e oscila de mês a mês; a meta de 1% não se sustentou em fevereiro.**
- **Como contar:** contagem direta nas amostras de 500 pedidos de cada mês, sem reponderação.
- **Triagem humana:** o erro dos ~139 pedidos que vão para uma pessoa não foi medido.
- **Custo:** US$ 2,54 por 1.000 pedidos.

**Acompanhamento de março a outubro de 2026** (150 pedidos por mês, regra congelada; README §4c):

| Mês | mar | abr | mai | jun | jul | ago | set | out | **mar–out** |
|---|---|---|---|---|---|---|---|---|---|
| Erro, regra original | 1,55% | 0,83% | 1,63% | 3,97% | 3,79% | 0,76% | 0,76% | 1,50% | **1,85%** |
| Erro, regra recalibrada com jan+fev | 1,56% | 0,83% | 1,63% | 3,28% | 3,94% | 0,77% | 0,77% | 1,52% | **1,78%** |
| Erro sem o lote do INSS (original) | 1,55% | 0,83% | 1,63% | 2,42% | 1,55% | 0,76% | 0,76% | 1,50% | **1,37%** |
| Alerta simples (>2% dois meses seguidos) | — | não | não | não | **sim** | não | não | não | |
| Alerta robusto (dois meses somados, com folga acima de 1%) | — | não | não | **sim** | **sim** | **sim** | não | não | |

- **Recalibrar não resolveu.** Com mais dados (jan+fev), a regra errou 1,78%, quase o mesmo que a original. A promessa honesta é um erro entre 1% e 2%, não 1%.
- **Os alertas de junho a agosto vieram de um único solicitante.** Foram 158 pedidos quase iguais, mandados ao INSS, sobre ex-servidores identificados pela matrícula SIAPE. A IA mandou ao MGI, que gere o SIAPE: é uma resposta defensável, um rótulo discutível em massa. Esse lote fez 5 dos 19 erros. **Sem ele, nenhum dos dois alertas dispara**, e o erro acumulado fica em 1,37%.
- **A cobertura ficou estável:** de 81% a 89% dos pedidos saíram sem pessoa, todo mês.

**Sem enviar texto a um serviço externo,** o modelo clássico com a mesma lógica cobriu 67%, com 1,5% de erro. Ficou acima da meta de 1%.

## Riscos

- **Erros com confiança alta existem.** No teste de 2025, foram 3 em 500. Em dois, a IA não sabia a qual órgão uma unidade pertence; o terceiro é um caso discutível. A regra de segurança não pega esses erros.
- **O ponto de corte foi escolhido depois do primeiro teste.** A meta original de 2% falhou duas vezes (3,1% e 2,3%). O ponto de 1% foi confirmado em dados novos, mas com 500 pedidos o erro pode chegar a 2%.
- **O erro varia de um mês para outro.** Em fevereiro de 2026, a mesma regra errou 1,87% na parte automática (IC 95% 0,95%–3,64%), acima da meta de 1%. De março a outubro, errou 1,85% (1,2%–2,9%). O limiar precisa de acompanhamento mensal.
- **Um alerta pode medir um solicitante, não o modelo.** Sem um lote repetido de um só solicitante, nenhum dos dois alertas teria disparado. Antes de reagir, é preciso olhar se os erros se concentram num solicitante.
- **Uma versão com consulta à estrutura do governo não melhorou o resultado.** Empatou com a recomendada e custa mais, então a recomendada continua sendo a mais simples.
- **Privacidade.** A máscara deixou passar nome de pessoa em 7 de 1.570 textos enviados à API (0,45%, limite inferior). No monitoramento, 4 de 1.200 textos foram com a matrícula SIAPE visível; a máscara já cobre esse caso para conjuntos novos. Antes de usar com dados reais, é preciso uma máscara revisada e um contrato com o fornecedor.
- **Dados federais, não municipais.** Uma prefeitura tem outra estrutura e outros pedidos.
- **O erro da triagem humana não foi medido.** Sem ele, o ganho líquido é uma estimativa.

## Próximo passo

**Um piloto em sombra, por um mês, numa prefeitura.** A IA sugere e o servidor decide, sem mudar o fluxo.

O piloto mede quatro coisas:
- o erro de destino atual;
- o erro do servidor;
- a cobertura e o erro da IA nesses pedidos;
- quantos pedidos não são da prefeitura.

Antes do piloto, é preciso pôr no prompt quem cuida de quê na prefeitura e definir a política de dados.

Dois ajustes de operação, ainda não implementados:
- **Checar a concentração por solicitante** antes de reagir a um alerta.
- **Agrupar pedidos quase idênticos,** para o servidor decidir uma vez por lote.

*Números: `results/*.json`. Detalhes: README.md.*
