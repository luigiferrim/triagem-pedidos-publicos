# Progresso

Atualizado a cada marco. Os números saem dos arquivos em `results/`.

## Fase 2 (marcos 6 a 10): orçamento de API de US$ 10; a v1.0 está publicada e não muda

## Marco atual: 7, IA com ferramenta de consulta (v2); congelado, parado antes de fevereiro

**Decisões do Luigi:**
- o limiar da v2 segue o mesmo critério da v1 (maior cobertura com erro ≤ 1% no dev);
- Batch API para a v1 em fevereiro (em reavaliação, ver custo);
- um piloto de 20 pedidos do treino de 2025, só para achar bug;
- o prompt da v2 só pode ser ajustado até o fim da rodada de janeiro;
- antes do registro de fevereiro, congelar e commitar juntos o prompt, a ferramenta, a tabela, os limiares e o hash.

**Feito (sem gasto):**
- **Tabela do SIORG** (`make unidades`, `results/unidades_orgaos.json`): 15.971 unidades, da API de dados abertos, consultada em 10/11/2026.
  - **Três relações:** "interna" (unidade de um dos 10), "vinculada" (entidade com atendimento próprio, por exemplo a Fiocruz, vinculada ao MS) e "fora" (Ministério da Justiça fora da PF).
  - **PF:** dentro do SIORG ela é uma unidade do Ministério da Justiça; a subárvore dela vira "PF".
  - **Testes:** os 6 casos da análise de erros (Arquivo Nacional→MGI, SESAI→MS, SEST→MGI, SPU→MGI, CARF→MF, PGFN→MF) acertam no 1º resultado. A busca prefere a unidade mais alta na árvore.
  - **Proibido:** nenhum rótulo de treino entra na tabela, e há teste para isso.
- **Ferramenta e laço da v2** (`src/triagem/llm_v2.py`):
  - `tool_choice` auto, com no máximo 1 chamada por turno; depois de 2 chamadas, `tool_choice` none, para obrigar a resposta;
  - o mesmo JSON, os mesmos exemplos, o mesmo effort e o mesmo thinking da v1;
  - a transcrição inteira e as chamadas à ferramenta ficam no cache local;
  - os testes sem rede cobrem o limite de 2 chamadas, o `tool_result` e o cache.
- **Holdout de fevereiro de 2026** (`data/holdout_2026_02.jsonl`, fora do git): 500 pedidos, 26 reencaminhados, sem textos repetidos de 2025 nem de janeiro.
  - O hash só vai ser registrado no commit de congelamento, depois da rodada de janeiro.
  - Ninguém olhou os pedidos além das contagens.
- **Exceção da varredura para a tabela do SIORG.** Cada linha tem de existir no bruto baixado do SIORG; uma linha de outra origem faz a varredura falhar. A busca de CPF, e-mail e telefone continua valendo para o arquivo inteiro.
- **Estimativa** (`make marco7-estimar`, `results/estimativa_custo_marco7.json`).
- **Decisões novas do Luigi:**
  - a v1 de fevereiro vai por chamada normal, nas mesmas condições de janeiro, e não pela Batch API;
  - o teto da fase sobe para US$ 12, somando os Marcos 7 e 8.

**Piloto** (20 pedidos do treino de 2025, `make marco7-piloto`): **nenhum bug.**
- O JSON final saiu válido nos 20.
- Nenhum pedido passou de 2 chamadas.
- 19 de 20 leram o cache de prompt.
- A segunda passada veio inteira do cache local.
- A ferramenta foi chamada 2 vezes: "Arquivo Nacional" → MGI e "Secretaria do Tesouro Nacional" → MF.
- **O caminho das 2 chamadas não apareceu nos 20.** Testei com 2 pedidos inventados: o 3º turno saiu com `tool_choice` none e JSON válido.
- Custo: US$ 0,08.

**v2 em janeiro, o dev da v2** (`make marco7-dev`, `results/marco7_dev.json`, 500 pedidos, US$ 1,35):
- **Acurácia igual à da v1:** 95,4% [93,2–96,9], contra 95,4%. A diferença pareada é de 0,0 ponto [−1,2 a 1,2].
- **A ferramenta quase não foi usada:** 4 pedidos de 500, com 7 chamadas. Não corrigiu nem causou erro.
  - As outras diferenças são 5 pedidos que só a v2 acerta e 5 que só a v1 acerta, sem ferramenta. É variação do modelo.
- **Por que a ferramenta tem pouco espaço:** dos 23 erros da v1 em janeiro, só 1 cita uma sigla que a tabela liga ao órgão certo, e é a própria sigla "INSS". Os erros de janeiro quase nunca dependem de a qual órgão uma unidade pertence.
- **Limiar da v2** (critério da v1, maior cobertura com erro ≤ 1% no dev): média com o ML concordando e p ≥ 0,4252. No dev, cobre 89,8% com 0,89% de erro, perto da meta, como aconteceu com a v1.
- **Custo da v2:** US$ 2,70 por 1.000 pedidos, contra US$ 2,52 da v1.
- **Previsões por pedido**, sem texto e sem a entrada da ferramenta: `results/predicoes/v2_holdout_2026.jsonl`.

