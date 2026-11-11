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


ARQ_INSS = config.RESULTS / "marco8_inss.json"
ARQ_INSS_EXEMPLOS = config.DATA / "marco8_inss_exemplos.jsonl"   # textos mascarados, fora do git
MESES_QUEDA, MESES_BASE = (6, 7, 10), (2, 3)


def investigar_inss() -> dict:
    """Pedidos ao INSS no volume todo: o que mudou nos meses de queda (jun, jul, out) em relação a fev e mar.
    Só descreve: volume, para onde vão as previsões erradas, palavras sobre-representadas, assunto da CGU."""
    import math
    from triagem import ml
    from triagem.holdout import modelo_ml
    from triagem.texto import termos
    pool, _, _ = _pool_2026()
    inss = pool[(pool["OrgaoDestinatario"].map(orgaos.sigla) == "INSS") & pool["_mes"].isin(MESES_QUEDA + MESES_BASE)].copy()
    inss["_mask"] = pii.mascarar(inss["_texto"].tolist(), Counter())
    mdl = modelo_ml()
    inss["_pred"] = ml.prever(mdl, inss["_mask"].tolist())[0]
    total_mes = pool.groupby("_mes").size()
    grupo = lambda ms: inss[inss["_mes"].isin(ms)]
    por_mes = {}
    for m in MESES_BASE + MESES_QUEDA:
        g = inss[inss["_mes"] == m]
        erradas = g[g["_pred"] != "INSS"]
        por_mes[NOME_MES[m]] = {
            "pedidos_inss": len(g), "fracao_do_volume": round(len(g) / total_mes[m], 4), "acerto_ml": round((g["_pred"] == "INSS").mean(), 4),
            "previsoes_erradas_foram_para": dict(Counter(erradas["_pred"]).most_common()),
            "tamanho_mediano_caracteres": int(g["_texto"].str.len().median()), "reencaminhados": round((g["FoiReencaminhado"] == "Sim").mean(), 4),
            "assunto_cgu_mais_comum": dict(Counter(g["AssuntoPedido"]).most_common(3)),
        }
    # palavras (uni e bigramas) muito mais frequentes nos meses de queda: log-odds de frequência por documento
    def df(textos):
        c = Counter()
        for t in textos:
            c.update(set(termos(t)))
        return c
    q, b = grupo(MESES_QUEDA), grupo(MESES_BASE)
    dq, db = df(q["_mask"]), df(b["_mask"])
    nq, nb = len(q), len(b)
    sobre = []
    for w, k in dq.items():
        if k < 8 or "nome" in w:
            continue
        pq, pb = (k + 0.5) / (nq + 1), (db.get(w, 0) + 0.5) / (nb + 1)
        sobre.append((math.log(pq / pb), w, k, db.get(w, 0)))
    sobre.sort(reverse=True)
    top = [{"termo": w, "pedidos_queda": k, "frac_queda": round(k / nq, 3), "pedidos_base": kb, "frac_base": round(kb / nb, 3)} for _, w, k, kb in sobre[:15]]
    assunto = lambda g: {a: round(n / len(g), 3) for a, n in Counter(g["AssuntoPedido"]).most_common(5)}
    # pedidos que trazem pelo menos 4 dos 5 termos mais sobre-representados: é o mesmo modelo de texto?
    import difflib
    import random
    top5 = [t["termo"] for t in top[:5]]
    q = q.assign(_termos=[set(termos(t)) for t in q["_mask"]])
    rep = q[[sum(w in ts for w in top5) >= 4 for ts in q["_termos"]]]
    textos_rep = rep["_texto"].tolist()
    rng = random.Random(config.SEED)
    pares = [rng.sample(range(len(textos_rep)), 2) for _ in range(40)] if len(textos_rep) > 1 else []
    sims = [difflib.SequenceMatcher(None, textos_rep[i], textos_rep[j]).ratio() for i, j in pares]
    sem = q.drop(rep.index)
    modelo_repetido = {
        "criterio": "pedidos dos meses de queda com pelo menos 4 dos 5 termos mais sobre-representados",
        "pedidos": len(rep), "por_mes": {NOME_MES[m]: int((rep["_mes"] == m).sum()) for m in MESES_QUEDA},
        "solicitantes_distintos": int(rep["IdSolicitante"].nunique()), "sem_solicitante_identificado": int((rep["IdSolicitante"] == "0").sum()),
        "semelhanca_media_entre_pares": round(sum(sims) / len(sims), 3) if sims else None, "semelhanca_minima": round(min(sims), 3) if sims else None,
        "acerto_ml_nesses": round((rep["_pred"] == "INSS").mean(), 4) if len(rep) else None,
        "previsoes_nesses": dict(Counter(rep["_pred"]).most_common(3)),
        "acerto_ml_inss_na_queda_sem_eles": {NOME_MES[m]: {"n": int((sem["_mes"] == m).sum()), "acerto": round((sem[sem["_mes"] == m]["_pred"] == "INSS").mean(), 4)}
                                              for m in MESES_QUEDA if (sem["_mes"] == m).any()},
        "dado_pessoal_nao_mascarado": "os textos trazem a matrícula SIAPE de cada servidor citado; a máscara do projeto cobre nome, CPF, e-mail, telefone e documentos rotulados, não matrícula",
    }
    saida = {"descricao": "pedidos ao INSS (volume todo, rótulo confiável); meses de queda = jun, jul, out; base = fev, mar",
             "por_mes": por_mes, "termos_mais_frequentes_na_queda": top,
             "assunto_cgu": {"base": assunto(b), "queda": assunto(q)},
             "modelo_de_texto_repetido": modelo_repetido,
             "acerto_ml": {"base": round((b["_pred"] == "INSS").mean(), 4), "queda": round((q["_pred"] == "INSS").mean(), 4)},
             "nota": "o assunto da CGU é preenchido pelo SIC depois de receber o pedido; serve só para descrever, não entra em nenhum modelo"}
    ARQ_INSS.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    # exemplos curtos mascarados com o termo mais sobre-representado (fora do git, para leitura)
    t0 = top[0]["termo"] if top else ""
    linhas = q[["IdPedido", "_mes", "_pred", "_mask"]].to_dict("records")
    ex = [x for x in linhas if t0 and t0 in " ".join(termos(x["_mask"])) and len(x["_mask"]) <= 350][:5]
    with open(ARQ_INSS_EXEMPLOS, "w", encoding="utf-8") as f:
        for x in ex:
            f.write(json.dumps({"id": str(x["IdPedido"]), "mes": int(x["_mes"]), "previsto_ml": x["_pred"], "texto": x["_mask"]}, ensure_ascii=False) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


ARQ_ML_SEM_LOTE = config.RESULTS / "marco8_ml_sem_lote.json"


def _no_lote(textos_mascarados: list[str], top5: list[str]) -> list[bool]:
    """Critério do lote repetido: pelo menos 4 dos 5 termos mais sobre-representados na queda do INSS."""
    from triagem.texto import termos
    return [sum(w in set(termos(t)) for w in top5) >= 4 for t in textos_mascarados]


def ml_sem_lote() -> dict:
    """Deriva do modelo estatístico no volume todo, com e sem o lote repetido do INSS (mesmo critério, aplicado
    a TODOS os meses de fevereiro a outubro, não só aos meses de queda)."""
    from triagem import ml
    from triagem.holdout import modelo_ml
    top5 = [t["termo"] for t in json.loads(ARQ_INSS.read_text())["termos_mais_frequentes_na_queda"][:5]]
    pool, _, _ = _pool_2026()
    pool = pool[pool["_mes"].between(2, 10)].copy()
    pool["_rot"] = [orgaos.sigla(o) for o in pool["OrgaoDestinatario"]]
    pool["_mask"] = pii.mascarar(pool["_texto"].tolist(), Counter())
    pool["_pred"] = ml.prever(modelo_ml(), pool["_mask"].tolist())[0]
    pool["_ok"] = pool["_pred"] == pool["_rot"]
    pool["_lote"] = False
    inss = pool["_rot"] == "INSS"
    pool.loc[inss, "_lote"] = _no_lote(pool.loc[inss, "_mask"].tolist(), top5)
    acerto = lambda g: {"n": len(g), "acerto": round(g["_ok"].mean(), 4) if len(g) else None}
    meses = {}
    for m in range(2, 11):
        g = pool[pool["_mes"] == m]
        lote = g[g["_lote"]]
        meses[NOME_MES[m]] = {
            "pedidos_do_lote": len(lote), "solicitantes_no_lote": int(lote["IdSolicitante"].nunique()),
            "com_o_lote": {"todos": acerto(g), "inss": acerto(g[g["_rot"] == "INSS"])},
            "sem_o_lote": {"todos": acerto(g[~g["_lote"]]), "inss": acerto(g[(g["_rot"] == "INSS") & ~g["_lote"]])},
        }
    saida = {"descricao": "acerto do modelo estatístico no volume todo, com e sem o lote repetido do INSS",
             "criterio_do_lote": "rótulo INSS e pelo menos 4 destes 5 termos no texto mascarado: " + ", ".join(top5),
             "pedidos_do_lote": int(pool["_lote"].sum()), "solicitantes_distintos_no_lote": int(pool.loc[pool["_lote"], "IdSolicitante"].nunique()),
             "previsoes_no_lote": dict(Counter(pool.loc[pool["_lote"], "_pred"]).most_common(3)),
             "meses": meses}
    ARQ_ML_SEM_LOTE.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
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


TETO_FASE_USD = 12.0


def conferir_congelado() -> dict:
    from triagem.marco3 import _sistema, hash_prompt
    reg = json.loads(ARQ_CONGELADO.read_text())
    if sha256(ARQ_AMOSTRA) != reg["sha256_amostra"]:
        raise SystemExit("PARADO: a amostra mudou depois do congelamento")
    if hash_prompt(_sistema()) != reg["sha256_prompt_v1"]:
        raise SystemExit("PARADO: o prompt da v1 mudou")
    regra_ = json.loads(ARQ_REGRA.read_text())
    if [regra_["regra_original"]["limiar"], regra_["regra_corrigida"]["limiar"]] != [reg["regra_original"], reg["regra_corrigida"]]:
        raise SystemExit("PARADO: as regras mudaram")
    return reg


def rodar(paralelo: int = 6) -> None:
    """Uma rodada do Sonnet v1 nos 1.200 pedidos da amostra (chamada normal, mesmo prompt de janeiro)."""
    import anthropic
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from triagem.marco3 import _sistema
    from triagem.marco7 import gasto_fase
    conferir_congelado()
    regs = ler_jsonl(ARQ_AMOSTRA)
    s1 = _sistema()
    modelo = llm.MODELOS["sonnet"]
    cache = llm.Cache(modelo)
    pend = [r for r in regs if cache.get(llm.chave_cache(llm.corpo_requisicao(modelo, s1, r["texto"]), r["id"])) is None]
    previsto = gasto_fase() + 0.0036 * len(pend)
    print(f"marco 8: {len(pend)} a chamar; gasto da fase previsto ao fim: US$ {previsto:.2f} (teto {TETO_FASE_USD})")
    if previsto > TETO_FASE_USD:
        raise SystemExit("PARADO: passaria do teto da fase")
    cli = anthropic.Anthropic(max_retries=2)
    if pend:
        llm.chamar(cli, llm.corpo_requisicao(modelo, s1, pend[0]["texto"]), pend[0]["id"], cache)
        with ThreadPoolExecutor(max_workers=paralelo) as ex:
            fut = [ex.submit(llm.chamar, cli, llm.corpo_requisicao(modelo, s1, r["texto"]), r["id"], cache) for r in pend[1:]]
            for k, f in enumerate(as_completed(fut), 2):
                f.result()
                if k % 200 == 0:
                    g = gasto_fase()
                    print(f"  {k}/{len(pend)}, gasto da fase US$ {g:.3f}")
                    if g > TETO_FASE_USD:
                        for x in fut:
                            x.cancel()
                        raise SystemExit("PARADO: gasto da fase passou do teto")
    print(f"fim. gasto da fase: US$ {gasto_fase():.3f}")


ARQ_RESULTADO = config.RESULTS / "marco8_resultado.json"


def avaliar() -> dict:
    """As duas regras congeladas nas MESMAS respostas, mês a mês e no acumulado; os dois alertas; deriva por órgão."""
    from triagem import ml
    from triagem.holdout import modelo_ml
    from triagem.marco2 import DIR_PRED
    from triagem.marco3 import _sistema
    from triagem.marco4 import NIVEL, aplicar
    from triagem.metricas import intervalo_wilson
    reg = conferir_congelado()
    alertas = json.loads((config.RESULTS / "marco8_alertas.json").read_text())["alertas"]
    regs = ler_jsonl(ARQ_AMOSTRA)
    mdl = modelo_ml()
    pred_ml, prob = ml.prever(mdl, [r["texto"] for r in regs])
    classes = list(mdl.classes_)
    s1 = _sistema()
    modelo = llm.MODELOS["sonnet"]
    cache = llm.Cache(modelo)
    linhas, pub, custo = [], [], 0.0
    for r, pm, pr in zip(regs, pred_ml, prob):
        rec = cache.get(llm.chave_cache(llm.corpo_requisicao(modelo, s1, r["texto"]), r["id"]))
        if rec is None:
            raise SystemExit(f"falta a resposta do Sonnet para {r['id']}")
        custo += rec["custo_usd"]
        d, _ = llm.interpretar(rec["resposta"])
        prev, conf = (d["orgao"], d["confianca"]) if d else (None, None)
        pmap = dict(zip(classes, map(float, pr)))
        nota = (NIVEL[conf], int(prev == pm), pmap.get(prev, 0.0))
        linhas.append({"id": r["id"], "mes": r["mes"], "verdadeiro": r["orgao_sigla"], "reencaminhado": r["reencaminhado"],
                       "original": (prev, nota), "corrigida": (prev, nota)})
        pub.append({"id": r["id"], "mes": r["mes"], "verdadeiro": r["orgao_sigla"], "previsto": prev, "confianca": conf, "ml": pm,
                    "p_ml_do_previsto": round(pmap.get(prev, 0.0), 4), "reencaminhado": r["reencaminhado"]})
    lims = {"original": reg["regra_original"], "corrigida": reg["regra_corrigida"]}
    # lote repetido do INSS (mesmo critério da investigação: >= 4 dos 5 termos mais sobre-representados)
    top5 = [t["termo"] for t in json.loads(ARQ_INSS.read_text())["termos_mais_frequentes_na_queda"][:5]]
    inss_ = [r for r in regs if r["orgao_sigla"] == "INSS"]
    lote = {r["id"] for r, b in zip(inss_, _no_lote([r["texto"] for r in inss_], top5)) if b}

    def res(ls, nome):
        a = aplicar(ls, nome, lims[nome])
        return {k: a[k] for k in ("cobertos", "cobertura", "erros", "erro", "erro_ic95")}

    def calcular(linhas):
        meses = sorted({l["mes"] for l in linhas})
        por_mes = {}
        for m in meses:
            ls = [l for l in linhas if l["mes"] == m]
            ac = sum(l["original"][0] == l["verdadeiro"] for l in ls)
            lo, hi = intervalo_wilson(ac, len(ls))
            por_mes[NOME_MES[m]] = {"pedidos": len(ls), "acuracia_sonnet": round(ac / len(ls), 4), "acuracia_ic95": [round(lo, 4), round(hi, 4)],
                                    "original": res(ls, "original"), "corrigida": res(ls, "corrigida")}
        acumulado = {"original": res(linhas, "original"), "corrigida": res(linhas, "corrigida"),
                     "acuracia_sonnet": round(sum(l["original"][0] == l["verdadeiro"] for l in linhas) / len(linhas), 4)}
        # alertas, para cada regra, mês a mês (a partir do 2º mês da série)
        nomes = [NOME_MES[m] for m in meses]
        al = {}
        for regra_ in ("original", "corrigida"):
            al[regra_] = {}
            for i, m in enumerate(nomes):
                if i == 0:
                    al[regra_][m] = {"original": None, "robusto": None}
                    continue
                a0, a1 = por_mes[nomes[i - 1]][regra_], por_mes[m][regra_]
                simples = a0["erro"] > alertas["original"]["limite_erro"] and a1["erro"] > alertas["original"]["limite_erro"]
                erros, cob = a0["erros"] + a1["erros"], a0["cobertos"] + a1["cobertos"]
                lo, hi = intervalo_wilson(erros, cob)
                al[regra_][m] = {"original": bool(simples),
                                 "robusto": bool(lo > alertas["robusto"]["limite_inferior_acima_de"]),
                                 "erro_2_meses": round(erros / cob, 4), "ic95_2_meses": [round(lo, 4), round(hi, 4)]}
        return por_mes, acumulado, al, meses, nomes

    por_mes, acumulado, al, meses, nomes = calcular(linhas)
    sem_lote = calcular([l for l in linhas if l["id"] not in lote])
    # deriva por órgão: acerto do Sonnet na amostra (n pequeno) e do modelo estatístico no volume todo
    orgs = sorted({l["verdadeiro"] for l in linhas})

    def deriva(ls):
        return {o: {NOME_MES[m]: {"n": n_, "acerto": round(a_ / n_, 4) if n_ else None}
                    for m in meses
                    for n_, a_ in [(sum(1 for l in ls if l["mes"] == m and l["verdadeiro"] == o),
                                    sum(1 for l in ls if l["mes"] == m and l["verdadeiro"] == o and l["original"][0] == o))]}
                for o in orgs}
    deriva_sonnet = deriva(linhas)
    ml_mensal = json.loads(ARQ_ML.read_text())["meses"] if ARQ_ML.exists() else {}
    ml_sl = json.loads(ARQ_ML_SEM_LOTE.read_text())["meses"] if ARQ_ML_SEM_LOTE.exists() else {}
    erros_lote = {r: sum(1 for l in linhas if l["id"] in lote and aplicar([l], r, lims[r])["cobertos"] and l[r][0] != l["verdadeiro"])
                  for r in ("original", "corrigida")}
    saida = {
        "amostra": {"meses": nomes, "n_por_mes": reg["n_por_mes"], "n": len(linhas), "sha256": reg["sha256_amostra"]},
        "regras": lims, "acumulado_mar_out": acumulado, "por_mes": por_mes, "alertas": al,
        "sem_o_lote_repetido_do_inss": {"pedidos_do_lote_na_amostra": sorted(lote, key=int), "por_mes": sem_lote[0],
                                        "previsoes_do_sonnet_no_lote": dict(Counter(l["original"][0] for l in linhas if l["id"] in lote)),
                                        "erros_automaticos_do_lote": erros_lote,
                                        "acumulado_mar_out": sem_lote[1], "alertas": sem_lote[2],
                                        "deriva_inss_sonnet_na_amostra": deriva([l for l in linhas if l["id"] not in lote])["INSS"],
                                        "deriva_modelo_estatistico_no_volume_todo": ml_sl},
        "nota_lote": ("o lote de pedidos quase idênticos ao INSS (um só solicitante, jun-jul) pede dados funcionais de "
                      "ex-servidores identificados pela matrícula SIAPE; o SIAPE é gerido pelo MGI, então MGI é uma "
                      "resposta defensável: é um rótulo discutível em massa, não um erro claro do modelo"),
        "regra_corrigida_se_sustentou": {"meta": META, "erro_acumulado": acumulado["corrigida"]["erro"], "ic95": acumulado["corrigida"]["erro_ic95"],
                                         "dentro_da_meta_no_ponto": acumulado["corrigida"]["erro"] <= META,
                                         "dentro_da_meta_com_folga": acumulado["corrigida"]["erro_ic95"][1] <= META},
        "deriva_por_orgao": {"sonnet_na_amostra": deriva_sonnet,
                             "modelo_estatistico_no_volume_todo": {m: v["por_orgao"] for m, v in ml_mensal.items()}},
        "custo_usd": round(custo, 4), "custo_por_1000_usd": round(1000 * custo / len(linhas), 4),
        "privacidade": {"textos_enviados_com_matricula_visivel": sum(bool(pii.PADRAO_MATRICULA[1].search(r["texto"])) for r in regs),
                        "nota": "a amostra congelada foi mantida; a matrícula é dado já publicado pela CGU; nenhum número está no repositório"},
    }
    ARQ_RESULTADO.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    with open(DIR_PRED / "v1_monitor_2026.jsonl", "w", encoding="utf-8") as f:
        for x in pub:
            f.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n")
    br = lambda x: f"{100 * x:.2f}".replace(".", ",")
    for m, v in por_mes.items():
        print(f"{m}: acur {br(v['acuracia_sonnet'])}% | original cob {br(v['original']['cobertura'])} erro {br(v['original']['erro'])} "
              f"({v['original']['erros']}/{v['original']['cobertos']}) | corrigida cob {br(v['corrigida']['cobertura'])} erro {br(v['corrigida']['erro'])} "
              f"({v['corrigida']['erros']}/{v['corrigida']['cobertos']}) | alertas orig {al['original'][m]} | corr {al['corrigida'][m]}")
    print("acumulado", json.dumps(acumulado, ensure_ascii=False))
    print("custo", saida["custo_usd"])
    return saida


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["regra", "amostra", "ml", "congelar", "estimar", "inss", "ml-sem-lote", "rodar", "avaliar"])
    a = ap.parse_args()
    {"regra": regra, "amostra": amostra, "ml": ml_mensal, "congelar": congelar, "estimar": estimar, "inss": investigar_inss,
     "ml-sem-lote": ml_sem_lote, "rodar": rodar, "avaliar": avaliar}[a.cmd]()


if __name__ == "__main__":
    main()
