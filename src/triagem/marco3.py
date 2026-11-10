"""Marco 3: Claude Haiku 5.5 e Claude Sonnet 5.5 em dev e teste, com cache e custo medido.

Uso:
  python -m triagem.marco3 rodar --modelo haiku --conjunto dev [--limite 20] [--paralelo 4]
  python -m triagem.marco3 avaliar [--teste]   # só lê o cache e gera results/marco3.json (não chama a API)

O teste só é avaliado com --teste, e cada avaliação é registrada em results/registro_avaliacoes_teste.jsonl
com o hash do prompt, para mostrar que o prompt não mudou depois de ver o teste.

Trava de custo: antes de cada chamada nova, soma o custo já gasto (cache) com uma estimativa do que falta.
Se passar de TETO_USD, para antes de chamar.

O que vai para o git (results/marco3.json e results/predicoes/<modelo>_<conjunto>.jsonl) não tem
texto: nem o pedido, nem o trecho citado, nem a justificativa. Esses ficam só em cache/ (fora do git).
"""
import argparse
import hashlib
import json
import statistics
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from triagem import config, llm, metricas
from triagem.marco2 import DIR_PRED, REGISTRO_TESTE, avaliar_completo
from triagem.preparar import ler_jsonl

TETO_USD = 5.0
CONJUNTOS = {"dev": config.ARQ_DEV, "test": config.ARQ_TESTE}


def _sistema():
    return llm.prompt_sistema(llm.escolher_exemplos(ler_jsonl(config.ARQ_TREINO_AMOSTRA)))


def gasto_total() -> float:
    total = 0.0
    for modelo in llm.MODELOS.values():
        total += sum(r.get("custo_usd", 0.0) for r in llm.Cache(modelo).dados.values())
    return total


def rodar(apelido: str, conjunto: str, limite: int | None, paralelo: int) -> None:
    import anthropic

    modelo = llm.MODELOS[apelido]
    regs = ler_jsonl(CONJUNTOS[conjunto])[:limite]
    sistema = _sistema()
    cache = llm.Cache(modelo)
    cliente = anthropic.Anthropic(max_retries=2)
    pendentes = [r for r in regs if cache.get(llm.chave_cache(llm.corpo_requisicao(modelo, sistema, r["texto"]), r["id"])) is None]
    print(f"{apelido}/{conjunto}: {len(regs)} pedidos, {len(regs) - len(pendentes)} já no cache, {len(pendentes)} a chamar")
    if not pendentes:
        return

    # Custo por chamada: média do que já foi gasto com este modelo, ou a estimativa conservadora.
    gastos = [r["custo_usd"] for r in cache.dados.values()]
    por_chamada = statistics.mean(gastos) if gastos else (0.0025 if apelido == "sonnet" else 0.0002)
    previsto = gasto_total() + por_chamada * len(pendentes)
    print(f"gasto até agora: US$ {gasto_total():.3f}; previsto ao fim deste lote: US$ {previsto:.3f}")
    if previsto > TETO_USD:
        raise SystemExit(f"PARADO: o gasto previsto (US$ {previsto:.2f}) passa do teto de US$ {TETO_USD:.2f}.")

    def uma(r):
        return llm.chamar(cliente, llm.corpo_requisicao(modelo, sistema, r["texto"]), r["id"], cache)

    # A 1ª chamada sozinha grava o prefixo no cache de prompt; as outras já leem dele.
    uma(pendentes[0])
    feitos = 1
    with ThreadPoolExecutor(max_workers=paralelo) as ex:
        futuros = [ex.submit(uma, r) for r in pendentes[1:]]
        for f in as_completed(futuros):
            f.result()
            feitos += 1
            if feitos % 50 == 0:
                g = gasto_total()
                print(f"  {feitos}/{len(pendentes)} chamadas, gasto acumulado US$ {g:.3f}")
                if g > TETO_USD:
                    for x in futuros:
                        x.cancel()
                    raise SystemExit(f"PARADO: gasto acumulado US$ {g:.2f} passou do teto.")
    print(f"fim. gasto acumulado: US$ {gasto_total():.3f}")


