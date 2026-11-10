# Dados

Este documento descreve de onde vêm os dados, quais campos existem de verdade, como o rótulo foi definido e como os dados pessoais foram mascarados.
Todo número citado aqui sai de `results/dor.json` ou de `results/preparacao.json`, gerados por `make dor` e `make preparar`.

## 1. Fontes

São os dados abertos de pedidos de acesso à informação (LAI) do Fala.BR, mantidos pela CGU, referentes a 2025. Existem dois arquivos, e eles não são iguais.

| Arquivo | URL | Tem o texto do pedido? | Pedidos em 2025 | Uso no projeto |
|---|---|---|---|---|
| Base completa | `.../FalaBR/Arquivos_FalaBR/Pedidos_csv_2025.zip` | Não | 150.190 | Medir a dor |
| Base com texto ("Filtrado") | `.../FalaBR/Arquivos_FalaBR_Filtrado/Arquivos_csv_2025.zip` | Sim | 83.773 | Classificar |

O prefixo das URLs é `https://dadosabertos-download.cgu.gov.br`.

A página de dados abertos (https://falabr.cgu.gov.br/web/dadosabertoslai) só aponta para a base completa. A base com texto aparece na página "Busca de pedidos e respostas – download de dados", no gov.br.

A CGU regera os arquivos diariamente. Os CSVs usados aqui têm data de 08/11/2026 no nome. O SHA-256 de cada zip está em `results/manifesto_download.json`. O conjunto de teste fica congelado mesmo que os arquivos mudem (ver seção 6).

## 2. Campos que existem de verdade

Os campos foram conferidos nos arquivos, não no dicionário. Os CSVs estão em UTF-16, com separador `;` e campos vazios preenchidos com espaço.

**Base com texto** (`*_Pedidos_csv_2025.csv`, 24 colunas):

| Campo | O que é | Uso |
|---|---|---|
| `IdPedido`, `ProtocoloPedido` | Identificadores | Chave |
| `Esfera` | Sempre "Federal" nesta base | Filtro |
| `OrgaoDestinatario` | Órgão que recebeu e respondeu o pedido | **Rótulo** |
| `Situacao` | Sempre "Concluída" nesta base | Nenhum |
| `DataRegistro`, `PrazoAtendimento`, `DataResposta` | Datas (DD/MM/AAAA) | Separação temporal e atraso |
| `ResumoSolicitacao` | Título curto escrito pelo cidadão | **Entrada** (mascarada) |
| `DetalhamentoSolicitacao` | Texto do pedido | **Entrada** (mascarada) |
| `FoiProrrogado`, `FoiReencaminhado` | "Sim"/"Não" | Dor |
| `FormaResposta`, `OrigemSolicitacao` | Canal | Nenhum |
| `IdSolicitante` | Id anônimo do solicitante; "0" = não identificado | Limite de pedidos por pessoa na amostra. Não é salvo nos conjuntos. |
| `AssuntoPedido`, `SubAssuntoPedido`, `Tag` | Classificação feita pelo SIC **depois** de receber o pedido | **Não usado**: vazaria a resposta |
| `Resposta` | Texto da resposta do órgão | Não é entrada. Serve só para entender casos de "sem competência". |
| `Decisao`, `EspecificacaoDecisao`, `DetalhamentoDecisao` | Tipo de resposta | Dor e filtro do rótulo |
| `MotivoNegativaAcesso`, `PrazoRestricaoAcesso` | Negativa por dado pessoal | Nenhum |

**Base completa** (23 colunas). Tem os mesmos metadados, mais `UF` e `Municipio`, e **não tem** `ResumoSolicitacao`, `DetalhamentoSolicitacao` nem `Resposta`. Inclui todas as esferas (federal, municipal, estadual) e pedidos ainda em andamento.

**O que não existe nas bases** e faria falta:
- o órgão de **origem** de um pedido reencaminhado (só aparece o destino final);
- a data do reencaminhamento;
- o motivo pelo qual um pedido ficou fora da base com texto.

## 3. A dor: quantos pedidos chegam ao órgão errado

**Universo:** base completa, esfera federal, situação "Concluída", com 130.407 pedidos em 2025.

| Indicador | Pedidos | % |
|---|---:|---:|
| Reencaminhados para outro órgão | 8.575 | 6,58% |
| Respondidos com "Órgão não tem competência" | 2.906 | 2,23% |
| Reencaminhados **e** sem competência no destino | 370 | 0,28% |
| **Chegaram ao órgão errado** (reencaminhado ou sem competência) | **11.111** | **8,52%** |
| Somando os casos em que "parte da informação é de competência de outro órgão" | — | 9,84% |

**Como ler:** de cada 100 pedidos federais, cerca de 8 ou 9 foram abertos no órgão errado. O número é um **piso**, porque só conta os erros que o próprio órgão percebeu e registrou.

**Atraso:**

| Grupo | Dias até a resposta (mediana) | Média | Prorrogados |
|---|---:|---:|---:|
| Chegaram ao órgão certo | 13 | 13,8 | 17% |
| Reencaminhados | 17 | 17,8 | **100%** |
| Sem competência | 8 | 10,9 | 20% |

- Um pedido reencaminhado leva **4 dias a mais** (na mediana e na média) e foi sempre prorrogado. Os 100% sugerem que o sistema prorroga automaticamente quando há reencaminhamento. Isso não foi confirmado na documentação.
- O pedido "sem competência" é respondido rápido, mas a resposta é "não é aqui". O cidadão precisa abrir outro pedido, e esse tempo extra não aparece na base.
- **Premissa:** `DataRegistro` é a data em que o cidadão abriu o pedido, e não a data do reencaminhamento. Se fosse a do reencaminhamento, o atraso real seria maior.
- A diferença de 4 dias é uma associação. Pedidos reencaminhados podem ser também mais difíceis por outros motivos.

**Por órgão** (top 10 do projeto): a MGI recebe 23% dos seus pedidos por reencaminhamento e a PF recebe 13%. São órgãos para onde vão pedidos abertos no lugar errado. O MEC é quem mais responde "sem competência" (6,5%). Ver `federal_concluida_por_orgao_top10` em `results/dor.json`.

**Na base com texto**, a taxa é parecida (8,42%), o que indica que a seleção da CGU não distorce muito esse indicador.

## 4. Recorte

1. Base com texto, 2025, federal.
2. **Os 10 órgãos com mais pedidos** na base com texto, contando só pedidos com rótulo confiável: MS, PETROBRAS, ANVISA, BACEN, INSS, MF, MGI, MEC, ANEEL, PF.
   - Na base completa, o 1º lugar é o INEP (6.322 pedidos). Na base com texto, o INEP cai para fora do top 10. Provavelmente os pedidos ao INEP envolvem dados pessoais (notas, inscrições) e foram excluídos pela CGU. O DNIT, 10º na base completa, também fica de fora: muitos dos seus pedidos com texto são "sem competência". A disputa pelo 10º lugar é apertada: PF tem 1.301 pedidos e FUNAI, o 11º, tem 1.297 (`ranking_base_com_texto_rotulo_confiavel` em `results/preparacao.json`).
3. Resultado: 25.172 pedidos.

## 5. Critério de rotulagem

**Rótulo = órgão que recebeu e respondeu o pedido (`OrgaoDestinatario`).**

| Situação | O que o campo guarda | Rótulo confiável? | O que fazemos |
|---|---|---|---|
| Pedido normal | Órgão que respondeu | Sim | Entra nos conjuntos |
| Reencaminhado | Órgão **final**, depois do reencaminhamento | Sim | Entra. Fica marcado (`reencaminhado: true`) porque são os casos difíceis de verdade |
| "Órgão não tem competência" | Órgão que **recusou** | Não: o órgão certo é desconhecido | Fica fora (500 pedidos em `data/fora_competencia.jsonl`, para análise à parte) |
| "Parte da informação é de outro órgão" | Órgão que respondeu a parte que lhe cabia | Parcial | Entra. O pedido tem dois destinos possíveis e isso é uma limitação |
| Texto idêntico enviado a órgãos diferentes | Vários órgãos | Ambíguo | Descartado (241 pedidos) |
| Texto idêntico repetido no mesmo órgão | O mesmo | Sim | Fica só o primeiro (329 descartados) |

Para conferir que o rótulo de um reencaminhado é o destino final, foram lidas amostras. Exemplo: "o MCTI redirecionou a demanda ao MMA", e o pedido aparece com `OrgaoDestinatario` = MMA.

**Atenção para a analogia com a prefeitura.** No Fala.BR, quem escolhe o órgão é o **cidadão**, e não há uma triagem central. O "erro" medido aqui é a escolha errada do cidadão, corrigida depois pelo órgão. Na prefeitura, a pergunta é se uma triagem central (humana ou automática) acertaria o setor. O rótulo usado é o destino que a administração considerou correto.

### Revisão manual (para o Luigi)

- `data/revisao_manual_50.csv` tem 50 pedidos do treino, 5 por órgão, em ordem aleatória, **sem o rótulo da base**. A ideia é que você escolha o órgão às cegas, sem ser influenciado pelo rótulo.
- Preencha `orgao_luigi` com uma das siglas (MS, PETROBRAS, ANVISA, BACEN, INSS, MF, MGI, MEC, ANEEL, PF) ou com `OUTRO`, `certeza_1a3` (1 = chute, 3 = certeza) e `observacao`.
- O rótulo da base está em `data/revisao_manual_50_gabarito.csv`. A concordância será calculada por script no Marco 2.
- O `id` permite achar o pedido em `train.jsonl`. A revisão só é cega se você não fizer essa consulta antes de preencher.

## 6. Separação treino / dev / teste

A separação é **temporal**, pela data de registro:

| Conjunto | Período | Pedidos | Como foi escolhido | Uso |
|---|---|---:|---|---|
| `train.jsonl` | jan–ago 2025 | 16.778 | Todos | Treino do ML clássico |
| `train_amostra.jsonl` | jan–ago 2025 | 2.000 | Estratificado, mínimo 50 por órgão | Escrever regras, exemplos do prompt, ML "pequeno" de referência |
| `dev.jsonl` | set–out 2025 | 500 | Estratificado | Ajustar regras, prompt e limiar de abstenção |
| `test.jsonl` | nov–dez 2025 | 500 | Estratificado | **Só a medição final** |

**Por que temporal e não sorteio aleatório:**
- Na base dos 10 órgãos (25.172 pedidos), 140 solicitantes identificados fizeram 10 ou mais pedidos cada. Juntos somam 3.935 pedidos (15,6%). Um deles fez 508. Outros 4.304 pedidos não têm solicitante identificado (`IdSolicitante` = "0"). Fonte: `solicitantes_base_10_orgaos` em `results/preparacao.json`.
- Muitos desses pedidos seguem um modelo fixo. Num sorteio aleatório, o mesmo modelo cairia no treino e no teste, e o classificador pareceria melhor do que é.
- A separação temporal reproduz o uso real: o sistema aprende com o passado e classifica os pedidos novos.

**Outras regras:**
- **Estratificação:** a cota por órgão é proporcional ao volume, com mínimo de 25 no dev e no teste. A soma dá exatamente 500 (método dos maiores restos).
- **Teto por solicitante:** no máximo 5 pedidos de um mesmo solicitante identificado no dev, no teste e na amostra de treino, para nenhum autor dominar a medição. O treino completo não tem teto.
- **Seed:** fixa (`SEED = 42` em `src/triagem/config.py`), com um gerador por conjunto. Rodar `make preparar` de novo produz arquivos idênticos.
- **Teste congelado:** `data/test.jsonl` tem o SHA-256 registrado em `data/test.sha256`, no README e em `tests/test_conjuntos.py`. Se o arquivo já existir, `make preparar` reaproveita os mesmos pedidos e para com erro se o hash não conferir.
- **Distribuição do teste:** MS 91, ANVISA 74, BACEN 72, MF 43, PETROBRAS 43, MEC 41, MGI 40, PF 39, INSS 30, ANEEL 27. São 34 pedidos reencaminhados.

**Campos de cada linha:** `id`, `orgao`, `orgao_sigla`, `texto` (resumo + detalhamento, mascarado), `reencaminhado`, `decisao`, `data_registro`.

**Só `texto` pode ser entrada de classificador.** `reencaminhado` e `decisao` só são conhecidos depois da resposta e servem apenas para análise, por exemplo para medir o acerto nos casos reencaminhados.

## 7. Dados pessoais

Todo texto salvo em `data/*.jsonl` e `data/*.csv` passou pela máscara abaixo. Só esse texto vai para os classificadores e para a API. A máscara reduz o risco mas não o zera: as taxas medidas estão no fim da seção. O código está em `src/triagem/pii.py`.

**Camada 1, regex** (o dado vira um marcador como `[CPF]`):
- e-mail;
- CPF (com ou sem pontuação, e qualquer sequência solta de 11 dígitos);
- telefone (com DDD, com hífen ou precedido de "tel/cel/whatsapp/fone/contato");
- CEP;
- RG;
- data de nascimento, quando rotulada ("Data de nascimento: …", "nascida em …");
- endereço do tipo "Rua X, 123";
- números de documento quando vêm rotulados (passaporte, NIS/PIS, CNH, cartão SUS, título de eleitor, matrícula SIAPE, OAB). Nesses casos o rótulo fica e só o número é mascarado ("PIS [DOCUMENTO]").

**Camada 2, nomes de pessoas.** Cada texto passa por quatro etapas, em ordem:

1. **NER do spaCy** (`pt_core_news_md`, entidade PER), com filtro.
   - Sem o filtro, o NER marcava como nome palavras como "Agradeço", "Bacen", "Selic", "Prouni", "Registro de Operações Financeiras" e "Casa da Moeda do Brasil", que são justamente pistas do órgão certo.
   - A entidade é aceita se começa com um prenome frequente do Censo 2010 (IBGE via brasil.io, `data/ref/prenomes_ibge.txt`) ou se tem 2 ou mais palavras com maiúscula e nenhuma delas é palavra comum.
2. **Sequências** em caixa alta ou com inicial maiúscula, a partir de um prenome: "SUS JULIANA PAULA …" (exemplo inventado), listas de advogados.
3. **Pistas no texto**: "Meu nome é …", "Eu, …", "Nome: …", "Atenciosamente, …". Isso pega nomes com prenome raro, fora da lista do IBGE.
4. **Absorção de sobrenomes** que ficaram colados a um `[NOME]` ("[NOME] DE SOUSA TAVEIRA", exemplo inventado).

**Nome que batiza instituição ou lugar fica.** As etapas 1 e 2 não mascaram nomes que vêm logo depois de "Plataforma", "Fundação", "Hospital", "município de", "São", "avenida" e termos parecidos ("Plataforma Nilo Peçanha", "Fundação Oswaldo Cruz"). Isso não é dado pessoal e é pista da triagem.

**Listas de apoio:**
- **"Palavra comum"** (`data/ref/palavras_comuns.txt`) é uma palavra que, no próprio corpus, aparece pelo menos 10 vezes em minúsculas e pelo menos metade das vezes em que aparece com maiúscula. "registro" (5.280 contra 1.144) é comum. "silva" (126 contra 1.854) não é, porque quase sempre é sobrenome. A contagem é feita depois de tirar os e-mails, para "fulana.souza@…" não contar como palavra.
- **Exclusões fixas:** prenomes que também são termos do domínio (MEI, LEI, BRASIL, SANTOS…), siglas de órgãos e palavras institucionais ou de lugar (Ministério, Secretaria, São, Rio…).
- Regerar as duas listas: `make ref`.

**Mascaramentos** nos 18.278 textos salvos (treino, dev, teste e fora de competência): 4.953 nomes, 668 e-mails, 368 CPFs, 231 telefones, 188 documentos, 139 CEPs, 115 endereços, 56 datas de nascimento, 23 RGs.

**Testes** (`tests/test_pii.py`, `tests/test_conjuntos.py`):
- casos positivos e negativos para cada regra, incluindo os padrões de vazamento achados na verificação do Marco 1 (com nomes inventados);
- termos do domínio que não podem ser apagados (anos, NUP, protocolo, BR-101, Lei 12.527, CNPJ, GTIN, registro Anvisa, contrato, processo SEI, nomes de doenças, São Paulo);
- uma varredura que falha se sobrar qualquer dado estruturado nos conjuntos.

**Taxas medidas** em dev e teste (1.000 textos), com `make auditoria-pii` (resumo em `results/auditoria_pii.json`):
- **Onde a máscara atua:** 164 dos 1.000 textos têm pelo menos um `[NOME]`.
- **Nomes que escapam:** uma varredura procura prenome seguido de sobrenome sem máscara. Achou 6 textos, e os 6 eram falsos alarmes: nomes de instituição ou lugar que a regra acima preserva de propósito ("Fundação Oswaldo Cruz", "município de Frederico Westphalen", "Hospital Júlia Kubitschek") e "ITÁLIA Obrigada". Essa varredura não vê nomes raros escritos em minúsculas, então o risco real é maior que zero. A verificação independente achou ainda sobrenomes em caixa alta que também são palavras comuns, colados a um `[NOME]` ("[NOME] LEITE …").
- **Nome depois de pronome de tratamento:** a verificação independente achou um nome completo vazando depois de "Sra." porque o sobrenome era palavra comum ("Torres"). Isso foi corrigido com uma regra própria: depois de Sr./Sra./Dr./Prezado, um prenome do IBGE é mascarado com todos os sobrenomes que vierem em seguida, mesmo os que são palavras comuns. A sequência para em palavra institucional ("Dr. [NOME] Hospital …"), para não apagar o nome do hospital.
- **Excesso de máscara:** o script sorteia (seed fixa) 80 trechos trocados por `[NOME]`, com o original ao lado, para classificação manual. **7 de 80 (8,8%) não eram nomes de pessoa**: 3 empresas, 1 operadora, 1 cidade, 1 doença (Ataxia de Friedreich) e a abreviação "Att".
  - Os outros 73 são pessoas, inclusive autoridades citadas.
  - A classificação, item a item, está em `results/auditoria_pii_manual.json`.
  - A amostra com o texto original (`results/auditoria_pii_amostra.csv`) tem nomes reais e por isso fica fora do git.

**Limitações conhecidas** (risco residual):
- Nomes de uma só palavra que não são prenome do IBGE ficam (ex.: "ministro Padilha"). Em geral são autoridades citadas, não o solicitante.
- Nomes escritos todos em minúsculas ("fulano beltrano") só são pegos se o NER os marcar.
- Números longos **sem rótulo** não são mascarados. Na base, quase sempre são GTIN, registro Anvisa, CNPJ, contrato ou processo SEI, e mascará-los apagaria pistas da triagem. Um NIS ou cartão SUS solto, sem rótulo, passaria.
- Números de processo judicial ou administrativo ficam no texto. Eles podem ajudar a reidentificar alguém, mas também são sinal para a triagem.
- Nomes de autoridades públicas também são mascarados quando começam com prenome ("Gabriel Galípolo", "Fernando Haddad"). Isso tira um pouco de sinal (Galípolo → BACEN), mas é a opção conservadora.
- A CGU já seleciona o que publica com texto. Esta máscara é uma segunda camada, não a única.

**O que escapou e foi enviado à API (achado no Marco 3).**
- **Os casos.** Ao ler os erros dos modelos, achei 2 pedidos do teste com nome de pessoa sem máscara:
  - um prenome estrangeiro fora da lista do IBGE, que o NER pegou em uma ocorrência e não pegou nas outras duas;
  - um nome depois de "Proprietário:", que não está entre as pistas.
- **Medida.** Depois revisei à mão os 29 textos de dev e teste sobre naturalização, genealogia ou certidão, os temas em que esse tipo de nome é mais provável. Os 2 casos estavam entre eles (ids e critério em `results/pii_revisao_dirigida.json`). Os outros 971 textos e os 20 exemplos do prompt não foram lidos à mão: a taxa de escape fora desse recorte é desconhecida, e a varredura automática não pegou esses 2 casos.
- **Para onde foram.** Esses textos foram enviados à API da Anthropic. Ficam só no cache local, fora do git.
- **Por que não corrigi.** Corrigir a máscara agora mudaria o teste congelado e o seu hash. Fica como limitação.
- **Em produção:** prenomes estrangeiros, pistas como "Proprietário:"/"Titular:"/"Requerente:", e uma revisão por amostragem antes de enviar a qualquer serviço externo.

## 8. Limitações e viés da amostra

- **Federal como análogo de municipal.** Os órgãos federais são mais especializados que as secretarias de uma prefeitura, e os pedidos LAI são mais formais que os da ouvidoria municipal. O Plano B (Ouvidoria de BH) foi verificado e, pelo cabeçalho do arquivo de jan/2025, **não tem texto livre**, só categorias.
- **Base com texto é parcial.** Ela tem 56% dos pedidos, só os concluídos e só os que a CGU tornou públicos. O INEP praticamente some.
- **O rótulo é o destino final aceito.** Pode haver pedidos respondidos pelo órgão errado sem que ninguém tenha registrado o erro.
- **Pedidos com dois destinos** ("parte é de outro órgão") têm um só rótulo.
- **Mudança no tempo.** O teste (nov–dez) pode ter temas que não existiam no treino (jan–ago). Isso é realista e tende a baixar as métricas de todas as abordagens por igual.