**Congelamento** (`make marco7-congelar`, `results/marco7_congelado.json`): prompt da v2, ferramenta, código do laço, tabela do SIORG, limiares da v1 e da v2 e hash do holdout de fevereiro, commitados juntos antes de qualquer chamada em fevereiro. Um teste confere que nada mudou.

**Gasto da fase 2 até agora:** US$ 1,45 de US$ 12.

## Marco 6: Mesa de Triagem (concluído; aguardando aprovação do Luigi para o Marco 7)

**O que foi feito**
- **`mesa/`:** site estático, sem build e sem login. Visual do DESIGN.md do Lastro (Hanken Grotesk e DM Mono, monocromático, réguas de 2 px, pílulas de 44 px), com clima neutro de serviço público e sem a marca do Lastro. Tem modo claro e escuro e funciona em 390 px.
- **Faixa do topo e aviso fixo** com os textos do Luigi. Os números (8,5%, 4 dias e 0,69%) vêm do JSON gerado por `make mesa`.
- **Painel:** os números do holdout de janeiro de 2026 e o controle de limiar.
  - O controle é calculado no navegador a partir das 500 previsões reais, em `mesa/dados/holdout.json`, só com números.
  - As marcas de 1% e 2% são os limiares escolhidos no dev (Marco 4).
  - O Playwright confere que a marca de 1% mostra 86,6% e 0,69%, e a de 2% mostra 2,33%.
- **Fila e Detalhe:** 30 exemplos escolhidos no holdout, sendo 21 automáticos certos, 6 para pessoa e os 3 erros da parte automática. Um dos erros foi removido depois (ver abaixo), e a Mesa ficou com 29.
  - Cada exemplo mostra o texto mascarado com o trecho citado destacado, a segunda opinião do ML e o motivo em uma linha.
  - Os botões "Confirmar" e "Corrigir para…" funcionam só em memória.
- **Revisão dos exemplos pelo Luigi.** Ele recusou 2, por detalhe pessoal identificável e por dado de saúde, e aprovou os 2 substitutos.
  - Antes de mostrar, eu já tinha descartado um candidato que relatava antecedente criminal (`EXCLUIDOS_POR_CONTEUDO` em `src/triagem/mesa.py`).
- **Exceção da varredura.** O `mesa/dados/exemplos.json` só passa se o hash de cada exemplo (texto, trecho e justificativa) estiver em `results/mesa_exemplos_aprovados.json`. CPF, e-mail e nomes continuam sendo procurados nesses textos.
- **Modo ao vivo**, só local (`make mesa-ao-vivo`, em 127.0.0.1:8765).
  - Mascara o texto, bloqueia se a checagem de dados pessoais achar algo, chama o Sonnet e aplica a política. O teto é de US$ 0,50 por sessão.
  - O site público não procura a API.
  - **Teste com 3 pedidos inventados: US$ 0,017.**
    - Vacina da dengue foi para o MS, com confiança alta, automático.
    - Aposentadoria foi para o INSS, com confiança alta, automático.
    - O pedido vago teve confiança baixa e foi para pessoa.
  - O servidor em si não foi aberto no meu ambiente, porque o permissionamento bloqueia abrir porta local. Testei a mesma função de classificação e o servidor tem teste sem rede.
- **Previsões do holdout por pedido, sem texto,** em `results/predicoes/holdout_2026.jsonl`.

**Gasto da fase 2: US$ 0,017** de US$ 10.

**Verificação independente:** reprovado na 1ª rodada e aprovado na 2ª. A reprovação apontou três problemas, todos corrigidos:
- alvos de toque menores que 44 px no topo;
- o status de erro da IA mostrado só pela cor na fila;
- no celular, o detalhe abrindo fora da tela e o foco perdido ao voltar.

Também foram corrigidos:
- números do painel escritos no HTML;
- o rótulo do KPI "hoje";
- a origem dos pedidos e o teto de gasto do modo ao vivo;
- "null" na fila;
- o contraste das bordas;
- falta de testes.

**Depois da verificação:** o Luigi decidiu tirar o exemplo 10265265, um dos 3 erros da IA e um relato longo e sensível, sem substituto.
- A Mesa ficou com 29 exemplos: 21 automáticos, 6 para pessoa e 2 erros da IA.
- O aviso acima da fila tira o número do JSON.
- O registro está no CSV de revisão e em `REMOVIDOS_SEM_SUBSTITUTO` (`src/triagem/mesa.py`).
- Os números do painel não mudam, porque vêm dos 500 pedidos do holdout.

## Revisão do Luigi depois do Marco 5 (10/11/2026), concluída e publicada como v1.0

