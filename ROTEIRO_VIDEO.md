# Roteiro do vídeo (2 minutos)

Tom: direto, sem jargão. Tela: `report.html` aberto no navegador, rolando de cima para baixo.

| Tempo | Tela | Fala |
|---|---|---|
| 0:00–0:20 | Os 4 indicadores no topo | "Em 2025, 8,5% dos pedidos de acesso à informação federais chegaram ao órgão errado. Os que foram reencaminhados levaram 4 dias a mais, e todos tiveram o prazo prorrogado. A pergunta é: dá para a máquina encaminhar esses pedidos, e quanto dá para automatizar sem aumentar o erro?" |
| 0:20–0:45 | Gráfico "Quatro abordagens" | "Testei quatro jeitos em 500 pedidos de novembro e dezembro, separados antes de qualquer ajuste. Regras com palavras-chave acertam 74%. Um modelo estatístico clássico, 89%. O Claude Haiku empata com ele, 91%. O Claude Sonnet acerta 95%." |
| 0:45–1:00 | Gráfico "Quanto vem só da sigla" | "Quando o pedido cita a sigla do órgão, todo mundo acerta. A diferença está nos que não citam. Ali as regras caem para 64%, e o Sonnet fica em 94%." |
| 1:00–1:30 | Curva cobertura × erro | "Mas 95% ainda é 1 erro a cada 20. Então a máquina só decide quando está segura. Nesta curva, quanto mais à direita, mais ela decide sozinha e mais erra. No ponto escolhido, ela encaminhou 85% dos pedidos do teste com menos de 1% de erro, e o resto foi para um servidor. Esse número ainda precisa ser confirmado em dados novos." |
| 1:30–1:45 | Tabela de custo e seção de erros | "Por mil pedidos, os encaminhamentos errados da máquina seriam cerca de 8, contra 68 hoje, mais os erros do servidor. A API custa menos de 3 dólares. Mas a IA erra com confiança: 3 casos em 500." |
| 1:45–2:00 | Seção "Limites" | "O que deu errado: minha meta de 2% falhou no teste, e dois nomes escaparam da máscara. Próximo passo: um mês de piloto em sombra numa prefeitura." |

**Não dizer:** que a IA "resolve" o problema, nem números sem a ressalva do teste. Não mostrar texto de pedido na tela.
