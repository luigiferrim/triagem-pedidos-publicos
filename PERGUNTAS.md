# Perguntas que um avaliador faria

Respostas curtas, com a fonte de cada número. Os arquivos citados estão em `results/`, e as seções, no [README](README.md).

## O problema e a decisão

**1. Qual é o problema, em números?**
Em 2025, 8,52% dos pedidos de acesso à informação federais chegaram ao órgão errado. Nos 10 órgãos estudados, 68 de cada 1.000 foram reencaminhados, com 4 dias a mais de espera e prazo sempre prorrogado. Fonte: `dor.json`, README §1.

**2. Numa prefeitura é diferente?**
É pior. Na Prefeitura de São Paulo, 123 de cada 1.000 pedidos de 2024 aos 10 órgãos que mais recebem pedidos foram transferidos para outro órgão. A taxa ficou estável de 2021 a 2024, entre 12,2% e 13,5%. Fonte: `marco9_dor.json`, README §1 e §4d.

**3. Qual é a recomendação?**
O Claude Sonnet encaminha sozinho quando declara confiança alta, ou média com o modelo estatístico concordando e seguro (probabilidade ≥ 0,8035). O resto vai para uma pessoa. Fonte: README §5.

**4. Quanto isso automatiza e quanto erra?**
De março a outubro de 2026, em 1.200 pedidos novos e com a regra congelada antes:
- 85,5% dos pedidos saíram sem pessoa;
- a parte automática errou 1,85% (IC 95% 1,2–2,9%), cerca de 16 erros por 1.000, contra 68 reencaminhados hoje.

Fonte: `manchete.json`, README §4c.

**5. A meta de 1% de erro foi atingida?**
Não. Janeiro de 2026 ficou em 0,69%, fevereiro em 1,87% e março a outubro em 1,85%. A regra recalibrada com janeiro e fevereiro errou 1,78%. O honesto é prometer um erro entre 1% e 2%. Fonte: `manchete.json`, `marco8_resultado.json`.

**6. Por que não deixar a IA decidir tudo?**
Sem a regra de segurança, o Sonnet acertou 94,7% de março a outubro: cerca de 53 erros por 1.000. Com a regra, ficam cerca de 16 na parte automática, e 145 pedidos vão para uma pessoa. Nos pedidos que sobram para uma pessoa, a máquina acerta bem menos, e é aí que o servidor faz falta. Fonte: `marco8_resultado.json`, `manchete.json`.

**7. Por que o Sonnet, e não o modelo clássico ou o Haiku?**
No teste de 2025, os acertos foram:
- Sonnet: 95,2%;
- Haiku: 90,8%;
- modelo clássico: 89,4%;
- regras: 74,0%.

O Sonnet ganha do clássico por 5,8 pontos [3,0 a 8,4]. O Haiku empata com o clássico, custa mais e é mais lento. Fonte: `marco3.json`, README §3.

**8. Quanto custa?**
Cerca de US$ 2,83 por 1.000 pedidos, menos de 1 centavo por pedido. Em todo o projeto, as chamadas à API custaram cerca de US$ 13,8:
- **fase 1:** US$ 4,23, sendo US$ 2,83 de dev e teste (`marco3.json`), US$ 1,26 do holdout de janeiro e US$ 0,14 da revisão manual (README "Como reproduzir");
- **fase 2:** US$ 9,59 (`gasto_fase_2_usd` em `marco9_comparacao.json`).

Custo por 1.000: `marco8_resultado.json`.

## Método e confiança nos números

**9. Como sei que os números não foram escolhidos a dedo?**
- Cada teste em dados novos teve o hash da amostra, o prompt e os limiares commitados **antes** da primeira chamada: janeiro (`75ebd4c`), fevereiro (`marco7_congelado.json`), março a outubro (`e59c188`) e São Paulo (`d305a99`).
- Os testes automáticos conferem que nada mudou depois.
- O teste de 2025 só é calculado com registro, em `registro_avaliacoes_teste.jsonl`.

Fonte: README, registros no fim.

