"""Marco 4: abstenção. Onde a máquina encaminha sozinha e onde uma pessoa decide.

Cada estratégia dá, para cada pedido, um órgão previsto e uma nota de confiança. Um limiar na nota divide a fila:
nota >= limiar -> encaminhamento automático; abaixo -> fila humana.
- cobertura = fração encaminhada automaticamente;
- erro = fração de erros entre os encaminhados automaticamente.

A ordem das notas (abaixo) é a natural: primeiro o sinal do próprio modelo, depois a concordância com o ML.
Ela foi definida antes de calcular as curvas, mas depois de o Marco 3 já ter mostrado a acurácia por confiança
no teste e o Marco 2 a concordância ML + regras no teste. O limiar é escolhido só no dev, para cada meta de
erro; o teste só mede o que acontece com o limiar escolhido. Lê apenas results/predicoes/ (sem texto).

Estratégias (nota em ordem lexicográfica):
- ml:          probabilidade máxima do ML.
- ml_regras:   [regras concordam com o ML], depois a probabilidade do ML. Custo zero.
- haiku/sonnet: confiança declarada (alta > média > baixa), depois [concorda com o ML], depois a probabilidade
                que o ML dá ao órgão escolhido pelo LLM.

Saída: results/marco4.json
"""
import json

from triagem import config
from triagem.marco2 import DIR_PRED
from triagem.metricas import intervalo_wilson
from triagem.preparar import ler_jsonl

METAS_ERRO = [0.01, 0.02, 0.05]
# Meta combinada antes de rodar: 2%. No teste, o ponto escolhido no dev para 2% ficou acima da meta (ver regra_pre_registrada),
# porque o limiar caiu na borda da curva. A recomendação passou para o ponto de 1% (também escolhido no dev).
# Essa troca foi feita DEPOIS de ver o teste e está registrada em results/marco4.json.
META_PRE_REGISTRADA = 0.02
META_RECOMENDADA = 0.01
ESTRATEGIAS = ["ml", "ml_regras", "haiku", "sonnet"]
NIVEL = {"alta": 2, "media": 1, "baixa": 0, None: -1}
CUSTO_LLM_POR_1000 = {"ml": 0.0, "ml_regras": 0.0}   # haiku e sonnet vêm de results/marco3.json


def _por_id(nome: str, conjunto: str) -> dict:
    return {r["id"]: r for r in ler_jsonl(DIR_PRED / f"{nome}_{conjunto}.jsonl")}


def carregar(conjunto: str) -> list[dict]:
    ml, regras = _por_id("ml", conjunto), _por_id("regras", conjunto)
    prob = {r["id"]: r["prob"] for r in ler_jsonl(DIR_PRED / f"ml_{conjunto}_probabilidades.jsonl")}
    llms = {ap: _por_id(ap, conjunto) for ap in ("haiku", "sonnet")}
    linhas = []
    for i in sorted(ml):
        linha = {"id": i, "verdadeiro": ml[i]["verdadeiro"], "reencaminhado": ml[i]["reencaminhado"]}
        p = prob[i]
        linha["ml"] = (ml[i]["previsto"], (max(p.values()),))
        linha["ml_regras"] = (ml[i]["previsto"], (int(regras[i]["previsto"] == ml[i]["previsto"]), max(p.values())))
        for ap, d in llms.items():
            prev = d[i]["previsto"]
            linha[ap] = (prev, (NIVEL[d[i]["confianca"]], int(prev == ml[i]["previsto"]), p.get(prev, 0.0)))
        linhas.append(linha)
    return linhas


def curva(linhas: list[dict], estrategia: str) -> list[dict]:
    """Um ponto por limiar distinto (empates entram ou saem juntos)."""
    itens = sorted(((l[estrategia][1], l[estrategia][0] == l["verdadeiro"]) for l in linhas), reverse=True)
    n = len(itens)
    pontos, acertos = [], 0
    for k, (nota, ok) in enumerate(itens, 1):
        acertos += ok
        if k == n or itens[k][0] != nota:
            pontos.append({"limiar": list(nota), "cobertos": k, "cobertura": k / n, "erros": k - acertos,
                           "erro": (k - acertos) / k})
    return pontos


def escolher_limiar(pontos: list[dict], meta: float) -> dict | None:
    """Maior cobertura com erro <= meta (no dev)."""
    validos = [p for p in pontos if p["erro"] <= meta]
    return max(validos, key=lambda p: p["cobertura"]) if validos else None


def pesos_distribuicao_real(linhas: list[dict], dor: dict) -> dict[str, float]:
    """O teste foi estratificado (mínimo de 25 por órgão). Peso = fatia do órgão na base real / fatia no teste."""
    pop = {d["orgao"]: d["n_pedidos"] for d in dor["federal_concluida_por_orgao_top10"]}
    tot = sum(pop.values())
    n = len(linhas)
    cont = {}
    for l in linhas:
        cont[l["verdadeiro"]] = cont.get(l["verdadeiro"], 0) + 1
    return {o: (pop[o] / tot) / (cont[o] / n) for o in cont}


