"""Marco 7: v2 (Sonnet + consultar_unidade) contra v1, com dev em janeiro e holdout novo em fevereiro de 2026.

Uso:
  python -m triagem.marco7 estimar     # count_tokens (gratuito) + estimativa de custo de cada rodada
  python -m triagem.marco7 piloto      # 20 pedidos do TREINO de 2025: só para achar bug no laço
  python -m triagem.marco7 dev         # v2 nos 500 de janeiro de 2026 (dev da v2)
  python -m triagem.marco7 avaliar-dev # calibra o limiar da v2 em janeiro (critério da v1) e compara com a v1
  python -m triagem.marco7 congelar    # grava prompt, ferramenta, tabela, limiares e o hash de fevereiro (antes de rodar fev.)

Trava de gasto: soma o que a fase 2 já gastou (cache da v2 + chamadas da v1 depois de 10/11/2026) e para antes de
passar de TETO_FASE_USD.
"""
import argparse
import json
import random
import re

from triagem import config, llm, llm_v2
from triagem.marco3 import _sistema
from triagem.preparar import ler_jsonl

ARQ_ESTIMATIVA = config.RESULTS / "estimativa_custo_marco7.json"
ARQ_DEV = config.RESULTS / "marco7_dev.json"
ARQ_CONGELADO = config.RESULTS / "marco7_congelado.json"
TETO_FASE_USD = 12.0
INICIO_FASE_2 = "2026-11-10T21:00:00+00:00"   # depois da v1.0 (chamadas anteriores são da fase 1)
N_PILOTO = 20
# Metade do piloto cita alguma unidade (para exercitar a ferramenta); a outra metade é sorteada. Não ajusta nada.
PISTA_UNIDADE = re.compile(r"\b(secretaria|departamento|conselho|arquivo nacional|funda[çc][ãa]o|superintend[êe]ncia|coordena[çc][ãa]o)\b", re.I)
PRECO = llm.PRECOS[llm.MODELOS["sonnet"]]
SAIDA_MEDIA_V1 = 137          # tokens de saída por pedido, medidos no teste da v1 (Marco 3)
FRACAO_COM_FERRAMENTA = 0.30  # suposição até o piloto medir
SAIDA_CHAMADA = 40            # tokens de saída de um turno que só chama a ferramenta
ENTRADA_EXTRA_CHAMADA = 180   # tool_use + tool_result reenviados no turno seguinte


def sistemas() -> tuple[str, str]:
    s1 = _sistema()
    return s1, llm_v2.prompt_sistema_v2(s1)


