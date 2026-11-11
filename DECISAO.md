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

| Por 1.000 pedidos dos 10 órgãos | Hoje | Com a IA, jan/2026 | Com a IA, fev/2026 |
|---|---|---|---|
| Encaminhados sem pessoa | 0 | cerca de 860 | cerca de 830 |
| Para uma pessoa | — | cerca de 140 | cerca de 170 |
| Reencaminhados por destino errado | 68 | cerca de 6 (entre 2 e 17) na parte automática + erros da triagem humana | cerca de 13 (entre 8 e 30) na parte automática + erros da triagem humana |
| Dias de atraso somados | 274 | cerca de 26 na parte automática + erros da triagem humana | cerca de 52 na parte automática + erros da triagem humana |

- **Erro da parte automática:** 0,69% de erro em janeiro (IC 95% 0,24–2,02%) e **1,87% em fevereiro** (IC 95% 0,95–3,64%), acima da meta de 1%.
- **Triagem humana:** o erro dos ~140 pedidos que vão para uma pessoa não foi medido.
- **Custo:** US$ 2,52 por 1.000 pedidos.

**Sem enviar texto a um serviço externo,** o modelo clássico com a mesma lógica cobriu 67%, com 1,5% de erro. Ficou acima da meta de 1%.

## Riscos

- **Erros com confiança alta existem.** No teste de 2025, foram 3 em 500. Em dois, a IA não sabia a qual órgão uma unidade pertence; o terceiro é um caso discutível. A regra de segurança não pega esses erros.
- **O ponto de corte foi escolhido depois do primeiro teste.** A meta original de 2% falhou duas vezes (3,1% e 2,3%). O ponto de 1% foi confirmado em dados novos, mas com 500 pedidos o erro pode chegar a 2%.
- **O erro varia de um mês para outro.** Em fevereiro de 2026, a mesma regra errou 1,87% na parte automática (IC 95% 0,95%–3,64%), acima da meta de 1%. O limiar precisa de acompanhamento mensal.
- **Uma versão com consulta à estrutura do governo não melhorou o resultado.** Empatou com a recomendada e custa mais, então a recomendada continua sendo a mais simples.
- **Privacidade.** A máscara deixou passar nome de pessoa em 7 de 1.570 textos enviados à API (0,45%, limite inferior). Antes de usar com dados reais, é preciso uma máscara revisada e um contrato com o fornecedor.
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

*Números: `results/*.json`. Detalhes: README.md.*
