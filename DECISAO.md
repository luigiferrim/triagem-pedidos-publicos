# Decisão: triagem de pedidos com IA

## O problema

Hoje, 8,5% dos pedidos de acesso à informação federais chegam ao órgão errado. O reencaminhado leva 4 dias a mais e sempre tem o prazo prorrogado.

## O que testamos

Quatro formas de escolher o órgão a partir do texto do pedido:
- regras com palavras-chave;
- um modelo estatístico clássico;
- dois modelos de IA da Anthropic (Claude Haiku e Claude Sonnet).

O teste usou 500 pedidos reais de novembro e dezembro de 2025, separados antes de qualquer ajuste.

| | Acerta | Custo por 1.000 pedidos |
|---|---|---|
| Regras | 74% | ≈ 0 |
| Modelo clássico | 89% | ≈ 0 |
| Claude Haiku | 91% (empate com o clássico) | US$ 0,15 |
| **Claude Sonnet** | **95%** | US$ 2,83 |

## A decisão

**O Claude Sonnet encaminha sozinho quando está seguro. Quando não está, o pedido vai para um servidor.**

| Por 1.000 pedidos | Hoje | Com a IA |
|---|---|---|
| Encaminhados sem pessoa | 0 | cerca de 850 (no teste; precisa de confirmação) |
| Para um servidor | — | cerca de 150 |
| Reencaminhados por destino errado | 68 | cerca de 8 (entre 3 e 20) + erros do servidor |
| Dias de atraso somados | 274 | cerca de 31 + erros do servidor |

O custo de API é pequeno: US$ 2,83 por 1.000 pedidos, menos de 1 centavo de dólar por pedido.

**Alternativa sem enviar texto a um serviço externo:** o modelo clássico, com a mesma regra. Encaminha cerca de 64% sozinho, com o mesmo erro e custo zero.

## Riscos

- **Erros com confiança alta existem.** Em 500 pedidos foram 3. Em dois, a IA não sabia a qual órgão uma unidade pertence; o terceiro é um caso discutível. A regra de segurança não pega esses erros.
- **O ponto de corte foi ajustado depois de ver o teste.** A meta original de 2% falhou (deu 3,1%). O número de 0,9% de erro precisa de confirmação em dados novos.
- **Privacidade.** A máscara de dados pessoais deixou passar pelo menos 2 nomes, que foram enviados à API. Antes de usar com dados reais, é preciso uma máscara revisada e um contrato com o fornecedor.
- **Dados federais, não municipais.** Uma prefeitura tem outra estrutura e outros pedidos.
- **O erro do servidor não foi medido.** Sem ele, o ganho líquido é uma estimativa.

## Próximo passo

**Um piloto em sombra, por um mês, numa prefeitura.** A IA sugere e o servidor decide, sem mudar o fluxo.

O piloto mede quatro coisas:
- o erro de destino atual;
- o erro do servidor;
- a cobertura e o erro da IA nesses pedidos;
- quantos pedidos não são da prefeitura.

Antes do piloto, é preciso pôr no prompt quem cuida de quê na prefeitura e definir a política de dados.

*Números: `results/*.json`. Detalhes: README.md.*
