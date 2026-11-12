# Roteiro do vídeo (2 minutos)

Tom: direto, sem jargão. Tela: a Mesa de Triagem ([mesa-triagem.vercel.app](https://mesa-triagem.vercel.app/)), aberta no navegador, nas três abas.

| Tempo | Tela | Fala |
|---|---|---|
| 0:00–0:15 | Topo da Mesa (as três linhas: problema, o que faz, por 1.000) | "Quando alguém pede uma informação ao governo, escolhe para qual órgão mandar, e às vezes erra. Nos 10 órgãos federais que estudei, 68 de cada mil pedidos vão para o lugar errado e esperam 4 dias a mais. Numa prefeitura, em São Paulo, são 123 de cada mil." |
| 0:15–0:40 | Aba **Mesa**: abrir o 1º pedido da fila (um caso claro) e depois um que está "aguardando" | "A mesa lê o pedido e sugere o órgão. Ela mostra o trecho do texto que motivou a escolha e uma frase de motivo, para o servidor conferir em segundos. Quando a IA declara certeza alta, ou média com um segundo modelo concordando, o pedido segue sozinho. Quando não, como neste, ele fica na fila de uma pessoa." |
| 0:40–1:05 | Aba **Painel**: os quatro números, depois mover o controle da curva | "Comparei quatro jeitos. Regras com palavras-chave acertam 74%, um modelo estatístico, 89%, e o Claude Sonnet, 95%. Mas 95% ainda é um erro a cada 20, então a máquina só decide quando está segura. Nesta curva, quanto mais ela decide sozinha, mais erra." |
| 1:05–1:30 | Painel: tabela mês a mês, de março a outubro | "Congelei a regra e acompanhei oito meses de pedidos novos. A mesa encaminhou 85% sozinha e errou 1,85% na parte automática: uns 16 erros por mil, contra 68 hoje. A minha meta era 1%, e não foi atingida. Recalibrar não resolveu. E os alertas do meio do ano vieram de um único cidadão, com 158 pedidos quase iguais." |
| 1:30–1:50 | Aba **Numa prefeitura**: o bloco "Testado numa prefeitura: São Paulo" | "Repeti tudo em São Paulo. A IA acertou 89%, e a parte automática errou perto de 2%. Um limiar que ajustei com só 300 pedidos não se sustentou. Por isso, o próximo passo é um piloto em sombra: a IA sugere, o servidor decide, e só então se escolhe onde ligar." |
| 1:50–2:00 | Volta ao topo | "A IA não resolve sozinha, mas tira da frente do servidor os pedidos claros. O que falta medir é o erro de quem faz a triagem hoje." |

**De onde vem cada número:**
- os 68 por 1.000 e os 4 dias: `results/manchete.json` e `results/dor.json`;
- os 123 por 1.000 de SP: `results/marco9_dor.json`;
- os 74%, 89% e 95%: o teste de 2025 (`results/marco2.json` e `results/marco3.json`);
- os 85%, 1,85% e ~16 por 1.000: `results/manchete.json`;
- os 89% e "perto de 2%" de SP: `results/marco9_teste.json`.

**Não dizer:** que a IA "resolve" o problema, nem números sem a ressalva do período. Não mostrar o texto de um pedido além dos 29 exemplos públicos da Mesa.