def aplicar(linhas: list[dict], estrategia: str, limiar: list, pesos: dict | None = None) -> dict:
    cob = [l for l in linhas if l[estrategia][1] >= tuple(limiar)]
    erros = sum(l[estrategia][0] != l["verdadeiro"] for l in cob)
    fila = [l for l in linhas if l[estrategia][1] < tuple(limiar)]
    reenc_cob = [l for l in cob if l["reencaminhado"]]
    return {
        "cobertos": len(cob), "cobertura": round(len(cob) / len(linhas), 4),
        "erros": erros, "erro": round(erros / len(cob), 4) if cob else None,
        "erro_ic95": [round(x, 4) for x in intervalo_wilson(erros, len(cob))] if cob else None,
        "fila_humana": len(fila),
        "acerto_que_a_maquina_teria_na_fila": round(sum(l[estrategia][0] == l["verdadeiro"] for l in fila) / len(fila), 4) if fila else None,
        "reencaminhados_cobertos": len(reenc_cob),
        "reencaminhados_cobertos_certos": sum(l[estrategia][0] == l["verdadeiro"] for l in reenc_cob),
    } | ({} if pesos is None else {
        "ponderado_distribuicao_real": {
            "cobertura": round(sum(pesos[l["verdadeiro"]] for l in cob) / sum(pesos[l["verdadeiro"]] for l in linhas), 4),
            "erro": round(sum(pesos[l["verdadeiro"]] for l in cob if l[estrategia][0] != l["verdadeiro"])
                          / sum(pesos[l["verdadeiro"]] for l in cob), 4) if cob else None}})


def _br(x: float, casas: int = 2) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def custo_do_erro(ponto_teste: dict, dor: dict, custo_llm_1000: float) -> dict:
    """Por 1.000 pedidos dos 10 órgãos, na distribuição real (cobertura e erro reponderados).

    A faixa de erros usa o intervalo de Wilson do erro no teste (sem ponderação). A comparação com hoje usa só os
    reencaminhados dos 10 órgãos: os "sem competência" não são reencaminhados e não têm o mesmo atraso.
    """
    atr = dor["federal_concluida_atraso"]
    atraso = atr["atraso_extra_mediana_dias"]
    top = dor["federal_concluida_top10"]
    reenc_hoje = top["pct_reencaminhados"] / 100
    pond = ponto_teste["ponderado_distribuicao_real"]
    auto = 1000 * pond["cobertura"]
    erros = auto * pond["erro"]
    lo, hi = ponto_teste["erro_ic95"]
    return {
        "premissas": [
            f"um encaminhamento errado volta a ser reencaminhado, como hoje, e atrasa {atraso:g} dias: é a diferença entre as "
            f"medianas de prazo dos reencaminhados ({atr['reencaminhados']['mediana_dias']:g} dias) e dos que chegaram certo "
            f"({atr['chegaram_certo']['mediana_dias']:g}), em dor.json",
            "na fila humana, a triagem é feita por servidor; o erro humano não foi medido (a revisão manual de 50 casos vai estimá-lo)",
            f"hoje, nos 10 órgãos, {_br(100 * reenc_hoje)}% dos pedidos são reencaminhados e outros {_br(top['pct_sem_competencia'])}% "
            "recebem 'não é de competência'; este sistema só escolhe entre os 10 órgãos e não trata o segundo grupo",
            "cobertura e erro reponderados pela distribuição real dos órgãos; a faixa de erros vem do intervalo de 95% do erro no teste",
        ],
        "por_1000_pedidos": {
            "encaminhados_automaticamente": round(auto),
            "para_a_fila_humana": round(1000 - auto),
            "erros_automaticos_esperados": round(erros, 1),
            "erros_automaticos_faixa_ic95": [round(auto * lo, 1), round(auto * hi, 1)],
            "dias_de_atraso_dos_erros_automaticos": round(erros * atraso, 1),
            "dias_de_atraso_faixa_ic95": [round(auto * lo * atraso, 1), round(auto * hi * atraso, 1)],
            "hoje_reencaminhados": round(1000 * reenc_hoje, 1),
            "hoje_dias_de_atraso": round(1000 * reenc_hoje * atraso, 1),
            "hoje_sem_competencia": round(10 * top["pct_sem_competencia"], 1),
            "custo_de_api_usd": round(custo_llm_1000, 2),
        },
    }