**10. O que é o rótulo, e ele é confiável?**
É o órgão que respondeu o pedido, o final, depois de um reencaminhamento. Os pedidos com "não é de nossa competência" ficam fora, porque o órgão certo não aparece na base. Em alguns casos, o rótulo é discutível: o lote do INSS, ou o Bilhete Único Estudante em SP, que a SPTrans emite mas a SME respondeu. Fonte: DADOS.md §5 e §9.

**11. Por que separar treino e teste por data, e não por sorteio?**
Porque 140 solicitantes fizeram 10 pedidos ou mais cada, somando 15,6% da base, e muitos seguem um modelo fixo. Num sorteio, o mesmo modelo cairia no treino e no teste, e o resultado pareceria melhor do que é. Fonte: `preparacao.json`, DADOS.md §6.

**12. O que deu errado?**
- A meta combinada, de 2%, falhou no teste e no holdout.
- O ponto de 1% foi escolhido depois de ver o teste; por isso foi congelado e medido de novo.
- Nomes de pessoa escaparam da máscara.
- A matrícula SIAPE passou em 4 textos.
- Em SP, a limpeza deixou passar textos repetidos que diferiam só por um acento; a verificação achou isso antes do teste.

Fonte: README §6, PROGRESSO.md.

**13. Que erros a IA comete?**
Dos 20 erros lidos no teste de 2025:
- 8 não tinham pista no texto;
- 6 eram de vinculação (a IA não sabia que o Arquivo Nacional é do MGI, por exemplo);
- 5 tinham rótulo discutível;
- 1 trazia um fato inventado.

Três vieram com confiança alta, e a regra de segurança não pega esses. Fonte: `erros_classificacao_manual.json`, README §7.

**14. Por que os alertas dispararam de junho a agosto?**
Por causa de um lote de 158 pedidos quase iguais, de um só solicitante, ao INSS, sobre ex-servidores identificados pela matrícula SIAPE. A IA mandou ao MGI, que gere o SIAPE: é uma resposta defensável. Sem o lote, nenhum alerta dispara, e o erro fica em 1,37%. Fonte: `marco8_resultado.json`, README §4c.

**15. Dar à IA acesso à estrutura oficial do governo não ajudou?**
Não. A versão com consulta ao SIORG empatou com a recomendada em fevereiro: 93,6% contra 93,0% de acerto. Ela usou a ferramenta em 12 de 500 pedidos e custa mais. Fonte: `marco7_fev.json`, README §4b.

**16. E os dados pessoais?**
- **Máscara:** o texto passa por uma máscara antes de sair do computador.
- **O que escapou:** num detector offline com revisão à mão, 7 dos 1.570 textos enviados e auditados até janeiro de 2026 tinham nome de pessoa (0,45%, limite inferior). Depois, 4 textos do monitoramento foram com a matrícula SIAPE visível; a máscara foi corrigida para conjuntos novos.
- **Repositório:** o texto dos pedidos não está nele, salvo 29 exemplos revisados à mão. Uma varredura confere cada commit.

Fonte: `pii_detector_offline.json`, DADOS.md §7.

## Prefeitura e operação

**17. Funciona numa prefeitura?**
Em São Paulo, com pedidos de 2025 e o mesmo método, a IA acertou 88,6% sem abstenção, contra 95,2% no teste federal equivalente.
- **Regra principal, com limiar escolhido no dev de SP:** encaminhou 67,7% sem pessoa, com 2,37% de erro, ou 16 erros por 1.000, contra 123 trocas de órgão hoje.
- **Regra federal, registrada antes como comparação:** cobriu 78,2%, com os mesmos erros (2,05%).
- **No federal,** a mesma regra errou 0,94% no teste equivalente.

Funciona, com menos folga que no federal. Fonte: `marco9_comparacao.json`, README §4d.

**18. Por que o limiar ajustado para SP não ajudou?**
Porque foi escolhido num dev pequeno, com 2 erros em 220 pedidos encaminhados. O próprio intervalo do dev ia até 3,25%, e no teste ele errou 2,37%. A regra federal, sem ajuste, teve os mesmos 8 erros e cobriu mais. Com 300 pedidos, escolher um limiar fino é quase sorteio. Numa prefeitura real, o limiar tem de vir de um piloto em sombra com milhares de pedidos. Nos 10 órgãos de SP, são cerca de 360 pedidos de acesso à informação por mês. Por isso, ou o piloto inclui as demandas de ouvidoria e protocolo, ou dura mais de um mês. Fonte: `marco9_dev.json`, `marco9_teste.json`, `marco9_teste_analise.json`.