def comparacao_pareada(ac_a: list[bool], ac_b: list[bool], n_boot: int = 2000) -> dict:
    """Diferença de acurácia (a - b) nos mesmos pedidos, com intervalo de 95% por bootstrap pareado."""
    import random
    rng = random.Random(f"{config.SEED}-pareada")
    n = len(ac_a)
    difs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        difs.append(sum(ac_a[i] - ac_b[i] for i in idx) / n)
    difs.sort()
    return {"diferenca_pp": round(100 * (sum(ac_a) - sum(ac_b)) / n, 1),
            "ic95_pp": [round(100 * difs[int(0.025 * n_boot)], 1), round(100 * difs[int(0.975 * n_boot) - 1], 1)],
            "so_a_acerta": sum(a and not b for a, b in zip(ac_a, ac_b)),
            "so_b_acerta": sum(b and not a for a, b in zip(ac_a, ac_b))}


def comparacoes(conjunto: str) -> dict:
    """Haiku, Sonnet, ML e regras comparados dois a dois nos mesmos pedidos (lê results/predicoes/)."""
    acertos = {}
    for nome in ("sonnet", "haiku", "ml", "regras"):
        regs = {r["id"]: r for r in ler_jsonl(DIR_PRED / f"{nome}_{conjunto}.jsonl")}
        acertos[nome] = {i: r["previsto"] == r["verdadeiro"] for i, r in regs.items()}
    ids = sorted(acertos["sonnet"])
    pares = [("sonnet", "ml"), ("haiku", "ml"), ("sonnet", "haiku"), ("haiku", "regras")]
    return {f"{a}_vs_{b}": comparacao_pareada([acertos[a][i] for i in ids], [acertos[b][i] for i in ids]) for a, b in pares}


def hash_prompt(sistema: str) -> str:
    """Hash só do texto do system. O schema, o effort e o max_tokens entram na chave do cache e em hash_requisicao."""
    return hashlib.sha256(sistema.encode("utf-8")).hexdigest()[:12]


