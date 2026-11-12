"""Números de manchete da regra recomendada (v1, limiar congelado do Marco 4), um só jeito de contar.

Fonte única para o site, o README, a DECISAO e o relatório: results/manchete.json.

Desde o Marco 10, a manchete é o monitoramento de março a outubro de 2026 (Marco 8, 1.200 pedidos, 150 por mês).
Janeiro e fevereiro de 2026 (holdouts dos Marcos 4 e 7) ficam como histórico, no mesmo arquivo.

Contagem direta nas amostras, sem reponderação pela proporção real dos órgãos:
- cobertura = encaminhados sem pessoa / pedidos;
- erro = erros entre os encaminhados sem pessoa (com intervalo de Wilson de 95%);
- por 1.000 pedidos: encaminhados, para uma pessoa e erros = contagem / pedidos x 1.000
  (a faixa dos erros usa o intervalo do erro x encaminhados).

Uso: python -m triagem.manchete
"""
import json

from triagem import config
from triagem.metricas import intervalo_wilson

ARQ = config.RESULTS / "manchete.json"
NOME_MES = {"mar": "março", "abr": "abril", "mai": "maio", "jun": "junho", "jul": "julho", "ago": "agosto",
            "set": "setembro", "out": "outubro"}


def _br(x: float, casas: int = 1) -> str:
    """Arredonda o meio para cima (1,85 -> 1,9), sem o erro do ponto flutuante."""
    from decimal import ROUND_HALF_UP, Decimal
    q = Decimal(str(round(x, 6))).quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
    return str(q).replace(".", ",")


def _mes(nome: str, n: int, cobertos: int, erros: int, custo_1000: float, atraso: float) -> dict:
    lo, hi = intervalo_wilson(erros, cobertos)
    return {
        "mes": nome, "pedidos": n, "cobertos": cobertos, "erros": erros,
        "cobertura": round(cobertos / n, 4), "erro": round(erros / cobertos, 4), "erro_ic95": [round(lo, 4), round(hi, 4)],
        "por_1000": {"sem_pessoa": round(1000 * cobertos / n), "para_pessoa": round(1000 * (n - cobertos) / n),
                     "erros": round(1000 * erros / n, 1),
                     "erros_faixa_ic95": [round(1000 * cobertos / n * lo, 1), round(1000 * cobertos / n * hi, 1)],
                     "dias_de_atraso": round(1000 * erros / n * atraso)},
        "custo_por_1000_usd": round(custo_1000, 2),
    }


def _jan_fev(atraso: float) -> dict:
    """Histórico: os dois holdouts de 500 pedidos (janeiro: Marco 4; fevereiro: Marco 7)."""
    jan_res = json.loads((config.RESULTS / "holdout_2026_resultado.json").read_text())
    jan = jan_res["regras_congeladas"]["sonnet_0.01"]["holdout"]
    fev_res = json.loads((config.RESULTS / "marco7_fev.json").read_text())
    fev = fev_res["v1"]["meta_1pct"]
    meses = {
        "janeiro de 2026": _mes("janeiro de 2026", jan_res["n"], jan["cobertos"], jan["erros"], jan_res["custo_sonnet_por_1000_usd"], atraso),
        "fevereiro de 2026": _mes("fevereiro de 2026", 500, fev["cobertos"], fev["erros"], fev_res["v1"]["custo_por_1000_usd"], atraso),
    }
    n = sum(m["pedidos"] for m in meses.values())
    acumulado = _mes("janeiro e fevereiro de 2026", n, sum(m["cobertos"] for m in meses.values()),
                     sum(m["erros"] for m in meses.values()),
                     sum(m["custo_por_1000_usd"] * m["pedidos"] for m in meses.values()) / n, atraso)
    return {"acumulado": acumulado, "meses": meses,
            "metodo": "contagem direta nas amostras de 500 pedidos de cada mês"}


def gerar() -> dict:
    dor = json.loads((config.RESULTS / "dor.json").read_text())
    atraso = dor["federal_concluida_atraso"]["atraso_extra_mediana_dias"]
    m8 = json.loads((config.RESULTS / "marco8_resultado.json").read_text())
    custo = m8["custo_por_1000_usd"]
    meses = {f"{NOME_MES[k]} de 2026": _mes(f"{NOME_MES[k]} de 2026", v["pedidos"], v["original"]["cobertos"],
                                            v["original"]["erros"], custo, atraso)
             for k, v in m8["por_mes"].items()}
    n = sum(m["pedidos"] for m in meses.values())
    acumulado = _mes("março a outubro de 2026", n, sum(m["cobertos"] for m in meses.values()),
                     sum(m["erros"] for m in meses.values()), custo, atraso)
    a8 = m8["acumulado_mar_out"]["original"]
    if (acumulado["cobertos"], acumulado["erros"]) != (a8["cobertos"], a8["erros"]):
        raise SystemExit("a soma dos meses não bate com o acumulado do Marco 8")
    sl = m8["sem_o_lote_repetido_do_inss"]["acumulado_mar_out"]["original"]
    corr = m8["acumulado_mar_out"]["corrigida"]
    hoje = round(10 * dor["federal_concluida_top10"]["pct_reencaminhados"])
    saida = {
        "regra": "v1: Sonnet encaminha sozinho com confiança alta, ou média com o modelo estatístico concordando (limiar congelado do Marco 4)",
        "metodo": "contagem direta na amostra de 150 pedidos por mês, de março a outubro de 2026 (Marco 8), sem reponderação",
        "hoje_por_1000": hoje,
        "hoje_dias_de_atraso_por_1000": round(10 * dor["federal_concluida_top10"]["pct_reencaminhados"] * atraso),
        "meta": 0.01, "meta_atingida": False, "atraso_por_erro_dias": atraso,
        "acumulado": acumulado, "meses": meses,
        "sem_o_lote_do_inss": {k: sl[k] for k in ("cobertos", "erros", "erro", "erro_ic95")} | {
            "nota": "158 pedidos quase iguais de um só solicitante; 5 caíram na amostra (README §4c)"},
        "faixa_do_erro": [sl["erro"], acumulado["erro"]],
        "regra_corrigida": {k: corr[k] for k in ("cobertura", "erro", "erro_ic95")} | {
            "nota": "limiar recalibrado só com jan+fev; não segurou 1%"},
        "historico_jan_fev": _jan_fev(atraso),
        "frase": (f"De março a outubro de 2026, a mesa encaminhou {_br(100 * acumulado['cobertura'])}% sem pessoa e errou de "
                  f"~{_br(100 * sl['erro'])}% (sem o lote do INSS) a ~{_br(100 * acumulado['erro'])}% na parte automática: "
                  f"~{round(acumulado['por_1000']['erros'])} erros por 1.000, contra {hoje} reencaminhados hoje. "
                  "A meta de 1% não foi atingida, e recalibrar o limiar não resolveu."),
    }
    ARQ.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in saida.items() if k not in ("meses", "historico_jan_fev")}, ensure_ascii=False, indent=1))
    return saida


if __name__ == "__main__":
    gerar()
