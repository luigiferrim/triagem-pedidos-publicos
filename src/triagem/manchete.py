"""Números de manchete da regra recomendada (v1, limiar congelado do Marco 4), um só jeito de contar.

Fonte única para o site, o README, a DECISAO e o relatório: results/manchete.json.

Contagem direta nas amostras de 500 pedidos de cada mês, sem reponderação pela proporção real dos órgãos:
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


def gerar() -> dict:
    dor = json.loads((config.RESULTS / "dor.json").read_text())
    atraso = dor["federal_concluida_atraso"]["atraso_extra_mediana_dias"]
    jan_res = json.loads((config.RESULTS / "holdout_2026_resultado.json").read_text())
    jan = jan_res["regras_congeladas"]["sonnet_0.01"]["holdout"]
    fev_res = json.loads((config.RESULTS / "marco7_fev.json").read_text())
    fev = fev_res["v1"]["meta_1pct"]
    meses = {
        "janeiro de 2026": _mes("janeiro de 2026", jan_res["n"], jan["cobertos"], jan["erros"], jan_res["custo_sonnet_por_1000_usd"], atraso),
        "fevereiro de 2026": _mes("fevereiro de 2026", 500, fev["cobertos"], fev["erros"], fev_res["v1"]["custo_por_1000_usd"], atraso),
    }
    n = sum(m["pedidos"] for m in meses.values())
    acumulado = _mes("janeiro e fevereiro de 2026", n, sum(m["cobertos"] for m in meses.values()), sum(m["erros"] for m in meses.values()),
                     sum(m["custo_por_1000_usd"] * m["pedidos"] for m in meses.values()) / n, atraso)
    saida = {
        "regra": "v1: Sonnet encaminha sozinho com confiança alta, ou média com o modelo estatístico concordando (limiar congelado do Marco 4)",
        "metodo": "contagem direta nas amostras de 500 pedidos de cada mês, sem reponderação pela proporção real dos órgãos",
        "hoje_por_1000": round(10 * dor["federal_concluida_top10"]["pct_reencaminhados"]),
        "hoje_dias_de_atraso_por_1000": round(10 * dor["federal_concluida_top10"]["pct_reencaminhados"] * atraso),
        "meta": 0.01, "atraso_por_erro_dias": atraso,
        "acumulado": acumulado, "meses": meses,
        "frase": "A regra erra cerca de 1% a 2% na parte automática e oscila de mês a mês. A meta de 1% não se sustentou em fevereiro.",
    }
    ARQ.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


if __name__ == "__main__":
    gerar()
