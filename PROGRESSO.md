# Progresso

Atualizado a cada marco. Os números saem dos arquivos em `results/`.

## Marco atual: 3 (Claude Haiku e Sonnet). Aguardando o Luigi exportar a chave da API

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