def avaliar(usar_teste: bool = False) -> dict:
    sistema = _sistema()
    classes = llm.SIGLAS
    saida = {"fonte_precos": llm.FONTE_PRECOS, "hash_prompt": hash_prompt(sistema), "teste_calculado": usar_teste,
             "modelos": {}, "gasto_total_usd": round(gasto_total(), 4)}
    conjuntos = {c: a for c, a in CONJUNTOS.items() if c == "dev" or usar_teste}
    for apelido, modelo in llm.MODELOS.items():
        cache = llm.Cache(modelo)
        saida["modelos"][apelido] = {"id_modelo": modelo}
        for conjunto, arq in conjuntos.items():
            regs = ler_jsonl(arq)
            recs = [cache.get(llm.chave_cache(llm.corpo_requisicao(modelo, sistema, r["texto"]), r["id"])) for r in regs]
            if any(x is None for x in recs):
                saida["modelos"][apelido][conjunto] = {"status": "incompleto",
                                                       "no_cache": sum(x is not None for x in recs), "total": len(regs)}
                continue
            pred, conf, erros, literal, linhas = [], [], [], [], []
            for r, rec in zip(regs, recs):
                dados, erro = llm.interpretar(rec["resposta"])
                pred.append(dados["orgao"] if dados else None)
                conf.append(dados["confianca"] if dados else None)
                erros.append(erro or (None if rec["stop_reason"] in ("end_turn", None) else rec["stop_reason"]))
                lit = bool(dados) and llm.trecho_esta_no_pedido(dados["trecho"], r["texto"])
                literal.append(lit)
                linhas.append({"id": r["id"], "verdadeiro": r["orgao_sigla"], "previsto": pred[-1],
                               "confianca": conf[-1], "erro_resposta": erro, "trecho_literal": lit,
                               "cita_sigla": metricas.cita_sigla(r["texto"], r["orgao_sigla"]),
                               "reencaminhado": r["reencaminhado"]})
            DIR_PRED.mkdir(parents=True, exist_ok=True)
            with open(DIR_PRED / f"{apelido}_{conjunto}.jsonl", "w", encoding="utf-8") as f:
                for ln in linhas:
                    f.write(json.dumps(ln, ensure_ascii=False, sort_keys=True) + "\n")
            usos = [x["uso"] for x in recs]
            lat = [x["latencia_s"] for x in recs]
            custo = sum(x["custo_usd"] for x in recs)
            verdade = [r["orgao_sigla"] for r in regs]
            por_conf = {}
            for c in llm.CONFIANCAS:
                idx = [i for i, x in enumerate(conf) if x == c]
                if idx:
                    por_conf[c] = {"n": len(idx), "acuracia": round(sum(pred[i] == verdade[i] for i in idx) / len(idx), 4)}
            saida["modelos"][apelido][conjunto] = avaliar_completo(regs, pred, classes) | {
                "custo_usd": round(custo, 4),
                "custo_por_1000_usd": round(1000 * custo / len(regs), 4),
                "latencia_media_s": round(statistics.mean(lat), 3),
                "latencia_mediana_s": round(statistics.median(lat), 3),
                "tokens": {k: sum(u[k] for u in usos) for k in usos[0]},
                "respostas_invalidas": sum(e is not None for e in erros),
                "trecho_literal_pct": round(100 * sum(literal) / len(literal), 1),
                "acuracia_por_confianca": por_conf,
            }
    saida["comparacoes_pareadas"] = {c: comparacoes(c) for c in conjuntos
                                     if all("acuracia" in saida["modelos"][ap].get(c, {}) for ap in llm.MODELOS)}
    arq = config.RESULTS / "marco3.json"
    if not usar_teste and arq.exists():
        # Sem --teste, mantém o resultado de teste já registrado (não recalcula nem apaga).
        antigo = json.loads(arq.read_text())
        for ap in llm.MODELOS:
            if "test" in antigo.get("modelos", {}).get(ap, {}):
                saida["modelos"][ap]["test"] = antigo["modelos"][ap]["test"]
        if "test" in antigo.get("comparacoes_pareadas", {}):
            saida["comparacoes_pareadas"]["test"] = antigo["comparacoes_pareadas"]["test"]
        saida["teste_calculado"] = antigo.get("teste_calculado", False)
    saida["hash_requisicao"] = hashlib.sha256(json.dumps(
        llm.corpo_requisicao("<modelo>", sistema, "<pedido>"), sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    arq.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    acur_teste = {ap: m["test"]["acuracia"] for ap, m in saida["modelos"].items() if "acuracia" in m.get("test", {})}
    if usar_teste and acur_teste:
        with open(REGISTRO_TESTE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"quando": datetime.now(timezone.utc).isoformat(timespec="seconds"), "marco": 3,
                                "hash_prompt": saida["hash_prompt"], "modelos": {ap: llm.MODELOS[ap] for ap in acur_teste},
                                "acuracia_teste": acur_teste}, ensure_ascii=False, sort_keys=True) + "\n")
    return saida


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rodar")
    r.add_argument("--modelo", choices=list(llm.MODELOS), required=True)
    r.add_argument("--conjunto", choices=list(CONJUNTOS), required=True)
    r.add_argument("--limite", type=int)
    r.add_argument("--paralelo", type=int, default=4)
    av = sub.add_parser("avaliar")
    av.add_argument("--teste", action="store_true", help="avalia também o teste (registrado)")
    a = ap.parse_args()
    if a.cmd == "rodar":
        rodar(a.modelo, a.conjunto, a.limite, a.paralelo)
    else:
        s = avaliar(a.teste)
        for ap_, d in s["modelos"].items():
            for c in CONJUNTOS:
                if c not in d:
                    continue
                m = d[c]
                if "acuracia" in m:
                    print(f"{ap_:7} {c:5} acur {m['acuracia']:.3f} F1 {m['f1_macro']:.3f} | US$/1000 {m['custo_por_1000_usd']:.3f}"
                          f" | lat {m['latencia_media_s']:.2f}s | inválidas {m['respostas_invalidas']} | trecho literal {m['trecho_literal_pct']}%")
                else:
                    print(ap_, c, m)
        print(json.dumps(s["comparacoes_pareadas"], ensure_ascii=False))
        print(f"gasto total: US$ {s['gasto_total_usd']}")


if __name__ == "__main__":
    main()
