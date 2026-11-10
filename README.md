# Triagem de pedidos públicos: regras, ML clássico e IA

Dá para encaminhar pedidos de cidadãos ao órgão certo de forma automática e segura? Quanto da fila dá para automatizar sem aumentar o erro? Este projeto compara quatro abordagens no mesmo teste e decide onde a IA entra e onde uma pessoa decide.

Para um diretor: [DECISAO.md](DECISAO.md) (uma página). Gráficos: abra `report.html` no navegador. Diário do trabalho: [PROGRESSO.md](PROGRESSO.md).

## 1. A dor

Em 2025, **8,52% dos pedidos de acesso à informação federais chegaram ao órgão errado**: 11.111 de 130.407.
- 6,58% foram reencaminhados a outro órgão.
- 2,23% receberam "não é de nossa competência".

O reencaminhado leva **4 dias a mais**: a mediana do prazo foi de 17 dias, contra 13 dos que chegaram certo. Todos os reencaminhados tiveram o prazo prorrogado.

Fonte: base pública do Fala.BR (CGU). Os números saem de `make dor` (`results/dor.json`).

**Régua usada na decisão (§5).** O sistema só escolhe entre os 10 órgãos estudados. Por isso, a comparação com hoje usa os reencaminhados desses 10 órgãos: 6,84%, ou 68 por 1.000. Os 8,52% acima valem para todos os órgãos federais e incluem os "sem competência".

## 2. O que foi feito

- **Dados.** 17.778 pedidos dos 10 órgãos federais com mais pedidos com texto público: MS, PETROBRAS, ANVISA, BACEN, INSS, MF, MGI, MEC, ANEEL e PF.
- **Rótulo.** O órgão que respondeu. Nos reencaminhados, é o órgão final.
- **Separação por data.**
  - Treino: janeiro a agosto (16.778 pedidos).
  - Ajuste (dev): setembro e outubro (500).
  - **Teste: novembro e dezembro (500)**, separado antes de escrever qualquer classificador.
- **Dados pessoais mascarados antes de qualquer uso.** Nome, CPF, e-mail, telefone, endereço e documentos. Como funciona e quanto escapa: [DADOS.md](DADOS.md) §7.
- **Quatro abordagens:**
  1. **Regras:** nome e sigla de cada órgão, mais palavras-chave tiradas do treino.
  2. **ML clássico:** TF-IDF e regressão logística.
  3. **Claude Haiku 5.5:** poucos exemplos no prompt; responde em JSON com o órgão, um trecho do pedido e uma justificativa curta.
  4. **Claude Sonnet 5.5:** o mesmo prompt.
- **Confirmação em dados novos.** A regra escolhida foi congelada e medida uma vez em 500 pedidos de janeiro de 2026 (holdout), com o hash registrado antes.
- **Escolhas só no dev.** O teste só mede. Cada cálculo do teste fica registrado em `results/registro_avaliacoes_teste.jsonl`.
- **Escopo: só triagem.** Nada de resposta automática ao cidadão.

## 3. As quatro abordagens no teste

500 pedidos. Entre colchetes, o intervalo de 95%.

| Abordagem | Acurácia | F1 macro | Pedidos que citam a sigla (146) | Que não citam (354) | Reencaminhados (34) | Custo por 1.000 | Tempo | Explicação |
|---|---|---|---|---|---|---|---|---|
| Regras | 74,0% [70,0–77,7] | 0,731 | 97,3% | 64,4% | 18 | ≈ 0 | < 1 ms | palavras encontradas |
| ML clássico | 89,4% [86,4–91,8] | 0,888 | 95,9% | 86,7% | 24 | ≈ 0 | < 1 ms | termos de maior peso |
| Haiku 5.5 | 90,8% [88,0–93,0] | 0,903 | 99,3% | 87,3% | 30 | US$ 0,15 | 1,3 s | trecho do pedido + frase |
| **Sonnet 5.5** | **95,2% [93,0–96,8]** | **0,944** | 98,6% | **93,8%** | **31** | US$ 2,83 | 2,0 s | trecho do pedido + frase |