**1. Revisão manual dos 50 casos** (`make revisao`, `results/revisao_manual.json`)
- **Normalização:** a sigla antes de " – "; BCB → BACEN; MJSP → PF; "Outro" conta como discordância.
- **Concordância do leigo com a base:** 30 de 50.
  - Com certeza 3: 12 de 14.
  - Com certeza 2: 15 de 22.
  - Com certeza 1: 3 de 14.
- **Origem dos 50:** saíram da amostra de treino, então regras e ML foram retreinados sem eles. Os LLMs nesses 50 custaram US$ 0,14.
- **Acertos das máquinas:** regras 40, ML 43, Haiku 45, Sonnet 47.
- **Onde o leigo chutou** (certeza 1), o Sonnet acertou 13 de 14.
- **Limitação:** a ferramenta listava MJSP no lugar de PF, então 3 pedidos da PF ficaram como "Outro". Está em DADOS.md §7b.

**2. Os 3 erros contestados pelo verificador.** O Luigi ficou com o verificador nos três, e a contagem passou de 7/6/4/2/1 para 8/6/5/0/1.

**3. Nomes enviados à API.** Um detector offline (`make pii-detector`) procura três padrões:
- prenome do IBGE seguido de sobrenome;
- pista de nome seguida de palavras com maiúscula;
- palavra em maiúsculas logo depois de `[NOME]`.

Ele rodou nos 1.570 textos enviados e marcou 75, que li todos. **7 tinham nome de pessoa (0,45%)**: 3 com nome ou prenome inteiro e 4 com sobrenome que sobrou depois do prenome mascarado. É um limite inferior. `make varredura` agora também falha se um trecho de 8 palavras de algum pedido aparecer num arquivo versionado.

**4. Holdout de janeiro de 2026.** Hash registrado e commitado antes de rodar (commit `75ebd4c`, 10/11/2026 às 16:12, horário de Brasília; as chamadas ao Sonnet no holdout foram das 16:16 às 16:19); uma rodada só; US$ 1,26. O hash do commit mudou na reescrita do histórico (antes era outro), mas a data foi preservada.

| Regra congelada | Sem pessoa | Erro [IC 95%] | Meta | Reencaminhados certos |
|---|---|---|---|---|
| Sonnet a 1% | 86,6% | 0,69% [0,24–2,02] | cumprida | 12 de 12 |
| Sonnet a 2% | 94,6% | 2,33% [1,30–4,12] | não | 15 de 17 |
| ML a 1% | 67,2% | 1,49% [0,64–3,44] | não | 8 de 9 |
| ML a 2% | 73,6% | 2,17% [1,11–4,23] | não | 9 de 11 |

- **Sem abstenção:** o Sonnet acerta 95,4% e o ML 88,0%. Dos 23 reencaminhados, o Sonnet acerta 19 e o ML 14.
- **O ML clássico não segurou a meta de 1% em dados novos.** Isso está dito no README e na DECISAO.

**5. Base única para os números de "hoje".** A régua da decisão são os reencaminhados dos 10 órgãos (68 por 1.000). Os 8,52% valem para todos os órgãos federais e incluem os "sem competência"; isso está explicado numa linha no README §1. Os ~6 erros por 1.000 são só da parte automática (86%); o erro dos 14% da fila humana não foi medido.

**6. report.html.** Capturas com Playwright em 390 px (claro e escuro) e 1.280 px:
- não há rolagem lateral da página;
- não há erro de JavaScript;
- a dica da curva funciona.

No celular, os gráficos e as tabelas largas rolam dentro do próprio cartão.

**Gasto acumulado com a API: US$ 4,23** (teto de US$ 5).

**7. Nomes reais em casos de teste.** A busca no histórico do git achou partes de nomes tiradas de pedidos reais. Elas estavam em `tests/test_pii.py` e numa docstring de `src/triagem/pii.py`, desde o Marco 1.
- **Os nomes:** um prenome raro e quatro sobrenomes. Não os repito aqui de propósito.
- **A correção:** troquei todos por nomes inventados que não aparecem no bruto de 2025 nem no de 2026. Troquei também um nome inventado que, por acaso, coincide com o de um pedido de 2026.
- **Prevenção:** a `make varredura` agora lista as palavras com maiúscula que aparecem só de 1 a 3 vezes no bruto, para revisão.
- **Pendente:** **o histórico do git ainda tem esses nomes.** Reescrever o histórico ou não, antes do push, é decisão do Luigi.

**Verificação independente:** reprovado na 1ª rodada e aprovado na 2ª. A reprovação apontou:
- a revisão manual ainda descrita como "pendente";
- o DADOS.md §7 com os números antigos do detector;
- as premissas do custo citando o teste no holdout;
- o roteiro sem a explicação da base;
- quatro detalhes menores.

Tudo foi corrigido.

## Marco 5: entrega (concluído)

