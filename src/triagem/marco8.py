"""Marco 8: monitoramento ao longo de 2026.

1. Regra corrigida, escolhida SÓ com janeiro e fevereiro de 2026 (1.000 pedidos): mesma ordem de notas da política
   v1, maior cobertura com erro <= 1% no acumulado. A regra original (Marco 4) segue congelada ao lado.
2. Amostra do Sonnet: 150 pedidos por mês, de março a outubro de 2026, com o mesmo recorte e a mesma máscara,
   estratificada por órgão (mínimo de MIN_POR_ORGAO), no máximo 5 por solicitante, sem textos iguais a pedidos
   anteriores (2025 e meses anteriores de 2026).
3. Modelo estatístico (ML local, custo zero) no volume todo dos 10 órgãos, de fevereiro a outubro.
4. Congelamento (antes de qualquer chamada): as duas regras, os meses, o tamanho da amostra, o hash da amostra,
   o hash do prompt da v1 e a regra de alerta.
5. Depois (com aprovação): o Sonnet v1 roda uma vez na amostra; as duas regras são aplicadas às MESMAS respostas.

Uso:
  python -m triagem.marco8 regra | amostra | ml | congelar | estimar
"""
import argparse
import json
from collections import Counter

import numpy as np
import pandas as pd

from triagem import config, dados, llm, orgaos, pii
from triagem.preparar import _normalizar, _registro, _texto, amostrar, escrever_jsonl, ler_jsonl, sha256

MESES = list(range(3, 11))           # março a outubro de 2026
N_POR_MES = 150
MIN_POR_ORGAO = 5
META = 0.01
ALERTA = {"limite_erro": 0.02, "meses_seguidos": 2, "acao": "recalibrar o limiar"}
NOME_MES = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun", 7: "jul", 8: "ago", 9: "set", 10: "out"}
ARQ_AMOSTRA = config.DATA / "monitor_2026.jsonl"
ARQ_REGRA = config.RESULTS / "marco8_regra.json"
ARQ_AMOSTRA_RES = config.RESULTS / "marco8_amostra.json"
ARQ_ML = config.RESULTS / "marco8_ml_mensal.json"
ARQ_CONGELADO = config.RESULTS / "marco8_congelado.json"
ARQ_ESTIMATIVA = config.RESULTS / "estimativa_custo_marco8.json"


def _linhas_jan_fev() -> tuple[list[dict], list[dict]]:
    from triagem.marco2 import DIR_PRED
    from triagem.marco4 import NIVEL
    jan = [{"id": p["id"], "verdadeiro": p["verdadeiro"], "reencaminhado": p["reencaminhado"],
            "v1": (p["sonnet"], (NIVEL[p["confianca"]], int(p["sonnet"] == p["ml"]), p["p_ml_do_sonnet"]))}
           for p in ler_jsonl(DIR_PRED / "holdout_2026.jsonl")]
    fev = [{"id": p["id"], "verdadeiro": p["verdadeiro"], "reencaminhado": p["reencaminhado"],
            "v1": (p["previsto"], (NIVEL[p["confianca"]], int(p["previsto"] == p["ml"]), p["p_ml_do_previsto"]))}
           for p in ler_jsonl(DIR_PRED / "v1_holdout_2026_02.jsonl")]
    return jan, fev


def regra() -> dict:
    """Escolhe a regra corrigida só com jan+fev (1.000 pedidos)."""
    from triagem.marco4 import aplicar, curva, escolher_limiar
    jan, fev = _linhas_jan_fev()
    tudo = jan + fev
    m4 = json.loads((config.RESULTS / "marco4.json").read_text())
    original = m4["estrategias"]["sonnet"]["por_meta"]["0.01"]["limiar"]
    esc = escolher_limiar(curva(tudo, "v1"), META)
    corrigida = list(esc["limiar"])
    resumo = lambda lim: {"acumulado": aplicar(tudo, "v1", lim), "janeiro": aplicar(jan, "v1", lim), "fevereiro": aplicar(fev, "v1", lim)}
    saida = {
        "criterio": "maior cobertura com erro <= 1% em janeiro e fevereiro de 2026 somados (1.000 pedidos), na ordem de notas da v1",
        "dados_usados": ["results/predicoes/holdout_2026.jsonl", "results/predicoes/v1_holdout_2026_02.jsonl"],
        "regra_original": {"limiar": original, "em_palavras": "confiança alta; ou média com o modelo estatístico concordando e segurança >= 0,8035",
                           "origem": "escolhida no dev de 2025 (Marco 4)"} | resumo(original),
        "regra_corrigida": {"limiar": corrigida,
                            "em_palavras": f"confiança alta; ou média com o modelo estatístico concordando e segurança >= {corrigida[2]:.4f}".replace(".", ","),
                            "origem": "escolhida em janeiro+fevereiro de 2026; os números abaixo são dentro da amostra em que foi escolhida"} | resumo(corrigida),
    }
    ARQ_REGRA.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: (v["limiar"] if isinstance(v, dict) and "limiar" in v else v) for k, v in saida.items()}, ensure_ascii=False, indent=1))
    return saida