Tempos dos LLMs: mediana por pedido. O custo usa tokens reais e o preço oficial.

**O que a tabela diz:**
- **O Sonnet é o melhor.** Ganha do ML por 5,8 pontos [3,0 a 8,4], nos mesmos pedidos.
- **O Haiku empata com o ML.** A diferença é de 1,4 ponto [−1,4 a 4,2]. Ele custa mais e é mais lento. No F1 de MGI e MF, o ML é melhor.
- **As regras só funcionam quando o pedido cita a sigla.** Com sigla, empatam com os LLMs (142 de 146). Sem sigla, caem para 64%. Quase toda a vantagem das regras vem da sigla: com o peso dela zerado, a acurácia cai de 74,0% para 60,4%.
- **A explicação dos LLMs é verificável:** o trecho citado está mesmo no pedido em 97% das respostas.
- **Em dados novos, a ordem se mantém.** No holdout de janeiro de 2026, o Sonnet acertou 95,4% [93,2–96,9] e o ML, 88,0% [84,9–90,6] (§4).

Fontes: `results/marco2.json` e `results/marco3.json`.

## 4. A curva: quanto a máquina pode fazer sozinha

Cada estratégia dá uma nota de confiança a cada pedido. Acima de um limiar, o pedido é encaminhado sozinho. Abaixo, vai para um servidor. Ir para a direita é automatizar mais e errar mais.

![Curva de cobertura por erro no teste](results/curva_cobertura_erro.png)

Para cada meta de erro, o limiar foi escolhido no dev. A meta de 1% foi adotada depois de ver o teste (§6). Por isso, o limiar foi **congelado** e medido em dados novos: 500 pedidos de janeiro de 2026. O hash desse conjunto foi registrado antes de rodar qualquer modelo, e houve uma rodada só.

**Resultado no holdout de 2026** (número principal):

| Regra congelada | Encaminhados sem pessoa | Erro entre eles [IC 95%] | Meta cumprida? | Reencaminhados que a máquina pegou certo | No teste de 2025 |
|---|---|---|---|---|---|
| **Sonnet, meta de 1%** | **86,6%** | **0,69% [0,24–2,02]** | **sim** (no ponto; o intervalo vai até 2%) | 12 de 12 | 85,4%, com 0,9% de erro |
| Sonnet, meta de 2% | 94,6% | 2,33% [1,30–4,12] | não | 15 de 17 | 96,6%, com 3,1% de erro |
| ML, meta de 1% | 67,2% | 1,49% [0,64–3,44] | não | 8 de 9 | 63,8%, com 0,9% de erro |
| ML, meta de 2% | 73,6% | 2,17% [1,11–4,23] | não | 9 de 11 | 69,6%, com 1,4% de erro |

- O holdout tem 23 pedidos reencaminhados.
- **Sem abstenção, a máquina acerta:** o Sonnet, 19 dos 23; o ML, 14.
- **Com a regra do Sonnet a 1%:** 12 dos 23 ficaram com a máquina, que acertou todos; os outros 11 foram para uma pessoa.
- Fontes: `results/holdout_2026_resultado.json` (`make holdout`) e `results/marco4.json` (`make abstencao`).

**A certeza humana separa o fácil do difícil, como a confiança do modelo.**
- **Quem classificou:** um leigo sem treino (eu), às cegas, 50 pedidos de 2025, 5 por órgão. Para cada um, marcou o órgão e uma certeza de 1 a 3.
- **Comparação justa:** os 50 vieram do treino, por isso regras e ML foram retreinados sem eles.
- Acertos por nível de certeza do leigo:

| Certeza do leigo | Pedidos | Leigo | Regras | ML | Haiku | Sonnet |
|---|---|---|---|---|---|---|
| 3 (seguro) | 14 | 12 | 13 | 13 | 13 | 13 |
| 2 | 22 | 15 | 18 | 21 | 20 | 21 |
| 1 (chute) | 14 | 3 | 9 | 9 | 12 | 13 |