**O que foi feito**
- **README.md** reescrito para um avaliador de negócio, na ordem pedida: a dor, o que foi feito, a tabela das 4 abordagens, a curva, a decisão, o que deu errado, o que a IA errou feio, as limitações e o que testar com uma prefeitura.
- **DECISAO.md:** uma página para um diretor.
- **report.html** e **results/curva_cobertura_erro.png**, gerados por `make relatorio` (`src/triagem/relatorio.py`). Todos os números vêm dos JSON em `results/`.
  - Paleta validada para daltonismo.
  - Modo escuro.
  - Os gráficos rolam dentro do cartão no celular.
- **ROTEIRO_VIDEO.md:** 2 minutos, no máximo 148 palavras por minuto em cada trecho.

**Gasto total com a API:** US$ 2,83 (teto de US$ 5).

**Verificação independente:** reprovado na 1ª rodada e aprovado na 2ª. A reprovação apontou:
- **Origem de um dos nomes.** Eu tinha escrito que achei os 2 nomes ao ler os erros, mas um deles veio da revisão dirigida.
- **O 0,9% sem ressalva** no README e no indicador do relatório.
- **O empate do Haiku** não estava dito na DECISAO.
- **Faltava "+ erros do servidor"** na DECISAO e no roteiro.
- **Os 20 exemplos do prompt** não revistos não estavam citados.
- **O roteiro estava rápido demais** no fim.

Tudo foi corrigido.

## Marco 4: abstenção e decisão (concluído)

**O que foi feito** (`make abstencao`, `src/triagem/marco4.py`, resultado em `results/marco4.json`; só lê as previsões, não chama a API)
- **Cada estratégia dá uma nota de confiança por pedido.** Acima do limiar, o pedido é encaminhado sozinho; abaixo, vai para uma pessoa.
- **As 4 estratégias.** A ordem das notas é a natural: primeiro o sinal do próprio modelo, depois a concordância com o ML. Ela foi definida antes de calcular as curvas, mas o Marco 3 já tinha mostrado a acurácia por confiança no teste, e o Marco 2 a concordância ML + regras no teste.
  - **ML:** probabilidade do ML.
  - **ML + regras:** as regras concordam com o ML? Depois, a probabilidade do ML. Custo zero.
  - **Haiku e Sonnet:** a confiança declarada, depois se concorda com o ML, depois a probabilidade que o ML dá ao órgão escolhido.
- **Limiar só no dev.** Para cada meta de erro (1%, 2% e 5%), o limiar foi escolhido no dev como o de maior cobertura. O teste só mede.
- **Correção da estratificação.** O teste foi estratificado, então também calculei o erro reponderado pela distribuição real dos órgãos (`dor.json`).

**A meta combinada (2%) falhou no teste.**
- **Pelo dev,** o Sonnet cobriria 95,6% com 1,88% de erro.
- **No teste,** cobriu 96,6% com **3,1% de erro** [1,9–5,1].
- **Por quê:** o limiar caiu na borda da curva, aceitando até confiança "média" em desacordo com o ML. Com 500 pedidos no dev, essa borda não se sustenta.
- **O Haiku também passou da meta:** 2,6% no teste.
- `regra_pre_registrada` em `results/marco4.json` registra isso.

**Recomendação: o ponto de 1%, escolhido no dev.**
- **Aviso:** troquei a meta de 2% para 1% **depois** de ver o teste. Isso está escrito no `aviso` do JSON.
- **Estratégia:** Sonnet.
- **Regra:** encaminha sozinho se o Sonnet disser confiança "alta", ou "média" e o ML concordar com probabilidade ≥ 0,8035. O resto vai para uma pessoa.
- **Ressalva:** como a troca foi feita depois de ver o teste, o 0,9% abaixo não é uma estimativa limpa. O verificador também notou que o ponto de 1% está perto da borda: no dev, o ponto seguinte já sobe para 1,15%. Um jeito melhor seria escolher com margem (limite superior do intervalo no dev ≤ meta) e confirmar numa amostra nova, como outro mês de pedidos (cerca de US$ 1,40 de Sonnet).

| Ponto de 1% (teste) | Cobertura automática | Erro automático [IC 95%] | Fila humana | Erro reponderado |
|---|---|---|---|---|
| **Sonnet (recomendado)** | **85,4%** | **0,9% [0,4–2,4]** (4 de 427) | 73 de 500 | 0,9% |
| Haiku | 71,2% | 1,1% [0,4–2,9] | 144 | 1,4% |
| ML (sem API) | 63,8% | 0,9% [0,3–2,7] | 181 | 0,9% |
| ML + regras (sem API) | 55,0% | 0,0% [0,0–1,4] | 225 | 0,0% |

- **O que a abstenção tira da máquina.** Nos 73 pedidos da fila humana, a máquina acertaria só 72,6%. Ela realmente separa os difíceis.
- **Reencaminhados.** Dos 21 reencaminhados que ficaram com a máquina, ela acerta 20.
- **Sem abstenção, o Sonnet não serve sozinho.** Reponderado pela distribuição real, o erro sobe de 4,8% para **6,3%** (`sem_abstencao_teste`): o INSS, que tem peso maior na base real, é o órgão em que o Sonnet mais erra.

