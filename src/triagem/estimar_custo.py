"""Estimativa de custo do Marco 3, com ou sem chamar a API.

Sem chave: estima tokens pelo número de caracteres (CARACTERES_POR_TOKEN, conservador para português).
Com `--contar`: usa messages.count_tokens da API (gratuito) num conjunto de pedidos para medir de verdade.

O cenário assume o prefixo (instruções + exemplos) lido do cache em quase todas as chamadas e algumas
gravações de cache (o cache de 5 minutos expira entre rodadas).
Saída: results/estimativa_custo_marco3.json
"""
import json
import sys

from triagem import config, llm
from triagem.preparar import ler_jsonl

CARACTERES_POR_TOKEN = 3.0      # conservador: português costuma dar mais caracteres por token
SAIDA_TOKENS = 150              # JSON com trecho + justificativa curta (max_tokens = 400)
GRAVACOES_DE_CACHE = 20         # por modelo, folga para o cache expirar entre lotes


def estimar(contar: bool = False) -> dict:
    amostra = ler_jsonl(config.ARQ_TREINO_AMOSTRA)
    sistema = llm.prompt_sistema(llm.escolher_exemplos(amostra))
    pedidos = ler_jsonl(config.ARQ_DEV) + ler_jsonl(config.ARQ_TESTE)
    n = len(pedidos)

    if contar:
        import anthropic
        cli = anthropic.Anthropic()
        res = cli.messages.count_tokens(model=llm.MODELOS["sonnet"], system=sistema,
                                        messages=[{"role": "user", "content": "Pedido:\nx"}])
        prefixo_tok = res.input_tokens
        amostra_ped = pedidos[::20]
        tot = 0
        for p in amostra_ped:
            r = cli.messages.count_tokens(model=llm.MODELOS["sonnet"],
                                          messages=[{"role": "user", "content": f"Pedido:\n{p['texto']}"}])
            tot += r.input_tokens
        pedido_tok_medio = tot / len(amostra_ped)
        metodo = f"count_tokens da API (prefixo + {len(amostra_ped)} pedidos)"
    else:
        prefixo_tok = len(sistema) / CARACTERES_POR_TOKEN
        pedido_tok_medio = sum(len(p["texto"]) + 10 for p in pedidos) / n / CARACTERES_POR_TOKEN
        metodo = f"caracteres / {CARACTERES_POR_TOKEN}"

    saida = {"metodo": metodo, "fonte_precos": llm.FONTE_PRECOS, "pedidos": n,
             "tokens_prefixo": round(prefixo_tok), "tokens_pedido_medio": round(pedido_tok_medio),
             "tokens_saida_assumidos": SAIDA_TOKENS, "modelos": {}}
    total = 0.0
    for apelido, modelo in llm.MODELOS.items():
        p = llm.PRECOS[modelo]
        c = {
            "leitura_cache": n * prefixo_tok * p["leitura_cache"] / 1e6,
            "escrita_cache": GRAVACOES_DE_CACHE * prefixo_tok * p["escrita_cache_5m"] / 1e6,
            "entrada_pedidos": n * pedido_tok_medio * p["entrada"] / 1e6,
            "saida": n * SAIDA_TOKENS * p["saida"] / 1e6,
        }
        c["total"] = sum(c.values())
        c["sem_cache_de_prompt"] = (n * (prefixo_tok + pedido_tok_medio) * p["entrada"] + n * SAIDA_TOKENS * p["saida"]) / 1e6
        saida["modelos"][apelido] = {k: round(v, 3) for k, v in c.items()}
        total += c["total"]
    saida["total_estimado_usd"] = round(total, 2)
    saida["teto_usd"] = 5.0
    return saida


def main() -> None:
    est = estimar(contar="--contar" in sys.argv)
    (config.RESULTS / "estimativa_custo_marco3.json").write_text(json.dumps(est, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(est, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