- **A certeza do leigo separa o fácil do difícil.** Com certeza 3, ele acerta 12 de 14; com certeza 1, acerta 3 de 14.
- **As máquinas também caem nos casos em que o leigo chuta,** mas não todas igual: regras e ML acertam 9 de 14, e os LLMs, 12 e 13.
- **Nos 14 pedidos em que eu (leigo) tive certeza baixa, acertei 3 e o Sonnet acertou 13. É aí que o modelo mais ajuda.**
- **A confiança do Sonnet funciona nesses 50:** quando ele disse "alta", acertou 37 de 37.
- **O resultado do leigo é um limite inferior.** A ferramenta de revisão listava MJSP em vez de PF, e 3 pedidos da PF ficaram como "Outro". A amostra é pequena.
- Fonte: `results/revisao_manual.json` (`make revisao`). Detalhes em DADOS.md §7b.

## 5. A decisão

**O Sonnet encaminha sozinho quando declara confiança "alta", ou confiança "média" com o ML clássico concordando (probabilidade ≥ 0,8035). O resto vai para uma pessoa.**

Os números vêm do holdout de janeiro de 2026, com a regra congelada:

| Por 1.000 pedidos dos 10 órgãos | Hoje (o cidadão escolhe) | Com a recomendação |
|---|---|---|
| Encaminhados sem pessoa | 0 | 859 |
| Triados por uma pessoa | — | 141 (erro não medido) |
| Reencaminhados por destino errado | 68 | 6 (faixa de 2 a 17) na parte automática + erros da triagem humana |
| Dias de atraso somados | 274 | 26 (faixa de 8 a 69) + erros da triagem humana |
| Custo de API | 0 | US$ 2,52 |

**Como ler a tabela**
- **"Hoje"** é a régua do §1: os reencaminhados dos 10 órgãos.
- **Os ~6 erros por 1.000** são só da parte automática, que cobre 86% dos pedidos. O erro dos 14% que vão para uma pessoa não foi medido.
- **As contas** usam a distribuição real dos órgãos e 4 dias por reencaminhamento.

**Por que esse ponto**
- **Confirmado em dados novos.** No holdout, o erro automático foi de 0,69% [0,24–2,02], com 86,6% da fila saindo sem ninguém tocar. A meta de 1% foi cumprida no ponto, mas o intervalo de 95% vai até 2%.
- **A abstenção separa os difíceis.** Nos pedidos que sobram para uma pessoa, a máquina acertaria só 70%.

**O ML clássico sozinho não segurou a meta.** No holdout, o ML com o limiar de 1% errou 1,49% [0,64–3,44] e cobriu 67%. Se mandar texto para uma API externa não for aceitável, ele ainda reduz o erro de destino, mas com mais erro e menos cobertura que o Sonnet.

**O custo da API é pequeno:** US$ 2,52 por 1.000 pedidos no holdout, menos de 1 centavo de dólar por pedido. A escolha é de cobertura, erro e política de dados, mais do que de dinheiro.

## 6. O que deu errado

- **A meta combinada falhou no teste e de novo no holdout.**
  - A meta era 2% de erro. No dev, o Sonnet chegaria a 95,6% de cobertura com 1,88%. No teste, errou **3,1%**; no holdout de 2026, **2,33%**.
  - O limiar ficou na borda da curva, e 500 pedidos de dev não sustentam uma borda tão fina.
  - Passei a recomendar o ponto de 1%, também escolhido no dev, mas **depois de ver o teste**.
  - Para não ficar com um número escolhido a dedo, congelei esse limiar e medi em 500 pedidos novos (janeiro de 2026), com o hash registrado antes. Ele se manteve: 0,69% de erro, com cobertura de 86,6%.