**Custo do erro, por 1.000 pedidos** (premissas em `custo_do_erro` no JSON)

Pedidos dos 10 órgãos, com cobertura e erro reponderados pela distribuição real. Entre colchetes, a faixa pelo intervalo de 95% do erro.

| | Hoje (o cidadão escolhe) | Sonnet a 1% | ML a 1% (sem API) |
|---|---|---|---|
| Encaminhados sem pessoa | 0 | 847 | 636 |
| Fila humana | — | 153 | 364 |
| Reencaminhados por erro de destino | 68 | 8 [3–20] + erros da fila humana | 6 [2–17] + erros da fila humana |
| Dias de atraso somados (4 por reencaminhamento) | 274 | 31 [12–81] + fila humana | 23 [8–69] + fila humana |
| "Não é de competência" | 20 | não tratado | não tratado |
| Custo de API | 0 | US$ 2,83 | 0 |

**Premissas e limites**
- **O erro da triagem humana não foi medido.** A revisão manual dos 50 casos vai dar uma primeira estimativa.
- **Os 4 dias** são a diferença entre as medianas de prazo dos reencaminhados (17) e dos que chegaram certo (13), não a mediana do atraso de cada pedido.
- **A comparação com "hoje" usa só os reencaminhados** dos 10 órgãos (6,84%). Os "sem competência" (2,00%) não são reencaminhados e ficam de fora, porque este sistema só escolhe entre os 10 órgãos.
- **O custo de API é irrelevante** perto do tempo de um servidor. A escolha entre Sonnet e ML é de cobertura, não de dinheiro.

**Decisões**
- **A recomendação é a do Sonnet a 1%.** Se mandar texto para uma API externa não for aceitável, a alternativa é o ML a 1%: cobre menos (64%), com o mesmo erro e sem custo.

**Verificação independente:** reprovado na 1ª rodada e aprovado na 2ª. A reprovação apontou:
- o atraso de "hoje" inflado, por incluir os "sem competência" (341 dias viraram 274);
- falta da faixa de incerteza e da reponderação na tabela por 1.000;
- a frase "ordem fixada antes de olhar os dados", que exagerava;
- números digitados à mão no aviso;
- o limiar arredondado.
Tudo foi corrigido, com testes novos.

## Marco 3: Claude Haiku e Sonnet (concluído)

**O que foi feito**
- **Mesmo prompt para os dois modelos.**
  - Descrição curta de cada órgão, mais 2 exemplos por órgão tirados da amostra de treino.
  - Saída em JSON com o órgão, um trecho literal do pedido, uma justificativa curta e a confiança (alta, média ou baixa).
- **Cache local** (`cache/*.jsonl`, chave = hash da requisição + id). Rodar de novo não gasta.
- **Cache de prompt da Anthropic** no prefixo de 4.945 tokens.
- **Ordem:** contagem de tokens primeiro, depois dev, depois teste. O prompt não mudou depois do dev, e o hash do prompt está no registro de avaliações do teste.
- Rodar de novo: `make llm-dev` e `make llm-teste`.

**Custo**
- **Estimativa antes de rodar: US$ 3,08.** O count_tokens da API mediu o prefixo e uma amostra de 50 pedidos; a saída foi assumida em 150 tokens.
- **Gasto real: US$ 2,83.**
  - Haiku: US$ 0,15 nos 1.000 pedidos.
  - Sonnet: US$ 2,69.
- Preços conferidos em 09/11/2026 na página oficial, em US$ por milhão de tokens:
  - Haiku 5.5: 0,10 de entrada e 0,50 de saída.
  - Sonnet 5.5: 2,00 de entrada e 10,00 de saída.
  - Leitura do cache: 0,01 (Haiku) e 0,10 (Sonnet).

**Resultados no teste** (500 pedidos; entre colchetes, intervalo de 95%)

| Abordagem | Acurácia | F1 macro | Cita a sigla (146) | Não cita (354) | Reencaminhados (34) | Custo por 1.000 | Tempo por pedido |
|---|---|---|---|---|---|---|---|
| Regras | 74,0% [70,0–77,7] | 0,731 | 97,3% | 64,4% | 18 | ~0 | < 1 ms |
| ML clássico | 89,4% [86,4–91,8] | 0,888 | 95,9% | 86,7% | 24 | ~0 | < 1 ms |
| Haiku 5.5 | 90,8% [88,0–93,0] | 0,903 | 99,3% | 87,3% | 30 | US$ 0,15 | 1,3 s (mediana) |
| **Sonnet 5.5** | **95,2% [93,0–96,8]** | **0,944** | 98,6% | **93,8%** | **31** | US$ 2,83 | 2,0 s (mediana) |

No dev, a ordem foi a mesma: Sonnet 95,0%, Haiku 92,0%, ML 89,6% e regras 78,6%.

