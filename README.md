# Triagem de pedidos públicos: IA x regras

> Em construção. Este README será reescrito no Marco 5 para um avaliador de negócio.

## A pergunta

Dá para encaminhar pedidos de cidadãos ao setor certo de forma automática e segura? E quanto da fila dá para automatizar sem aumentar o erro?

## A dor, medida

Em 2025, **8,52% dos pedidos de acesso à informação federais chegaram ao órgão errado**. São 11.111 de 130.407 pedidos:
- 6,58% foram reencaminhados a outro órgão;
- 2,23% foram respondidos com "não é de nossa competência".

Um pedido reencaminhado levou **4 dias a mais** para ser respondido (mediana de 17 contra 13 dias).

Os números saem de `make dor`, que grava `results/dor.json`. Definições e limitações estão em [DADOS.md](DADOS.md).

## Dados

São pedidos LAI do Fala.BR (CGU), de 2025, dos 10 órgãos federais com mais pedidos. Eles servem como análogo das secretarias de uma prefeitura, porque não existe base pública municipal com o texto dos pedidos. Essa é uma limitação.

Detalhes em [DADOS.md](DADOS.md).

## Conjunto de teste congelado

`data/test.jsonl` tem 500 pedidos de nov–dez/2025, estratificados por órgão e com dados pessoais mascarados.

```
SHA-256: d38c70d75a229b3d2e961b39a5b6d504ad226da644ba0d09d574aa5a9b261956
```

Os pedidos do teste foram sorteados no Marco 1, antes de qualquer classificador ser escrito. Depois disso só mudou a máscara de dados pessoais, nunca a escolha dos pedidos.

**O texto dos pedidos não está neste repositório.** Os arquivos `data/*.jsonl` e `data/*.csv` ficam fora do git, mesmo mascarados. `make all` refaz todos os conjuntos a partir do arquivo público da CGU e `tests/test_conjuntos.py` confere o hash localmente.

A CGU regera o arquivo todos os dias. O hash acima só se reproduz com a mesma versão do arquivo, cujo SHA-256 está em `results/manifesto_download.json`. Se a CGU alterar pedidos de 2025, o teste do hash falha e avisa que os dados mudaram.

## Como rodar

```bash
make setup   # cria .venv com Python 3.11 e instala dependências
make all     # baixa dados, mede a dor, prepara conjuntos, roda testes
make varredura  # antes de cada commit: procura dados pessoais reais nos arquivos versionados
```

## Andamento

- [x] Marco 1: dados, dor, conjuntos
- [ ] Marco 2: regras e ML clássico
- [ ] Marco 3: Claude Haiku e Sonnet
- [ ] Marco 4: abstenção e decisão
- [ ] Marco 5: entrega