def _pool_2026() -> tuple[pd.DataFrame, set[str]]:
    """Pedidos de 2026 dos 10 órgãos com rótulo confiável, sem texto repetido entre órgãos; e os textos de 2025."""
    from triagem.holdout import _csv
    df = dados.ler_csv(_csv())
    lista = orgaos.top_orgaos(dados.ler_filtrada())
    base = df[(df["Esfera"] == "Federal") & df["OrgaoDestinatario"].isin(lista)].copy()
    pool = base[orgaos.rotulo_confiavel(base)].copy()
    pool["_texto"] = _texto(pool)
    pool["_norm"] = _normalizar(pool["_texto"])
    pool = pool[pool.groupby("_norm")["OrgaoDestinatario"].transform("nunique") == 1]
    pool["_mes"] = pd.to_datetime(pool["DataRegistro"], format="%d/%m/%Y").dt.month
    todos = df.copy()
    todos["_mes"] = pd.to_datetime(todos["DataRegistro"], format="%d/%m/%Y").dt.month
    todos["_norm"] = _normalizar(_texto(todos))
    return pool, todos, set(_normalizar(_texto(dados.ler_filtrada())))


def amostra() -> dict:
    if ARQ_AMOSTRA.exists():
        raise SystemExit(f"{ARQ_AMOSTRA} já existe (amostra congelada)")
    pool, todos, norm_2025 = _pool_2026()
    ids_anteriores = {r["id"] for a in (config.ARQ_TREINO, config.ARQ_DEV, config.ARQ_TESTE, config.DATA / "holdout_2026.jsonl",
                                        config.DATA / "holdout_2026_02.jsonl") for r in ler_jsonl(a)}
    partes, passos = [], {}
    for m in MESES:
        anteriores = norm_2025 | set(todos.loc[todos["_mes"] < m, "_norm"])
        mes = pool[pool["_mes"] == m].sort_values("IdPedido", key=lambda s: s.astype(int)).drop_duplicates("_norm", keep="first")
        mes = mes[~mes["_norm"].isin(anteriores) & ~mes["IdPedido"].isin(ids_anteriores)]
        rng = np.random.default_rng([config.SEED, sum(f"monitor_2026_{m:02d}".encode())])
        a = amostrar(mes, N_POR_MES, MIN_POR_ORGAO, rng)
        passos[NOME_MES[m]] = {"pool": len(mes), "amostra": len(a)}
        partes.append(a.assign(mes_ref=m))
    am = pd.concat(partes)
    contagem = Counter()
    mascarados = pii.mascarar(am["_texto"].tolist(), contagem)
    regs = [_registro(r, t) | {"mes": int(r.mes_ref)} for r, t in zip(am.itertuples(), mascarados)]
    escrever_jsonl(ARQ_AMOSTRA, regs)
    saida = {"meses": [NOME_MES[m] for m in MESES], "n_por_mes": N_POR_MES, "min_por_orgao": MIN_POR_ORGAO,
             "passos": passos, "n": len(regs), "por_mes_e_orgao": {NOME_MES[m]: dict(sorted(Counter(r["orgao_sigla"] for r in regs if r["mes"] == m).items())) for m in MESES},
             "reencaminhados": sum(r["reencaminhado"] for r in regs), "pii_mascarada": dict(contagem), "sha256": sha256(ARQ_AMOSTRA)}
    ARQ_AMOSTRA_RES.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in saida.items() if k != "por_mes_e_orgao"}, ensure_ascii=False, indent=1))
    return saida