**Comparação pareada no teste** (mesmos 500 pedidos, bootstrap; fonte: `comparacoes_pareadas` em `results/marco3.json`)
- **Sonnet contra ML: +5,8 pontos [3,0 a 8,4].** O Sonnet acerta 38 pedidos que o ML erra, e o ML acerta 9 que o Sonnet erra.
- **Haiku contra ML: +1,4 ponto [−1,4 a 4,2].** É empate estatístico.
- **Sonnet contra Haiku: +4,4 pontos [2,6 a 6,4].**

**Onde o ML e as regras empatam ou ganham** (teste)
- **Nos pedidos que citam a sigla, todo mundo acerta.** As regras acertam 142 de 146; o Haiku, 145; e o Sonnet, 144. É empate.
- **O ML ganha do Haiku no F1 de dois órgãos:**
  - MGI: 0,795 contra 0,731. O Haiku manda pedidos demais para o MGI: só 64% dos que ele manda para lá são do MGI.
  - MF: 0,884 contra 0,860.
- **O ML e as regras não custam nada e respondem em menos de 1 ms.** Os LLMs levam 1,3 a 2 s por pedido.

**A confiança declarada pelo modelo separa bem os erros.** Este é o insumo do Marco 4.

| Confiança | Sonnet (teste) | Haiku (teste) |
|---|---|---|
| Alta | 385 pedidos, 99,2% de acerto | 393 pedidos, 97,2% |
| Média | 104 pedidos, 85,6% | 91 pedidos, 72,5% |
| Baixa | 11 pedidos, 45,5% | 16 pedidos, 37,5% |

**Explicabilidade**
- O trecho citado está, de fato, no pedido em 97% das respostas (verificado por código).
- Nenhuma resposta veio em JSON inválido (0 de 2.000).

**20 erros lado a lado** (sorteio entre os 24 erros do Sonnet no teste; classificação manual em `results/erros_classificacao_manual.json`, sem texto de pedido)
- **8: sem pista no texto.** Exemplos: "contracheque", "consultar débitos", o número de um pregão, a venda de um imóvel sem dizer de quem é. O órgão certo depende de para onde o cidadão mandou. Nenhum classificador de texto acerta com segurança, e a máquina deveria abster-se.
- **6: vinculação institucional.**
  - O Arquivo Nacional pertence ao MGI, mas o modelo mandou 3 pedidos de naturalização antiga para a PF.
  - As cepas da vacina da gripe são definidas em norma da ANVISA.
  - O código orçamentário 26xxx é do MEC.
  - O prompt não trazia essas vinculações. Elas seriam fáceis de acrescentar, mas isso não foi feito, porque seria ajustar depois de ver o teste.
- **5: mais de um órgão ou rótulo discutível.** Dois deles foram reencaminhados pela própria administração. A resposta do modelo é defensável.
  - "CPF bloqueado com dinheiro retido" aponta para a Receita e para o BACEN.
  - Professores da educação básica são estaduais ou municipais, então MEC é defensável.
  - Em 10/11/2026, o Luigi ficou com o verificador nos 3 casos contestados, e a contagem passou de 7/6/4/2/1 para 8/6/5/0/1.
- **1: fato inventado.** O modelo disse que um grupo de destinação de bens da União tratava de armas apreendidas e escolheu PF.
- **O que a IA errou feio.** Há 3 erros com confiança **alta**:
  - naturalização para PF (era Arquivo Nacional/MGI);
  - resolução do CMN para BACEN (foi reencaminhada ao MF);
  - cepas da vacina para MS (era ANVISA).
- Nos 20 casos, o Haiku acerta 2, o ML 8 e as regras 7. Dos 24 erros do Sonnet no teste, o ML acerta 9 e erra 15. Combinar os dois ajuda, mas não resolve tudo.

**Dados pessoais que escaparam e foram enviados à API**
- Achei **2 pedidos do teste com nome de pessoa sem máscara**:
  - um prenome estrangeiro fora da lista do IBGE, na leitura dos erros;
  - um nome depois de "Proprietário:", na revisão dirigida abaixo (os modelos acertaram esse pedido).
- **Revisão dirigida.** Revisei à mão os 29 textos de dev e teste com tema de naturalização, genealogia ou certidão. Os 2 casos estavam entre eles. Os ids e o critério estão em `results/pii_revisao_dirigida.json`.
- **O que não foi revisto.** Os outros 971 textos e os 20 exemplos do prompt não foram lidos à mão. A taxa de escape fora desse recorte é **desconhecida**. A varredura automática do Marco 1 não pegou esses 2 casos.
- **Repositório.** Os textos não vão para o repositório; ficam só no cache local, fora do git. Por isso não é a parada 3, mas o Luigi precisa saber.
- **Máscara não corrigida.** Corrigir agora mudaria o teste congelado. Está documentado em DADOS.md §7.

