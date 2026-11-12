# Como a mesa de triagem funciona

Este texto é para quem não é da área técnica. Ele explica o caminho de um pedido, do momento em que chega até o órgão que vai respondê-lo.

## O problema, em uma frase

Quando o cidadão pede uma informação ao governo, ele mesmo escolhe para qual órgão mandar. Às vezes erra. Nos 10 órgãos federais estudados, 68 de cada 1.000 pedidos foram parar no lugar errado e precisaram ser reencaminhados, com 4 dias a mais de espera. Na Prefeitura de São Paulo, foram 123 de cada 1.000.

## O caminho de um pedido

```
pedido do cidadão
      │
      ▼
1. Máscara: tira nome, CPF, e-mail, telefone e endereço
      │
      ▼
2. IA (Claude Sonnet): lê o pedido e sugere o órgão,
   com um trecho do texto, uma frase de motivo e o grau de certeza
      │
      ▼
3. Regra de segurança: a IA declara certeza alta?
   Ou declara certeza média, e um segundo modelo concorda com segurança?
      │                                   │
     sim                                 não
      │                                   │
      ▼                                   ▼
4a. Vai direto ao órgão sugerido    4b. Vai para um servidor, que decide,
                                        com a sugestão da IA ao lado
```

### 1. Máscara

Antes de qualquer coisa, o texto passa por uma máscara que troca dados pessoais por marcadores. "Meu nome é Fulana de Tal, CPF 000.000.000-00" vira "Meu nome é [NOME], CPF [CPF]". Só o texto mascarado sai do computador.

A máscara não é perfeita: nos 1.570 textos auditados (até janeiro de 2026), 7 ainda tinham um nome de pessoa (0,45%). Por isso, antes de usar com pedidos reais, ela precisa ser revisada, e a prefeitura precisa de um contrato com o fornecedor da IA.

### 2. A IA sugere um órgão

A IA recebe o pedido mascarado, a lista dos órgãos com uma linha sobre o que cada um faz e alguns exemplos de pedidos já encaminhados. Ela devolve quatro coisas:
- **o órgão sugerido;**
- **um trecho do próprio pedido** que justifica a escolha, para o servidor conferir em segundos;
- **uma frase de motivo**, como "o pedido trata de vacinação, que é do Ministério da Saúde";
- **o grau de certeza:** alta, média ou baixa.

### 3. A regra de segurança

A IA erra pouco, mas erra. Por isso, ela só encaminha sozinha em dois casos:
- ela declara certeza **alta**; ou
- ela declara certeza **média**, e um segundo modelo, mais simples, que roda no próprio computador e aprendeu com pedidos antigos, **concorda** com ela e está bem seguro.

Esse segundo modelo funciona como uma segunda opinião nos casos médios. Com certeza média e sem o acordo dele, ou com certeza baixa, o pedido não segue sozinho. Com certeza alta, o pedido segue mesmo que o segundo modelo discorde.

### 4. Quem decide

- **Os pedidos claros** (cerca de 85 em cada 100) vão direto ao órgão sugerido.
- **Os outros** (cerca de 15 em cada 100) vão para um servidor. Ele vê a sugestão, o trecho e o motivo, e decide. A palavra final é sempre dele.

## Quanto isso ajuda

Medido em 1.200 pedidos novos, de março a outubro de 2026, com a regra congelada antes:

| Por 1.000 pedidos | Hoje | Com a mesa |
|---|---|---|
| Vão ao órgão errado | 68 (reencaminhados) | cerca de 16 na parte automática, mais os erros da triagem humana, que não foram medidos |
| Precisam de uma pessoa para decidir | todos passam pela escolha do cidadão | cerca de 145 |
| Custo da IA | — | cerca de US$ 2,83 (menos de 1 centavo por pedido) |

**O que não foi atingido.** A meta era errar no máximo 1% dos pedidos encaminhados sozinhos. O erro ficou entre 1,4% e 1,9%, dependendo de como se conta um lote de pedidos repetidos. Ajustar a regra com mais dados não resolveu.

## O que a mesa não faz

- **Não responde ao cidadão.** Ela só escolhe para onde o pedido vai.
- **Não sabe dizer "não é de nenhum destes órgãos".** Ela sempre escolhe um da lista. Um pedido que não é da prefeitura precisa de uma pessoa.
- **Não pega todo erro.** Às vezes a IA erra com certeza alta, por exemplo quando não sabe a qual órgão uma unidade pertence. A regra de segurança não pega esses casos.

## Antes de ligar de verdade

Um mês de **piloto em sombra** numa prefeitura: a IA sugere, o servidor decide como sempre, e nada muda no fluxo. No fim, sabe-se quanto a IA acertaria, quanto o servidor acerta e a partir de onde é seguro deixar a mesa encaminhar sozinha. O plano está em [DECISAO.md](DECISAO.md).

*Números: `results/manchete.json` (federal), `results/marco9_dor.json` (São Paulo) e `results/pii_detector_offline.json` (máscara). Detalhes técnicos: [README.md](README.md).*