- **Nomes de pessoa escaparam da máscara e foram enviados à API.**
  - **Medida:** rodei um detector offline em todos os 1.570 textos enviados:
    - os 1.000 de dev e teste;
    - os 500 do holdout;
    - os 50 da revisão manual;
    - os 20 exemplos do prompt.
  - **Como o detector funciona:** procura três padrões:
    - um prenome da lista do IBGE seguido de sobrenome;
    - uma pista ("Proprietário:", "Sr.", "naturalização de"…) seguida de nome;
    - uma palavra em maiúsculas logo depois de um `[NOME]`.
  - Ele marcou 75 textos, e li todos.
  - **Resultado:** **7 textos (0,45%) tinham nome de pessoa sem máscara**. Os outros 68 eram lugares, ruas, órgãos, cargos e termos técnicos.
    - Em 3, o nome ou prenome inteiro: o de quem fez o pedido, escrito no meio do texto; um prenome estrangeiro, fora da lista do IBGE; um nome depois de "Proprietário:".
    - Em 4, sobrou o sobrenome depois do prenome mascarado (ex.: `[NOME] SOBRENOME`).
  - **É um limite inferior.** Um nome estrangeiro solto, sem pista, passaria pelo detector.
  - Fonte: `results/pii_detector_offline.json`, só com ids. São pedidos que a CGU já publica em dados abertos, e os textos não estão neste repositório.
  - `make varredura` confere que nenhum trecho de 8 palavras de algum pedido aparece nos arquivos versionados. É um passo manual antes de cada commit; não há hook que o force.
- **O teste foi calculado mais de uma vez no Marco 2,** antes de existir o registro de avaliações. Nenhuma escolha mudou por isso. Está documentado em PROGRESSO.md.

## 7. O que a IA errou feio

O Sonnet errou 24 dos 500 pedidos. Li 20 deles, sorteados, ao lado do texto. Revisei comigo 3 classificações que o verificador contestou (`results/erros_classificacao_manual.json`):

| Tipo de erro | Casos | O que significa |
|---|---|---|
| Sem pista no texto | 8 | "Contracheque", "consultar débitos", o número de um pregão, a venda de um imóvel sem dizer de quem é. Nenhum classificador acerta; o certo é passar para uma pessoa. |
| Vinculação institucional | 6 | Não sabia que o Arquivo Nacional é do MGI (mandou 3 pedidos de naturalização para a PF), nem que as cepas da vacina da gripe saem em norma da ANVISA. |
| Mais de um órgão / rótulo discutível | 5 | A resposta é defensável. Dois desses a própria administração reencaminhou. Em "CPF bloqueado com dinheiro retido", o texto aponta para a Receita e para o BACEN. |
| Fato inventado | 1 | Disse que um grupo de destinação de bens da União tratava de armas apreendidas. |

**Três erros vieram com confiança "alta":**
- naturalização para a PF (era do Arquivo Nacional, no MGI);
- uma resolução do Conselho Monetário Nacional para o BACEN (foi reencaminhada ao MF);
- as cepas da vacina para o MS (era da ANVISA).

A abstenção não pega esses erros. Eles são o risco que fica.

Os erros de vinculação seriam fáceis de corrigir no prompt (Arquivo Nacional e SPU no MGI, por exemplo). Não corrigi, porque seria ajustar depois de ver o teste.

## 8. Limitações

- **Federal como análogo de municipal.**
  - Os órgãos federais são mais especializados que as secretarias de uma prefeitura, e os pedidos LAI são mais formais que os de ouvidoria.
  - Não há base pública municipal com o texto do pedido; a da Ouvidoria de BH só tem categorias.
- **Dez órgãos, não todos.** O sistema não sabe dizer "não é de nenhum destes". Os 2,23% de "sem competência" ficaram fora.
- **O rótulo é o órgão que respondeu.** Pode haver pedido respondido pelo órgão errado sem registro.
- **O teste é pequeno.** São 500 pedidos e só 34 reencaminhados; os intervalos de confiança estão em todas as tabelas.
- **O teste foi estratificado,** com mínimo de 25 por órgão (`MIN_POR_ORGAO_TESTE` em `src/triagem/config.py`). Os números por 1.000 pedidos estão reponderados pela distribuição real; sem abstenção, o erro do Sonnet sobe de 4,8% para 6,3%.
- **O erro da triagem humana não foi medido.** A revisão manual de 50 casos foi feita por um leigo sem treino (§4) e não mede o erro de um servidor.
- **A máscara de dados pessoais não é perfeita** (ver §6).

## 9. O que testar com uma prefeitura real

