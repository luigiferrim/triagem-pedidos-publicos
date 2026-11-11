"""v2 (Marco 7): o Sonnet com a ferramenta consultar_unidade (tabela do SIORG), no máximo 2 chamadas por pedido.

Igual à v1 em tudo o mais: mesmos exemplos no prompt, mesmo JSON final (output_config.format), effort "low",
thinking "between_tools", cache de prompt (ferramenta + system ficam fixos e são cacheados juntos).

O limite de 2 chamadas é garantido no código: tool_choice "auto" com disable_parallel_tool_use (no máximo 1 por
turno) e, depois da 2ª chamada, o turno seguinte vai com tool_choice "none" (o modelo tem de responder).

Cada pedido gera um registro no cache local (cache/claude-sonnet-5-5-v2.jsonl): a transcrição dos turnos, as
chamadas à ferramenta (entrada e saída), o uso de tokens somado, o custo e a resposta final.
"""
import hashlib
import json
import time
from datetime import datetime, timezone

from triagem import config, llm
from triagem.unidades import consultar_unidade

MODELO = llm.MODELOS["sonnet"]
NOME_CACHE = "claude-sonnet-5-5-v2"
MAX_CHAMADAS = 2
MAX_TOKENS = 600

FERRAMENTA = {
    "name": "consultar_unidade",
    "description": (
        "Consulta a estrutura oficial do governo federal (SIORG) e diz a qual órgão pertence uma unidade, secretaria, "
        "departamento ou entidade citada no pedido. Entrada: a sigla ou o nome da unidade, como aparece no pedido "
        "(ex.: 'SPU', 'Arquivo Nacional', 'CARF'). Saída: até 3 unidades com o órgão entre os 10 a que pertencem, "
        "ou 'nenhum dos 10' quando a unidade é de outro órgão ou é uma entidade vinculada com atendimento próprio."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"texto": {"type": "string", "description": "sigla ou nome da unidade citada no pedido"}},
        "required": ["texto"],
        "additionalProperties": False,
    },
    "strict": True,
}

PARAGRAFO_FERRAMENTA = """
## Ferramenta de consulta

Você tem a ferramenta consultar_unidade, que consulta a estrutura oficial do governo federal (SIORG).
Use-a quando o pedido citar uma unidade, secretaria, departamento, conselho, fundação ou sigla e você não tiver
certeza de a qual dos 10 órgãos ela pertence. Não use quando o órgão já estiver claro no texto.
Você pode consultar no máximo 2 vezes. Se a consulta disser "nenhum dos 10" ou não achar nada, decida pelo
conteúdo do pedido, como faria sem a ferramenta. Depois, responda no mesmo formato JSON de sempre.
"""


def prompt_sistema_v2(sistema_v1: str) -> str:
    return sistema_v1 + "\n" + PARAGRAFO_FERRAMENTA


def corpo_base(sistema: str, texto: str) -> dict:
    return {
        "model": MODELO,
        "max_tokens": MAX_TOKENS,
        "tools": [FERRAMENTA],
        "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": f"Pedido:\n{texto}"}],
        "output_config": {"format": {"type": "json_schema", "schema": llm.SCHEMA}, "effort": "low"},
        "thinking": {"type": "between_tools"},
        "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
    }


def chave(corpo: dict, id_pedido: str) -> str:
    return hashlib.sha256(json.dumps(corpo, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest() + ":" + id_pedido


def _criar(cliente, corpo, tentativas=4):
    import anthropic
    espera = 5.0
    for t in range(tentativas):
        try:
            return cliente.messages.create(**corpo)
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError):
            if t == tentativas - 1:
                raise
            time.sleep(espera)
            espera *= 2


def classificar(cliente, sistema: str, texto: str, id_pedido: str, cache: llm.Cache) -> dict:
    """Roda o laço de no máximo 2 consultas e devolve o registro (do cache, se já existir)."""
    corpo = corpo_base(sistema, texto)
    k = chave(corpo, id_pedido)
    if (r := cache.get(k)) is not None:
        return r | {"do_cache": True}
    llm.checar_pii(texto)
    mensagens = list(corpo["messages"])
    chamadas, turnos, uso_total, inicio = [], [], {"input_tokens": 0, "output_tokens": 0,
                                                    "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}, time.perf_counter()
    resposta, stop = None, None
    for turno in range(MAX_CHAMADAS + 1):
        pedido = dict(corpo, messages=mensagens)
        if len(chamadas) >= MAX_CHAMADAS:
            pedido["tool_choice"] = {"type": "none"}
        resp = _criar(cliente, pedido)
        uso = {kk: getattr(resp.usage, kk, 0) or 0 for kk in uso_total}
        for kk in uso_total:
            uso_total[kk] += uso[kk]
        stop = resp.stop_reason
        turnos.append({"turno": turno, "stop_reason": stop, "uso": uso, "tool_choice": pedido["tool_choice"]["type"],
                       "request_id": getattr(resp, "_request_id", None)})
        usos = [b for b in resp.content if b.type == "tool_use"]
        if stop == "tool_use" and usos:
            b = usos[0]
            entrada = b.input.get("texto", "") if isinstance(b.input, dict) else ""
            saida = consultar_unidade(entrada)
            chamadas.append({"turno": turno, "entrada": entrada, "saida": saida})
            mensagens = mensagens + [
                {"role": "assistant", "content": [blk.to_dict() for blk in resp.content]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": b.id,
                                              "content": json.dumps(saida, ensure_ascii=False) if saida else "nenhuma unidade encontrada"}]},
            ]
            continue
        resposta = next((blk.text for blk in resp.content if blk.type == "text"), None)
        break
    registro = {
        "chave": k, "id": id_pedido, "modelo": MODELO, "versao": "v2", "resposta": resposta, "stop_reason": stop,
        "chamadas_ferramenta": chamadas, "n_chamadas": len(chamadas), "turnos": turnos, "uso": uso_total,
        "custo_usd": round(llm.custo_usd(MODELO, uso_total), 8), "latencia_s": round(time.perf_counter() - inicio, 3),
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    cache.put(registro)
    return registro | {"do_cache": False}


def cache_v2() -> llm.Cache:
    return llm.Cache(NOME_CACHE)