def selecionar_piloto() -> list[dict]:
    treino = ler_jsonl(config.ARQ_TREINO)
    exemplos = {e["id"] for e in llm.escolher_exemplos(ler_jsonl(config.ARQ_TREINO_AMOSTRA))}
    candidatos = [r for r in treino if r["id"] not in exemplos and 80 <= len(r["texto"]) <= 1500]
    rng = random.Random(f"{config.SEED}-piloto-v2")
    com_pista = [r for r in candidatos if PISTA_UNIDADE.search(r["texto"])]
    escolhidos = rng.sample(com_pista, N_PILOTO // 2)
    ids = {r["id"] for r in escolhidos}
    escolhidos += rng.sample([r for r in candidatos if r["id"] not in ids], N_PILOTO - len(escolhidos))
    return sorted(escolhidos, key=lambda r: int(r["id"]))


def estimar() -> dict:
    import anthropic
    cli = anthropic.Anthropic()
    s1, s2 = sistemas()
    modelo = llm.MODELOS["sonnet"]
    msg = [{"role": "user", "content": "Pedido:\nx"}]
    pref_v1 = cli.messages.count_tokens(model=modelo, system=s1, messages=msg).input_tokens
    pref_v2 = cli.messages.count_tokens(model=modelo, system=s2, tools=[llm_v2.FERRAMENTA], messages=msg).input_tokens
    conjuntos = {"piloto (treino 2025)": selecionar_piloto(), "jan/2026 (dev da v2)": ler_jsonl(config.DATA / "holdout_2026.jsonl"),
                 "fev/2026 (holdout)": ler_jsonl(config.DATA / "holdout_2026_02.jsonl")}
    medio = {}
    for nome, regs in conjuntos.items():
        amostra = regs[::max(1, len(regs) // 25)]
        tot = sum(cli.messages.count_tokens(model=modelo, messages=[{"role": "user", "content": f"Pedido:\n{r['texto']}"}]).input_tokens
                  for r in amostra)
        medio[nome] = tot / len(amostra)

    def custo(prefixo, pedido, n, ferramenta: bool, batch=False, cache=True):
        base_in = (prefixo * PRECO["leitura_cache"] if cache else prefixo * PRECO["entrada"]) + pedido * PRECO["entrada"]
        c = base_in + SAIDA_MEDIA_V1 * PRECO["saida"]
        if ferramenta:  # um turno a mais em FRACAO_COM_FERRAMENTA dos pedidos
            extra = base_in + ENTRADA_EXTRA_CHAMADA * PRECO["entrada"] + SAIDA_CHAMADA * PRECO["saida"]
            c += FRACAO_COM_FERRAMENTA * extra
        c = c / 1e6 * n + (prefixo * PRECO["escrita_cache_5m"] / 1e6 * 10 if cache else 0)
        return round(c * (0.5 if batch else 1), 3)

    n = {k: len(v) for k, v in conjuntos.items()}
    rodadas = {
        "piloto v2 (20 do treino)": custo(pref_v2, medio["piloto (treino 2025)"], n["piloto (treino 2025)"], True),
        "v2 em jan/2026 (dev)": custo(pref_v2, medio["jan/2026 (dev da v2)"], n["jan/2026 (dev da v2)"], True),
        "v2 em fev/2026 (holdout)": custo(pref_v2, medio["fev/2026 (holdout)"], n["fev/2026 (holdout)"], True),
        "v1 em fev/2026, Batch API, com cache": custo(pref_v1, medio["fev/2026 (holdout)"], n["fev/2026 (holdout)"], False, batch=True),
        "v1 em fev/2026, Batch API, sem acerto de cache": custo(pref_v1, medio["fev/2026 (holdout)"], n["fev/2026 (holdout)"], False, batch=True, cache=False),
        "v1 em fev/2026, chamada normal com cache": custo(pref_v1, medio["fev/2026 (holdout)"], n["fev/2026 (holdout)"], False),
    }
    saida = {"metodo": "count_tokens da API (prefixos e ~25 pedidos de cada conjunto)", "fonte_precos": llm.FONTE_PRECOS,
             "tokens_prefixo_v1": pref_v1, "tokens_prefixo_v2": pref_v2,
             "tokens_pedido_medio": {k: round(v) for k, v in medio.items()},
             "suposicoes": {"saida_media_tokens": SAIDA_MEDIA_V1, "fracao_com_ferramenta": FRACAO_COM_FERRAMENTA,
                            "saida_turno_ferramenta": SAIDA_CHAMADA, "entrada_extra_turno_ferramenta": ENTRADA_EXTRA_CHAMADA},
             "rodadas_usd": rodadas}
    ARQ_ESTIMATIVA.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


def gasto_fase() -> float:
    """Tudo o que a fase 2 gastou: v2 (cache próprio) + chamadas da v1/Sonnet e Haiku registradas depois do início."""
    total = sum(r.get("custo_usd", 0.0) for r in llm_v2.cache_v2().dados.values())
    for m in llm.MODELOS.values():
        total += sum(r.get("custo_usd", 0.0) for r in llm.Cache(m).dados.values() if r.get("quando", "") >= INICIO_FASE_2)
    return total


def rodar_v2(regs: list[dict], rotulo: str, paralelo: int = 6, por_pedido: float = 0.005) -> list[dict]:
    import anthropic
    from concurrent.futures import ThreadPoolExecutor, as_completed
    s1, s2 = sistemas()
    cache = llm_v2.cache_v2()
    pend = [r for r in regs if cache.get(llm_v2.chave(llm_v2.corpo_base(s2, r["texto"]), r["id"])) is None]
    previsto = gasto_fase() + por_pedido * len(pend)
    print(f"{rotulo}: {len(regs)} pedidos, {len(pend)} a chamar; gasto da fase previsto ao fim: US$ {previsto:.2f} (teto {TETO_FASE_USD})")
    if previsto > TETO_FASE_USD:
        raise SystemExit("PARADO: passaria do teto da fase")
    cli = anthropic.Anthropic(max_retries=2)
    if pend:
        llm_v2.classificar(cli, s2, pend[0]["texto"], pend[0]["id"], cache)  # grava o prefixo no cache de prompt
        with ThreadPoolExecutor(max_workers=paralelo) as ex:
            fut = [ex.submit(llm_v2.classificar, cli, s2, r["texto"], r["id"], cache) for r in pend[1:]]
            for k, f in enumerate(as_completed(fut), 2):
                f.result()
                if k % 100 == 0:
                    g = gasto_fase()
                    print(f"  {k}/{len(pend)}, gasto da fase US$ {g:.3f}")
                    if g > TETO_FASE_USD:
                        for x in fut:
                            x.cancel()
                        raise SystemExit("PARADO: gasto da fase passou do teto")
    out = [llm_v2.classificar(cli, s2, r["texto"], r["id"], cache) for r in regs]  # tudo do cache agora
    print(f"fim. gasto da fase: US$ {gasto_fase():.3f}")
    return out


def checar_registros(regs: list[dict], recs: list[dict]) -> dict:
    """Procura bug: JSON final inválido, mais de 2 chamadas, stop_reason estranho, turno sem resposta."""
    problemas = []
    for r, rec in zip(regs, recs):
        dados_, erro = llm.interpretar(rec["resposta"])
        if erro:
            problemas.append((r["id"], f"json: {erro}"))
        if rec["n_chamadas"] > llm_v2.MAX_CHAMADAS:
            problemas.append((r["id"], f"{rec['n_chamadas']} chamadas"))
        if rec["stop_reason"] not in ("end_turn",):
            problemas.append((r["id"], f"stop_reason {rec['stop_reason']}"))
        if rec["n_chamadas"] == llm_v2.MAX_CHAMADAS and rec["turnos"][-1]["tool_choice"] != "none":
            problemas.append((r["id"], "3º turno sem tool_choice none"))
    return {"pedidos": len(regs), "com_ferramenta": sum(rec["n_chamadas"] > 0 for rec in recs),
            "chamadas": sum(rec["n_chamadas"] for rec in recs),
            "distribuicao": {n: sum(rec["n_chamadas"] == n for rec in recs) for n in range(llm_v2.MAX_CHAMADAS + 1)},
            "cache_de_prompt_lido": sum(rec["uso"]["cache_read_input_tokens"] > 0 for rec in recs),
            "custo_usd": round(sum(rec["custo_usd"] for rec in recs), 4), "problemas": problemas}


def piloto() -> None:
    regs = selecionar_piloto()
    recs = rodar_v2(regs, "piloto", paralelo=4)
    resumo = checar_registros(regs, recs)
    # segunda passada: tem de vir tudo do cache, sem chamar a API
    s1, s2 = sistemas()
    cache = llm_v2.cache_v2()
    resumo["segunda_passada_do_cache"] = all(cache.get(llm_v2.chave(llm_v2.corpo_base(s2, r["texto"]), r["id"])) is not None for r in regs)
    print(json.dumps(resumo, ensure_ascii=False, indent=1))
    exemplos = [(r["id"], c) for r, rec in zip(regs, recs) for c in rec["chamadas_ferramenta"]]
    for i, c in exemplos[:6]:
        print(f"  {i} | entrada: {c['entrada']!r} -> {[(x['sigla'], x['orgao_entre_os_10']) for x in c['saida']]}")


def linhas_v2(regs: list[dict], mdl) -> tuple[list[dict], list[dict]]:
    """Linhas no formato do Marco 4 (pred, nota) para a v2, e o registro por pedido sem texto."""
    from triagem import ml
    from triagem.marco4 import NIVEL
    s1, s2 = sistemas()
    cache = llm_v2.cache_v2()
    pred_ml, prob = ml.prever(mdl, [r["texto"] for r in regs])
    classes = list(mdl.classes_)
    linhas, pub = [], []
    for r, pm, pr in zip(regs, pred_ml, prob):
        rec = cache.get(llm_v2.chave(llm_v2.corpo_base(s2, r["texto"]), r["id"]))
        if rec is None:
            raise SystemExit(f"falta a v2 para {r['id']}")
        d, _ = llm.interpretar(rec["resposta"])
        prev, conf = (d["orgao"], d["confianca"]) if d else (None, None)
        pmap = dict(zip(classes, map(float, pr)))
        linhas.append({"id": r["id"], "verdadeiro": r["orgao_sigla"], "reencaminhado": r["reencaminhado"],
                       "v2": (prev, (NIVEL[conf], int(prev == pm), pmap.get(prev, 0.0)))})
        pub.append({"id": r["id"], "verdadeiro": r["orgao_sigla"], "previsto": prev, "confianca": conf, "ml": pm,
                    "p_ml_do_previsto": round(pmap.get(prev, 0.0), 4), "n_chamadas": rec["n_chamadas"],
                    "ferramenta_achou_orgao_dos_10": any(x["orgao_entre_os_10"] != "nenhum dos 10" for c in rec["chamadas_ferramenta"] for x in c["saida"]),
                    "custo_usd": rec["custo_usd"], "reencaminhado": r["reencaminhado"]})
    return linhas, pub


def avaliar_dev() -> dict:
    """Janeiro = dev da v2: escolhe o limiar da v2 pelo critério da v1 (maior cobertura com erro <= 1%) e compara."""
    from triagem.holdout import modelo_ml
    from triagem.marco2 import DIR_PRED
    from triagem.marco3 import comparacao_pareada
    from triagem.marco4 import NIVEL, aplicar, curva, escolher_limiar
    from triagem.metricas import intervalo_wilson
    regs = ler_jsonl(config.DATA / "holdout_2026.jsonl")
    lv2, pub = linhas_v2(regs, modelo_ml())
    v1 = {p["id"]: p for p in ler_jsonl(DIR_PRED / "holdout_2026.jsonl")}
    lv1 = [{"id": l["id"], "verdadeiro": l["verdadeiro"], "reencaminhado": l["reencaminhado"],
            "v1": (v1[l["id"]]["sonnet"], (NIVEL[v1[l["id"]]["confianca"]], int(v1[l["id"]]["sonnet"] == v1[l["id"]]["ml"]), v1[l["id"]]["p_ml_do_sonnet"]))}
           for l in lv2]
    m4 = json.loads((config.RESULTS / "marco4.json").read_text())
    lim_v1 = m4["estrategias"]["sonnet"]["por_meta"]["0.01"]["limiar"]
    esc = escolher_limiar(curva(lv2, "v2"), 0.01)
    lim_v2 = list(esc["limiar"])
    ac1 = [l["v1"][0] == l["verdadeiro"] for l in lv1]
    ac2 = [l["v2"][0] == l["verdadeiro"] for l in lv2]
    n = len(regs)

    def acur(ac):
        lo, hi = intervalo_wilson(sum(ac), n)
        return {"acuracia": round(sum(ac) / n, 4), "ic95": [round(lo, 4), round(hi, 4)]}

    com = [i for i, p in enumerate(pub) if p["n_chamadas"] > 0]
    sem = [i for i, p in enumerate(pub) if p["n_chamadas"] == 0]
    efeito = lambda idx: {"pedidos": len(idx), "corrigiu": sum((not ac1[i]) and ac2[i] for i in idx),
                          "causou": sum(ac1[i] and not ac2[i] for i in idx)}
    saida = {
        "conjunto": "holdout de janeiro de 2026 (500), usado como dev da v2",
        "criterio_limiar": "maior cobertura com erro <= 1% (o mesmo critério da v1, Marco 4)",
        "limiar_v1_congelado": lim_v1, "limiar_v2_escolhido": lim_v2,
        "v1": acur(ac1) | {"meta_1pct": aplicar(lv1, "v1", lim_v1)},
        "v2": acur(ac2) | {"meta_1pct": aplicar(lv2, "v2", lim_v2)},
        "comparacao_pareada_v2_menos_v1": comparacao_pareada(ac2, ac1),
        "ferramenta": {"pedidos_com_chamada": len(com), "chamadas": sum(p["n_chamadas"] for p in pub),
                       "distribuicao": {k: sum(p["n_chamadas"] == k for p in pub) for k in range(llm_v2.MAX_CHAMADAS + 1)},
                       "com_resultado_entre_os_10": sum(pub[i]["ferramenta_achou_orgao_dos_10"] for i in com)},
        "efeito_sobre_a_v1": {"com_ferramenta": efeito(com), "sem_ferramenta (variação do modelo)": efeito(sem)},
        "custo_v2_usd": round(sum(p["custo_usd"] for p in pub), 4),
        "custo_v2_por_1000_usd": round(1000 * sum(p["custo_usd"] for p in pub) / n, 4),
    }
    ARQ_DEV.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    with open(DIR_PRED / "v2_holdout_2026.jsonl", "w", encoding="utf-8") as f:
        for p in pub:
            f.write(json.dumps({k: v for k, v in p.items() if k != "custo_usd"}, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


def _sha(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()


def estado_congelavel() -> dict:
    """O que não pode mudar depois do registro de fevereiro."""
    import inspect
    from triagem import unidades
    s1, s2 = sistemas()
    dev = json.loads(ARQ_DEV.read_text())
    return {
        "modelo": llm_v2.MODELO,
        "sha256_prompt_v1": _sha(s1.encode("utf-8")),
        "sha256_prompt_v2": _sha(s2.encode("utf-8")),
        "sha256_requisicao_v2": _sha(json.dumps(llm_v2.corpo_base(s2, "<pedido>"), ensure_ascii=False, sort_keys=True).encode("utf-8")),
        "ferramenta": llm_v2.FERRAMENTA,
        "max_chamadas": llm_v2.MAX_CHAMADAS,
        "sha256_codigo_ferramenta_e_laco": _sha((inspect.getsource(llm_v2) + inspect.getsource(unidades)).encode("utf-8")),
        "sha256_tabela_unidades": _sha(unidades.ARQ.read_bytes()),
        "limiar_v1": dev["limiar_v1_congelado"], "limiar_v2": dev["limiar_v2_escolhido"],
        "sha256_holdout_fev": json.loads((config.RESULTS / "holdout_2026_02.json").read_text())["sha256"],
    }


def congelar() -> dict:
    from datetime import datetime, timezone
    from triagem.preparar import sha256
    arq_fev = config.DATA / "holdout_2026_02.jsonl"
    reg = json.loads((config.RESULTS / "holdout_2026_02.json").read_text())
    if sha256(arq_fev) != reg["sha256"]:
        raise SystemExit("o holdout de fevereiro mudou")
    if any(r.get("id") in {x["id"] for x in ler_jsonl(arq_fev)} for r in llm_v2.cache_v2().dados.values()):
        raise SystemExit("já existe chamada da v2 em pedido de fevereiro: não dá para registrar depois")
    estado = estado_congelavel() | {"congelado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                     "regra": "nada acima muda depois deste registro; fevereiro roda uma vez, v1 e v2 nos mesmos 500"}
    ARQ_CONGELADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n")
    reg["registrado_antes_de_rodar_modelos"] = True
    (config.RESULTS / "holdout_2026_02.json").write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in estado.items() if k != "ferramenta"}, ensure_ascii=False, indent=1))
    return estado


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["estimar", "piloto", "dev", "avaliar-dev", "congelar"])
    a = ap.parse_args()
    if a.cmd == "dev":
        recs = rodar_v2(ler_jsonl(config.DATA / "holdout_2026.jsonl"), "v2 em janeiro (dev)")
        print(json.dumps(checar_registros(ler_jsonl(config.DATA / "holdout_2026.jsonl"), recs), ensure_ascii=False, indent=1)[:1500])
        return
    {"estimar": estimar, "piloto": piloto, "avaliar-dev": avaliar_dev, "congelar": congelar}[a.cmd]()


if __name__ == "__main__":
    main()