def main() -> None:
    dev, teste = carregar("dev"), carregar("test")
    m3 = json.loads((config.RESULTS / "marco3.json").read_text())
    custo_1000 = CUSTO_LLM_POR_1000 | {ap: m3["modelos"][ap]["test"]["custo_por_1000_usd"] for ap in ("haiku", "sonnet")}
    dor = json.loads((config.RESULTS / "dor.json").read_text())
    pesos = pesos_distribuicao_real(teste, dor)

    saida = {"metas_erro": METAS_ERRO, "meta_pre_registrada": META_PRE_REGISTRADA, "meta_recomendada": META_RECOMENDADA,
             "pesos_distribuicao_real": {o: round(w, 3) for o, w in sorted(pesos.items())}, "estrategias": {}}
    for est in ESTRATEGIAS:
        c_dev, c_teste = curva(dev, est), curva(teste, est)
        r = {"custo_por_1000_usd": custo_1000[est],
             "sem_abstencao_teste": {"erro": round(c_teste[-1]["erro"], 4),
                                 "erro_ponderado_distribuicao_real":
                                     aplicar(teste, est, c_teste[-1]["limiar"], pesos)["ponderado_distribuicao_real"]["erro"]},
             "curva_dev": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()} for p in c_dev],
             "curva_teste": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()} for p in c_teste],
             "por_meta": {}}
        for meta in METAS_ERRO:
            esc = escolher_limiar(c_dev, meta)
            if esc is None:
                r["por_meta"][str(meta)] = None
                continue
            r["por_meta"][str(meta)] = {"limiar": esc["limiar"], "dev": {"cobertura": round(esc["cobertura"], 4), "erro": round(esc["erro"], 4)},
                                        "teste": aplicar(teste, est, esc["limiar"], pesos)}
        saida["estrategias"][est] = r

    # Em cada meta, a estratégia é escolhida só pelo dev (maior cobertura; empate -> menor custo).
    def melhor_na_meta(meta):
        cands = [(e, r["por_meta"][str(meta)]) for e, r in saida["estrategias"].items() if r["por_meta"][str(meta)]]
        return max(cands, key=lambda x: (x[1]["dev"]["cobertura"], -custo_1000[x[0]])), cands

    (e_pre, p_pre), _ = melhor_na_meta(META_PRE_REGISTRADA)
    saida["regra_pre_registrada"] = {
        "criterio": f"maior cobertura no dev com erro <= {META_PRE_REGISTRADA:.0%}",
        "estrategia": e_pre, "limiar": p_pre["limiar"], "dev": p_pre["dev"], "teste": p_pre["teste"],
        "meta_cumprida_no_teste": p_pre["teste"]["erro"] <= META_PRE_REGISTRADA,
    }
    (melhor, ponto), cands = melhor_na_meta(META_RECOMENDADA)
    saida["recomendacao"] = {
        "criterio": f"maior cobertura no dev com erro <= {META_RECOMENDADA:.0%}",
        "aviso": (f"A meta combinada era {META_PRE_REGISTRADA:.0%}. O ponto escolhido no dev para ela "
                  f"({_br(100 * p_pre['dev']['erro'])}% de erro no dev, perto da meta) errou {_br(100 * p_pre['teste']['erro'], 1)}% "
                  f"no teste. A recomendação passou para a meta de {META_RECOMENDADA:.0%}, que também foi escolhida no dev, "
                  "mas a troca foi feita depois de ver o teste. Por isso o erro do teste no ponto recomendado não é uma "
                  "estimativa limpa; confirmar numa amostra nova."),
        "estrategia": melhor, "limiar": ponto["limiar"], "dev": ponto["dev"], "teste": ponto["teste"],
        "custo_do_erro": custo_do_erro(ponto["teste"], dor, custo_1000[melhor]),
    }
    # Para comparação: a melhor estratégia de custo zero na mesma meta.
    gratis = [(e, p) for e, p in cands if custo_1000[e] == 0]
    if gratis:
        e0, p0 = max(gratis, key=lambda x: x[1]["dev"]["cobertura"])
        saida["alternativa_sem_api"] = {"estrategia": e0, "limiar": p0["limiar"], "dev": p0["dev"], "teste": p0["teste"],
                                        "custo_do_erro": custo_do_erro(p0["teste"], dor, 0.0)}

    (config.RESULTS / "marco4.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(f"{'estratégia':10} {'meta':>5} | {'dev cob':>7} {'dev err':>7} | {'teste cob':>9} {'teste err':>9} {'IC95 erro':>15} | fila")
    for est, r in saida["estrategias"].items():
        print(f"{est:10} sem abstenção: erro no teste {r['sem_abstencao_teste']['erro']:.3f} | US$/1000 {r['custo_por_1000_usd']}")
        for meta, p in r["por_meta"].items():
            if p is None:
                print(f"{'':10} {meta:>5} | inatingível no dev")
                continue
            t = p["teste"]
            print(f"{'':10} {meta:>5} | {p['dev']['cobertura']:7.3f} {p['dev']['erro']:7.3f} | {t['cobertura']:9.3f} {t['erro']:9.3f} "
                  f"{str(t['erro_ic95']):>15} | {t['fila_humana']}")
    print(json.dumps({k: v for k, v in saida.items() if k in ("recomendacao", "alternativa_sem_api")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