1. **Medir o erro de destino de hoje** no sistema da prefeitura: quantos pedidos trocam de secretaria e quanto atrasam.
2. **Rodar em sombra por um mês.** A máquina sugere e o servidor decide, sem mudar o fluxo. Isso mede a cobertura e o erro reais, com um limiar escolhido com margem.
3. **Medir o erro do servidor** na mesma amostra. Sem isso, não dá para saber o ganho líquido.
4. **Pôr no prompt a estrutura da prefeitura** (quem cuida de quê, unidades vinculadas). É a maior fonte de erro achada aqui.
5. **Definir a política de dados antes:** mascaramento revisado, contrato com o fornecedor da API, ou o ML local como alternativa.
6. **Incluir a saída "não é da prefeitura"** e medir quantos pedidos caem nela.

## Como reproduzir

```bash
make setup        # .venv com Python 3.11 e dependências
make all          # dados → dor → conjuntos → regras/ML → LLMs → abstenção → testes
make relatorio    # report.html e results/curva_cobertura_erro.png
make varredura    # antes de cada commit: procura dados pessoais reais nos arquivos versionados
```

**Chave da API.** Os LLMs precisam de `ANTHROPIC_API_KEY`, no ambiente ou num arquivo `.env`, que fica fora do git.
- As respostas ficam em cache (`cache/`, fora do git). Rodar de novo não gasta.
- Num clone novo, refazer tudo custa cerca de US$ 4,23: US$ 2,83 de dev e teste, US$ 1,26 do holdout e US$ 0,14 da revisão manual. `make estimar-custo` estima antes, e cada script para ao passar do seu teto.

**Conjunto de teste congelado.** `data/test.jsonl` tem 500 pedidos de novembro e dezembro de 2025, com dados pessoais mascarados.

```
SHA-256: d38c70d75a229b3d2e961b39a5b6d504ad226da644ba0d09d574aa5a9b261956
```

**Holdout de 2026, registrado antes de rodar qualquer modelo** (10/11/2026).
- **Composição:** `data/holdout_2026.jsonl` tem 500 pedidos de janeiro de 2026. O recorte, a estratificação e a máscara são os mesmos do teste, e textos iguais a algum pedido de 2025 foram tirados.
- **Por que existe:** para confirmar o limiar do Marco 4, que foi escolhido depois de ver o teste.
- **Regras congeladas:** Sonnet e ML, com os limiares de 1% e de 2% escolhidos no dev (`limiares_congelados` em `results/holdout_2026.json`). Nada é reajustado.
- **O que vale:** o resultado do holdout é o número principal da decisão. Se o erro passar de 1%, isso será dito.
- **Resultado** (rodado depois do registro): `results/holdout_2026_resultado.json`, com `make holdout`.

```
SHA-256: 9c5f39d6569c39cbfd7708475eecc781702cad15cfcd12524362f189a226bc49
```

**O texto dos pedidos não está neste repositório.**
- `data/*.jsonl`, `data/*.csv` e `cache/` ficam fora do git, mesmo mascarados.
- `make all` refaz os conjuntos a partir do arquivo público da CGU, e `tests/test_conjuntos.py` confere o hash localmente.
- A CGU regera o arquivo todo dia. O hash só se reproduz com a mesma versão, cujo SHA-256 está em `results/manifesto_download.json`.

**Testes:** `make test` (pytest). Cobrem:
- o hash do teste;
- a ausência de dados pessoais no que vai para a API;
- a leitura de JSON malformado;
- métricas com casos conhecidos;
- a curva de abstenção.

| Arquivo | O que tem |
|---|---|
| [DECISAO.md](DECISAO.md) | A decisão em uma página |
| `report.html` | Gráficos (abra no navegador) |
| [DADOS.md](DADOS.md) | Dados, rótulos, separação, máscara de dados pessoais |
| [PROGRESSO.md](PROGRESSO.md) | O que foi feito em cada marco, com as decisões e as correções |
| [ROTEIRO_VIDEO.md](ROTEIRO_VIDEO.md) | Roteiro de 2 minutos |
| `results/*.json` | Todas as métricas citadas aqui |
