# Triagem de pedidos públicos: regras, ML clássico e IA

Dá para encaminhar pedidos de cidadãos ao órgão certo de forma automática e segura? Quanto da fila dá para automatizar sem aumentar o erro? Este projeto compara quatro abordagens no mesmo teste e decide onde a IA entra e onde uma pessoa decide.

Para um diretor: [DECISAO.md](DECISAO.md) (uma página). Gráficos: abra `report.html` no navegador. Diário do trabalho: [PROGRESSO.md](PROGRESSO.md).

## 1. A dor

Em 2025, **8,52% dos pedidos de acesso à informação federais chegaram ao órgão errado**: 11.111 de 130.407.
- 6,58% foram reencaminhados a outro órgão.
- 2,23% receberam "não é de nossa competência".

O reencaminhado leva **4 dias a mais**: a mediana do prazo foi de 17 dias, contra 13 dos que chegaram certo. Todos os reencaminhados tiveram o prazo prorrogado.

Fonte: base pública do Fala.BR (CGU). Os números saem de `make dor` (`results/dor.json`).

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

Fontes: `results/marco2.json` e `results/marco3.json`.

## 4. A curva: quanto a máquina pode fazer sozinha

Cada estratégia dá uma nota de confiança a cada pedido. Acima de um limiar, o pedido é encaminhado sozinho. Abaixo, vai para um servidor. Ir para a direita é automatizar mais e errar mais.

![Curva de cobertura por erro no teste](results/curva_cobertura_erro.png)

Para cada meta de erro, o limiar foi escolhido no dev. Resultado no teste, na meta de 1%.

**Atenção:** a meta combinada era 2% e falhou no teste (§6). A meta de 1% foi adotada depois de ver o teste. Os números abaixo precisam ser confirmados em dados novos.

| Estratégia | Encaminhados sem pessoa | Erro entre eles [IC 95%] | Vão para um servidor |
|---|---|---|---|
| **Sonnet** | **85,4%** | **0,9% [0,4–2,4]** | 73 de 500 |
| Haiku | 71,2% | 1,1% [0,4–2,9] | 144 |
| ML (sem API) | 63,8% | 0,9% [0,3–2,7] | 181 |
| ML + regras (sem API) | 55,0% | 0,0% [0,0–1,4] | 225 |

Fonte: `results/marco4.json` (`make abstencao`).

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
- **A confiança do Sonnet funciona nesses 50:** quando ele disse "alta", acertou 37 de 37.
- **O resultado do leigo é um limite inferior.** A ferramenta de revisão listava MJSP em vez de PF, e 3 pedidos da PF ficaram como "Outro". A amostra é pequena.
- Fonte: `results/revisao_manual.json` (`make revisao`). Detalhes em DADOS.md §7b.

## 5. A decisão

**O Sonnet encaminha sozinho quando declara confiança "alta", ou confiança "média" com o ML clássico concordando (probabilidade ≥ 0,8035). O resto vai para um servidor.**

| Por 1.000 pedidos dos 10 órgãos | Hoje (o cidadão escolhe) | Com a recomendação |
|---|---|---|
| Encaminhados sem pessoa | 0 | 847 |
| Triados por um servidor | — | 153 |
| Reencaminhados por destino errado | 68 | 8 (faixa de 3 a 20) + erros do servidor |
| Dias de atraso somados | 274 | 31 (faixa de 12 a 81) + erros do servidor |
| Custo de API | 0 | US$ 2,83 |

As contas usam a distribuição real dos órgãos e 4 dias por reencaminhamento. O erro do servidor não foi medido.

**Por que esse ponto.**
- No teste, o erro automático foi de 0,9% [0,4–2,4], e 85% da fila saiu sem ninguém tocar.
- Os pedidos que sobram são mesmo os difíceis: neles, a máquina acertaria só 73%.

**Fragilidade.** O ponto foi escolhido depois de ver o teste e fica perto da borda: no dev, aceitar um pedido a mais já leva o erro de 0,92% para 1,15%. Antes de usar, escolha o limiar com margem e confirme em dados novos.

**Se mandar texto para uma API externa não for aceitável,** use o ML clássico com abstenção. Encaminha 64% sozinho, com o mesmo erro, sem custo e sem sair da máquina.

