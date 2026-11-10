# Roteiro do vídeo (2 minutos)

Tom: direto, sem jargão. Tela: `report.html` aberto no navegador, rolando de cima para baixo.

| Tempo | Tela | Fala |
|---|---|---|
| 0:00–0:20 | Os 4 indicadores no topo | "Em 2025, 8,5% dos pedidos de acesso à informação federais chegaram ao órgão errado. Os que foram reencaminhados levaram 4 dias a mais, e todos tiveram o prazo prorrogado. A pergunta é: dá para a máquina encaminhar esses pedidos, e quanto dá para automatizar sem aumentar o erro?" |
| 0:20–0:45 | Gráfico "Quatro abordagens" | "Testei quatro jeitos em 500 pedidos de novembro e dezembro, separados antes de qualquer ajuste. Regras com palavras-chave acertam 74%. Um modelo estatístico clássico, 89%. O Claude Haiku empata com ele, 91%. O Claude Sonnet acerta 95%." |
| 0:45–1:00 | Gráfico "Quanto vem só da sigla" | "Quando o pedido cita a sigla do órgão, todo mundo acerta. A diferença está nos que não citam. Ali as regras caem para 64%, e o Sonnet fica em 94%." |
| 1:00–1:28 | Curva cobertura × erro | "Mas 95% ainda é 1 erro a cada 20. Então a máquina só decide quando está segura. Nesta curva, quanto mais à direita, mais ela decide sozinha e mais erra. Congelei a regra e testei em 500 pedidos novos, de janeiro de 2026: a máquina encaminhou 87% sozinha, com 0,7% de erro. O resto foi para uma pessoa." |
| 1:28–1:45 | Tabela de custo e seção de erros | "Nesses 10 órgãos, hoje 68 em cada mil são reencaminhados. Com a regra, a parte automática erraria uns 6; a triagem humana não foi medida. A API custa menos de 3 dólares. E a IA ainda erra com confiança." |
| 1:45–2:00 | Seção "Limites" | "O que deu errado: minha meta de 2% falhou, e alguns nomes escaparam da máscara. Próximo passo: um mês de piloto em sombra numa prefeitura." |

**Nota sobre os números:** os 8,5% da abertura valem para todos os órgãos federais e incluem os "não é de competência". Os 68 por 1.000 são os reencaminhados dos 10 órgãos estudados, a régua da decisão. Os ~6 erros por 1.000 são só da parte automática (86% dos pedidos).

**Não dizer:** que a IA "resolve" o problema, nem números sem a ressalva do teste. Não mostrar texto de pedido na tela.