**19. Se ligássemos isso no 1Doc amanhã, quem usa, em que tela, o que muda?**
- **Quem usa:** o servidor da triagem, que recebe as demandas sem setor definido (ouvidoria, protocolo geral, WhatsApp).
- **Em que tela:** na chegada da demanda, ao lado do texto, aparecem a secretaria sugerida, o trecho que motivou a sugestão e uma linha de motivo.
- **O que muda:** os pedidos claros seguem direto, e os incertos ficam na fila dele.
- **No primeiro mês, nada segue sozinho:** é o piloto em sombra.

Esta é uma proposta feita com informação pública, não uma descrição de como o 1Doc funciona por dentro. Fonte: aba "Numa prefeitura" da Mesa.

**20. Em que prefeitura você usaria só o modelo estatístico local, em vez do Sonnet?**
Numa prefeitura que não pode mandar o texto do cidadão para fora, por lei, contrato ou política, e que tenha muitos pedidos antigos já encaminhados para treinar o modelo.
- **No federal,** com 16.778 pedidos de treino, o modelo local acertou 89%. Na regra de 1%, cobriu 67%, com 1,5% de erro.
- **Em SP,** com 3.424, acertou 78% e cobriu só 37%, com 1,6% de erro.

Com pouca história, ele deixa quase tudo para o servidor. Fonte: `holdout_2026_resultado.json`, `marco9_teste.json`.

**21. Quem fica com os pedidos que a máquina não decide, e quanto erra essa pessoa?**
Cerca de 145 de cada 1.000 vão para um servidor. O erro dele não foi medido: a revisão manual de 50 casos foi feita por um leigo e não mede um servidor. Medir esse erro é uma das quatro medidas do piloto em sombra. Fonte: `manchete.json`, README §8.

**22. O que é o piloto em sombra, e o que decide se a mesa pode encaminhar sozinha?**
Durante um mês, ou mais se o volume for pequeno, a IA sugere e o servidor decide, sem mudar o fluxo. Ao fim, comparam-se:
- o erro de hoje;
- o erro do servidor;
- o erro e a cobertura da IA;
- quantos pedidos não são da prefeitura.

A mesa só passa a encaminhar sozinha num ponto de corte escolhido com folga nesses dados. Fonte: DECISAO.md, "Próximo passo".

**23. Como a operação percebe que a IA piorou?**
Um alerta mensal compara o erro dos dois últimos meses com a meta. Antes de reagir a um alerta, é preciso checar se os erros se concentram num só solicitante, como no lote do INSS, e agrupar pedidos quase idênticos para o servidor decidir uma vez. Fonte: README §4c.

## Trabalho com IA

**24. Como você trabalhou com o Claude Code?**
- **Divisão:** eu defini o problema, as regras de avaliação e os pontos de parada, como antes de gastar com a API ou se aparecesse dado pessoal. O Claude Code escreveu o código, rodou os experimentos e redigiu os rascunhos.
- **Verificação:** em vários marcos, um verificador independente, outra instância que não escreveu o código, conferiu o trabalho. Ele reprovou várias rodadas, incluindo a 1ª do Marco 9, que tinha um defeito na limpeza dos dados.
- **Decisões:** eu revisei dados à mão e tomei as decisões.

Fonte: README "Como trabalhei com IA", PROGRESSO.md.

**25. Conte uma decisão em que você discordou do Claude Code.**
- **O caso:** na Bridge, ao testar uma API mockada, o Claude Code criou um teste com um valor nulo que o sistema real nunca deixaria entrar, porque ele é validado antes.
- **O que fiz:** barrei o teste. Ele geraria um falso negativo e confundiria o time.
- **O que mudou:** desde então, reproduzo à mão todo teste que a IA reprova antes de levá-lo aos devs.

Fonte: experiência do autor, fora deste repositório.