**O custo da API é pequeno:** US$ 2,83 por 1.000 pedidos, menos de 1 centavo de dólar por pedido. A escolha entre Sonnet e ML é de cobertura e de política de dados, mais do que de dinheiro.

## 6. O que deu errado

- **A meta combinada falhou no teste.**
  - A meta era 2% de erro. No dev, o Sonnet chegaria a 95,6% de cobertura com 1,88%; no teste, errou **3,1%**.
  - O limiar ficou na borda da curva, e 500 pedidos de dev não sustentam uma borda tão fina.
  - Passei a recomendar o ponto de 1%, também escolhido no dev, mas **depois de ver o teste**. Por isso o 0,9% não é uma estimativa limpa e precisa ser confirmado em dados novos.
- **Nomes de pessoa escaparam da máscara e foram enviados à API.**
  - **Medida:** rodei um detector offline em todos os 1.070 textos enviados:
    - os 1.000 de dev e teste;
    - os 50 da revisão manual;
    - os 20 exemplos do prompt.
  - **Como o detector funciona:** procura um prenome da lista do IBGE seguido de sobrenome, ou uma pista ("Proprietário:", "Sr.", "naturalização de"…) seguida de nome. Ele marcou 56 textos, e li todos.
  - **Resultado:** **3 textos (0,28%) tinham nome de pessoa sem máscara**. Os outros 53 eram lugares, ruas, órgãos e termos técnicos.
    - O nome de quem fez o pedido, escrito no meio do texto.
    - Um prenome estrangeiro, fora da lista do IBGE.
    - Um nome depois de "Proprietário:".
  - **É um limite inferior.** Um nome estrangeiro solto, sem pista, passaria pelo detector.
  - Fonte: `results/pii_detector_offline.json`, só com ids. São pedidos que a CGU já publica em dados abertos, e os textos não estão neste repositório.
  - `make varredura` confere, antes de cada commit, que nenhum trecho de 8 palavras de algum pedido aparece nos arquivos versionados.
- **O teste foi calculado mais de uma vez no Marco 2,** antes de existir o registro de avaliações. Nenhuma escolha mudou por isso. Está documentado em PROGRESSO.md.

## 7. O que a IA errou feio

O Sonnet errou 24 dos 500 pedidos. Li 20 deles, sorteados, ao lado do texto (`results/erros_classificacao_manual.json`):

| Tipo de erro | Casos | O que significa |
|---|---|---|
| Sem pista no texto | 7 | "Contracheque", "consultar débitos", o número de um pregão. Nenhum classificador acerta; o certo é passar para uma pessoa. |
| Vinculação institucional | 6 | Não sabia que o Arquivo Nacional é do MGI (mandou 3 pedidos de naturalização para a PF), nem que as cepas da vacina da gripe saem em norma da ANVISA. |
| Mais de um órgão / rótulo discutível | 4 | A resposta é defensável; dois desses a própria administração reencaminhou. |
| Pista ignorada | 2 | "CPF bloqueado com dinheiro retido" foi para a Receita; o rótulo é BACEN. O ML acertou. |
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
- **O erro da triagem humana não foi medido.** A revisão manual de 50 casos (pendente) dará uma primeira estimativa.
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
- Num clone novo, refazer tudo custa cerca de US$ 2,83. `make estimar-custo` estima antes, e o script para se o gasto passar de US$ 5.

**Conjunto de teste congelado.** `data/test.jsonl` tem 500 pedidos de novembro e dezembro de 2025, com dados pessoais mascarados.

```
SHA-256: d38c70d75a229b3d2e961b39a5b6d504ad226da644ba0d09d574aa5a9b261956
```

**Holdout de 2026, registrado antes de rodar qualquer modelo** (10/11/2026).
- **Composição:** `data/holdout_2026.jsonl` tem 500 pedidos de janeiro de 2026. O recorte, a estratificação e a máscara são os mesmos do teste, e textos iguais a algum pedido de 2025 foram tirados.
- **Por que existe:** para confirmar o limiar do Marco 4, que foi escolhido depois de ver o teste.
- **Regras congeladas:** Sonnet e ML, com os limiares de 1% e de 2% escolhidos no dev (`limiares_congelados` em `results/holdout_2026.json`). Nada é reajustado.
- **O que vale:** o resultado do holdout é o número principal da decisão. Se o erro passar de 1%, isso será dito.

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