**Decisões**
- O prompt não foi ajustado depois do dev nem depois do teste. As melhorias óbvias (Arquivo Nacional e SPU no MGI, cepas na ANVISA) ficam registradas como próximos passos.
- **Correção da verificação.** `marco3 avaliar` sem `--teste` agora preserva o resultado de teste já registrado, em vez de apagá-lo. O `hash_prompt` cobre só o texto do prompt; `hash_requisicao` cobre também o schema, o effort e o max_tokens.
- O Sonnet 5.5 não aceita `thinking` desligado. Ficou `between_tools`, que na prática não gera raciocínio numa chamada sem ferramentas: a saída média foi de 137 tokens.
- O teste dos LLMs também só é avaliado com `--teste`, registrado com o hash do prompt. Foram 2 avaliações, porque acrescentei a comparação pareada depois; as acurácias foram idênticas.

**Verificação independente:** reprovado na 1ª rodada e aprovado na 2ª. A reprovação apontou um bug (`avaliar` sem `--teste` apagava o resultado de teste), um número sem fonte (os 29 textos revistos), a taxa desconhecida de escape da máscara, pontos em que o ML empata ou ganha que não estavam escritos, e 3 frases imprecisas. Tudo foi corrigido.

## Marco 2: baselines, regras e ML clássico (concluído)

**O que foi feito**
- **Só nome/sigla:** prevê o órgão cujo nome ou sigla o pedido cita. É a régua do ganho "grátis" da sigla.
- **Regras:** nome/sigla de cada órgão (escrito à mão) mais palavras-chave tiradas da amostra de treino (log-odds por documento). As palavras ficam legíveis em `results/regras_palavras_chave.json`. No dev foram escolhidas 800 palavras por órgão, e o nome/sigla vale 20 palavras.
- **ML:** TF-IDF (palavras e pares de palavras) + regressão logística, treinado nos 16.778 pedidos de jan a ago. O C = 30 foi escolhido no dev. Há uma versão de referência treinada só com 2.000 pedidos (C = 100).
- **Todas as escolhas usaram só o dev.** O teste agora só é calculado com `--teste`, e cada cálculo fica registrado em `results/registro_avaliacoes_teste.jsonl`. Antes desse registro existir, o script calculou o teste em 4 execuções:
  1. 1ª grade;
  2. grade ampliada, porque a escolha no dev caiu no limite (k = 200, peso 10);
  3. correção da medição de tempo;
  4. ordenação da explicação das regras.

  O verificador rodou mais 2. Nenhuma escolha mudou por causa do teste, e o ML e o "só sigla" deram o mesmo resultado em todas.
- Rodar de novo: `make baselines`. As previsões estão em `results/predicoes/` (ids, rótulos e no máximo 8 termos por explicação, sem texto do pedido).

**Resultados no teste** (500 pedidos; entre colchetes, intervalo de 95%)

| Abordagem | Acurácia | F1 macro | Cita a sigla literal (146) | Não cita (354) | Reencaminhados (34) | Tempo por 1.000 |
|---|---|---|---|---|---|---|
| Só nome/sigla | 38,8% [34,6–43,1] | 0,557 | 99,3% | 13,8% | 7 de 34 | 0,2 s |
| Regras | 74,0% [70,0–77,7] | 0,731 | 97,3% | 64,4% | 18 de 34 | 0,4 s |
| **ML (16.778 de treino)** | **89,4% [86,4–91,8]** | **0,888** | 95,9% | **86,7%** | 24 de 34 | 0,05 s |
| ML (2.000 de treino) | 80,2% [76,5–83,5] | 0,795 | 89,7% | 76,3% | 22 de 34 | 0,04 s |

O custo das quatro é só de computação local: menos de 1 segundo por 1.000 pedidos.

**Quanto as regras ganham só por causa da sigla** (pergunta do Luigi)
- **Dois jeitos de definir "cita".**
  - **Sigla literal** (ANVISA, MEC…): 146 pedidos.
  - **Nome ou sigla** (inclui "Banco Central", "Receita Federal", "Ministério da Saúde"): 195 pedidos. São 49 a mais.
- **O que os números mostram (sigla literal).** Pedidos que citam a sigla são mais fáceis para qualquer abordagem. As regras acertam 97,3% contra 64,4%, uma diferença de 33 pontos. O ML acerta 95,9% contra 86,7%, uma diferença de 9 pontos.
- **Diferença entre as duas diferenças** (o quanto as regras dependem da sigla além disso, dentro do subgrupo "cita"):
  - sigla literal: **23,7 pontos** (intervalo de 95% por bootstrap: 17,4 a 29,8);
  - nome ou sigla: **26,9 pontos** (20,7 a 33,1).
- **Medida direta.** Com as mesmas regras e peso zero para o nome/sigla, o acerto no subgrupo "cita" cai de 97,3% para 63,0% (−34 pontos). Na acurácia geral cai de 74,0% para 60,4% (−13,6 pontos). Fonte: `analise_peso_sigla_zero` em `results/marco2.json`.
- **Conclusão.**
  - Sem sigla, o ML ganha das regras por 22 pontos (86,7% contra 64,4%).
  - Com sigla, as regras ganham por 1,4 ponto (2 pedidos), dentro da margem de erro.
  - Quase toda a vantagem das regras vem da sigla.

