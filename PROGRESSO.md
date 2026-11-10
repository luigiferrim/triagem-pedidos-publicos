# Progresso

Atualizado a cada marco. Os números saem dos arquivos em `results/`.

## Marco atual: 2 (baselines: regras e ML clássico)

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
