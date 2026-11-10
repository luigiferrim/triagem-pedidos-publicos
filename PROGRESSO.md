# Progresso

Atualizado a cada marco. Os números saem dos arquivos em `results/`.

## Marco atual: 4 (abstenção e decisão)

Em andamento.

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
- **7: sem pista no texto.** Exemplos: "contracheque", "consultar débitos", o número de um pregão. O órgão certo depende de para onde o cidadão mandou. Nenhum classificador de texto acerta com segurança, e a máquina deveria abster-se.
- **6: vinculação institucional.**
  - O Arquivo Nacional pertence ao MGI, mas o modelo mandou 3 pedidos de naturalização antiga para a PF.
  - As cepas da vacina da gripe são definidas em norma da ANVISA.
  - O código orçamentário 26xxx é do MEC.
  - O prompt não trazia essas vinculações. Elas seriam fáceis de acrescentar, mas isso não foi feito, porque seria ajustar depois de ver o teste.
- **4: mais de um órgão ou rótulo discutível.** Dois deles foram reencaminhados pela própria administração. A resposta do modelo é defensável.
- **2: pista ignorada.** "CPF bloqueado com dinheiro retido" foi para a Receita; o rótulo é BACEN, e "dinheiro retido" aponta para ele. O Haiku e o ML acertaram esse. Este caso e o dos professores afastados também caberiam em "rótulo discutível" (observação do verificador).
- **1: fato inventado.** O modelo disse que um grupo de destinação de bens da União tratava de armas apreendidas e escolheu PF.
- **O que a IA errou feio.** Há 3 erros com confiança **alta**:
  - naturalização para PF (era Arquivo Nacional/MGI);
  - resolução do CMN para BACEN (foi reencaminhada ao MF);
  - cepas da vacina para MS (era ANVISA).
- Nos 20 casos, o Haiku acerta 2, o ML 8 e as regras 7. Dos 24 erros do Sonnet no teste, o ML acerta 9 e erra 15. Combinar os dois ajuda, mas não resolve tudo.

**Dados pessoais que escaparam e foram enviados à API**
- Na leitura dos erros, achei **2 pedidos do teste com nome de pessoa sem máscara**:
  - um prenome estrangeiro fora da lista do IBGE;
  - um nome depois de "Proprietário:".
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