def ml_mensal() -> dict:
    """Modelo estatístico no volume todo, mês a mês (fevereiro a outubro), com a mesma máscara do treino."""
    from triagem import ml
    from triagem.holdout import modelo_ml
    from triagem.metricas import intervalo_wilson
    pool, _, _ = _pool_2026()
    mdl = modelo_ml()
    saida = {"descricao": "acerto do modelo estatístico (treinado em jan-ago/2025) em todos os pedidos dos 10 órgãos, por mês de registro",
             "meses": {}}
    for m in range(2, 11):
        mes = pool[pool["_mes"] == m]
        textos = pii.mascarar(mes["_texto"].tolist(), Counter())
        pred, _ = ml.prever(mdl, textos)
        rot = [orgaos.sigla(o) for o in mes["OrgaoDestinatario"]]
        ok = [p == r for p, r in zip(pred, rot)]
        lo, hi = intervalo_wilson(sum(ok), len(ok))
        por_org = {}
        for o in sorted(set(rot)):
            idx = [i for i, r in enumerate(rot) if r == o]
            por_org[o] = {"n": len(idx), "acerto": round(sum(ok[i] for i in idx) / len(idx), 4)}
        saida["meses"][NOME_MES[m]] = {"n": len(ok), "acerto": round(sum(ok) / len(ok), 4), "ic95": [round(lo, 4), round(hi, 4)],
                                       "por_orgao": por_org, "distribuicao": {o: round(v["n"] / len(ok), 4) for o, v in por_org.items()}}
        print(NOME_MES[m], len(ok), round(sum(ok) / len(ok), 4))
    ARQ_ML.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    return saida


def congelar() -> dict:
    from datetime import datetime, timezone
    from triagem.marco3 import _sistema, hash_prompt
    am = json.loads(ARQ_AMOSTRA_RES.read_text())
    if sha256(ARQ_AMOSTRA) != am["sha256"]:
        raise SystemExit("a amostra mudou")
    cache = llm.Cache(llm.MODELOS["sonnet"])
    ids = {r["id"] for r in ler_jsonl(ARQ_AMOSTRA)}
    if any(r["id"] in ids for r in cache.dados.values()):
        raise SystemExit("já existe chamada em pedido da amostra: não dá para congelar depois")
    rg = json.loads(ARQ_REGRA.read_text())
    saida = {
        "congelado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo": llm.MODELOS["sonnet"], "sha256_prompt_v1": hash_prompt(_sistema()),
        "regra_original": rg["regra_original"]["limiar"], "regra_corrigida": rg["regra_corrigida"]["limiar"],
        "meses": am["meses"], "n_por_mes": am["n_por_mes"], "n_total": am["n"], "sha256_amostra": am["sha256"],
        "alerta": ALERTA, "regra": "uma rodada do Sonnet v1 na amostra; as duas regras são aplicadas às mesmas respostas, sem chamadas extras",
    }
    ARQ_CONGELADO.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


def estimar() -> dict:
    """Custo esperado a partir do custo real da v1 em janeiro e fevereiro, ajustado pelo tamanho dos textos."""
    m = json.loads((config.RESULTS / "manchete.json").read_text())
    regs = ler_jsonl(ARQ_AMOSTRA)
    ref = ler_jsonl(config.DATA / "holdout_2026.jsonl") + ler_jsonl(config.DATA / "holdout_2026_02.jsonl")
    razao = (sum(len(r["texto"]) for r in regs) / len(regs)) / (sum(len(r["texto"]) for r in ref) / len(ref))
    por_pedido = m["acumulado"]["custo_por_1000_usd"] / 1000
    custo = round(len(regs) * por_pedido * max(1.0, razao), 2)
    from triagem.marco7 import gasto_fase
    g = gasto_fase()
    saida = {"pedidos": len(regs), "custo_v1_por_pedido_jan_fev_usd": round(por_pedido, 5),
             "razao_tamanho_texto_amostra_sobre_jan_fev": round(razao, 3), "estimativa_usd": custo,
             "gasto_da_fase_ate_agora_usd": round(g, 2), "gasto_previsto_ao_fim_usd": round(g + custo, 2), "teto_da_fase_usd": 12.0}
    ARQ_ESTIMATIVA.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["regra", "amostra", "ml", "congelar", "estimar"])
    a = ap.parse_args()
    {"regra": regra, "amostra": amostra, "ml": ml_mensal, "congelar": congelar, "estimar": estimar}[a.cmd]()


if __name__ == "__main__":
    main()