**Outros achados**
- **ML e regras concordam em 376 de 500 pedidos no teste e, quando concordam, acertam 95,2%** (no dev: 400 de 500, com 94,5% de acerto). Para o Marco 4, esse critério será calibrado no dev, não no teste.
- O ML acerta 89 pedidos que as regras erram. As regras acertam 12 que o ML erra. Os dois erram 41. Fonte: `analises` em `results/marco2.json`.
- **Órgãos mais difíceis.** Para o ML, o pior F1 é o da MGI (0,80). A MGI recebe 23% dos seus pedidos por reencaminhamento (`dor.json`). Para as regras, os piores são MGI (0,53), MEC (0,64) e ANEEL (0,65).
- **Confusões mais comuns do ML:** PF→MGI, MEC→MS, MS→PETROBRAS e INSS→MGI, com 3 ou 4 casos cada.
- **Reencaminhados** (os casos que já confundiram o cidadão): são só 34, e o intervalo fica largo. O ML acerta 24 (54–83%) e as regras 18 (37–69%).
- **Explicabilidade.**
  - ML: os 5 termos que mais pesaram ("bpc", "renda", "carteira trabalho" → INSS). É útil.
  - Regras: as palavras encontradas, mas com 800 por órgão entram termos genéricos ("quero", "pode"). Agora mostram só as 8 mais fortes.
  - Nenhum dos dois cita um trecho literal do pedido.

**Decisões**
- A grade das regras foi ampliada porque a escolha **no dev** caiu no limite. A escolha final (k = 800, peso 20) ficou dentro da grade. A grade do ML com 2.000 de treino também foi ampliada, e C = 100 continua sendo o escolhido.
- **O tempo do ML mede só a classificação.** A explicação leva cerca de 0,3 s por 1.000 pedidos.
- **A varredura de dados pessoais também procura termos em minúsculas** em `results/`. Os 12 encontrados foram revisados e são lugares, siglas e instituições ("paulo" de São Paulo, "nilo" de Nilo Peçanha, CID, Marinha).
- **A revisão manual dos 50 casos está pendente** (Luigi). `make revisao` calcula a concordância quando o CSV estiver preenchido.

**Verificação independente:** aprovado na 1ª rodada, com 3 correções de documentação, que foram feitas: o teste calculado mais de uma vez, a definição do subgrupo e o intervalo do ganho da sigla.

## Marco 1: dados, dor, conjuntos (aprovado pelo Luigi em 09/11/2026)

**O que foi feito**
- Download e inspeção dos arquivos LAI 2025 da CGU. A base completa não tem o texto do pedido. O texto está na base "Filtrado", que cobre 56% dos pedidos.
- Medição da dor na base completa, com 130.407 pedidos federais concluídos.
- Recorte dos 10 órgãos com mais pedidos com texto: MS, PETROBRAS, ANVISA, BACEN, INSS, MF, MGI, MEC, ANEEL, PF.
- Separação temporal dos conjuntos: treino de jan a ago (16.778 pedidos), dev de set a out (500) e teste de nov a dez (500). Dev e teste são estratificados por órgão, com no máximo 5 pedidos por solicitante.
- Máscara de dados pessoais: regex, NER do spaCy filtrado por prenomes do IBGE e por palavras comuns do corpus, mais regras para pistas no texto e pronomes de tratamento.
- 50 casos separados para a revisão manual às cegas.

**Números principais**

| Indicador | Valor |
|---|---|
| Pedidos que chegaram ao órgão errado | 8,52% (11.111 de 130.407) |
| Reencaminhados | 6,58% |
| "Não é de competência" | 2,23% |
| Atraso de um reencaminhado (mediana) | +4 dias (17 contra 13) |
| Pedidos de teste que citam a sigla do próprio órgão | 146 de 500 (regra em `metricas.cita_sigla`; o verificador contou 148 com outra regra) |
| Excesso de máscara (auditoria manual) | 7 de 80 trechos não eram nomes |
| Hash do teste | `d38c70d7…1956` |

**Decisões**
- **Separação temporal em vez de sorteio.** 140 solicitantes fazem pedidos em série e somam 15,6% da base.
- **"Não é de competência" fica fora** do treino e do teste, porque o rótulo está errado. Os reencaminhados ficam e usam o órgão final como rótulo.
- **Texto dos pedidos fora do git.** `make all` refaz os conjuntos a partir do arquivo da CGU.
- **Varredura de dados pessoais antes de cada commit** (`make varredura`). Ela foi criada depois que a verificação achou dados reais copiados para os testes.

**Verificação independente:** reprovado 2 vezes e aprovado na 3ª. A ressalva da 3ª rodada (nome depois de "Sra.") foi corrigida e verificada à parte antes do commit. A ressalva dessa verificação (o nome do hospital era apagado junto, depois de "Dr.") também foi corrigida antes do commit, com teste de regressão.
