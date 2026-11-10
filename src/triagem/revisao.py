"""Revisão manual às cegas do Luigi (50 pedidos) ao lado das 4 abordagens.

Lê data/revisao_manual_50.csv (orgao_luigi, certeza_1a3) e o gabarito data/revisao_manual_50_gabarito.csv.

Normalização de orgao_luigi: sigla antes de " – "; BCB -> BACEN; MJSP -> PF (a PF é vinculada ao MJSP, e a
ferramenta de revisão listava MJSP no lugar de PF). "Outro / nenhum dos 10" conta como discordância.

Os 50 pedidos saíram da amostra de treino (train_amostra). Para comparar sem vazamento:
- regras: palavras-chave extraídas de novo da amostra de treino SEM os 50 (k e peso escolhidos no dev, Marco 2);
- ML: treinado de novo no treino completo SEM os 50 (C escolhido no dev, Marco 2);
- Haiku e Sonnet: mesmo prompt do Marco 3 (nenhum dos 50 está entre os exemplos do prompt; há um teste disso).
  Com --chamar-api, chama a API para o que faltar no cache (teto TETO_USD); sem a flag, só lê o cache.

Saída: results/revisao_manual.json (ids, rótulos e previsões; sem texto).
"""
import argparse
import json
from collections import Counter

import pandas as pd

from triagem import config, llm, ml
from triagem.preparar import ler_jsonl
from triagem.regras import Regras, extrair_palavras_chave

TETO_USD = 0.30
MAPA = {"BCB": "BACEN", "MJSP": "PF"}
CERTEZAS = ["3", "2", "1"]


def normalizar(rotulo: str) -> str:
    r = (rotulo or "").strip()
    if not r:
        return ""
    if r.lower().startswith("outro"):
        return "OUTRO"
    sigla = r.split(" – ")[0].split(" - ")[0].strip().upper()
    return MAPA.get(sigla, sigla)


def ler_revisao() -> pd.DataFrame:
    rev = pd.read_csv(config.ARQ_REVISAO, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    gab = pd.read_csv(config.DATA / "revisao_manual_50_gabarito.csv", dtype=str, encoding="utf-8-sig")
    df = rev.merge(gab, on="id")
    df["humano"] = df["orgao_luigi"].map(normalizar)
    df["certeza"] = df["certeza_1a3"].str.strip()
    return df


def prever_maquinas(ids: list[str], chamar_api: bool) -> dict[str, dict[str, dict]]:
    """{abordagem: {id: {"previsto": ..., "confianca": ...}}}"""
    idset = set(ids)
    amostra = ler_jsonl(config.ARQ_TREINO_AMOSTRA)
    por_id = {r["id"]: r for r in amostra}
    alvo = [por_id[i] for i in ids]
    m2 = json.loads((config.RESULTS / "marco2.json").read_text())
    saida = {}

    esc_r = m2["abordagens"]["regras"]["escolha_no_dev"]
    sem50 = [r for r in amostra if r["id"] not in idset]
    todas = extrair_palavras_chave(sem50, k=esc_r["k"])
    regras = Regras({o: lst[: esc_r["k"]] for o, lst in todas.items()}, esc_r["peso_alias"])
    saida["regras"] = {r["id"]: {"previsto": regras.prever(r["texto"])[0], "confianca": None} for r in alvo}

    c = m2["abordagens"]["ml"]["escolha_no_dev"]["C"]
    treino = [r for r in ler_jsonl(config.ARQ_TREINO) if r["id"] not in idset]
    mdl = ml.treinar([r["texto"] for r in treino], [r["orgao_sigla"] for r in treino], c)
    pred, prob = ml.prever(mdl, [r["texto"] for r in alvo])
    saida["ml"] = {r["id"]: {"previsto": p, "confianca": round(float(max(pr)), 4)} for r, p, pr in zip(alvo, pred, prob)}

    sistema = llm.prompt_sistema(llm.escolher_exemplos(amostra))
    cliente = None
    if chamar_api:
        import anthropic
        cliente = anthropic.Anthropic(max_retries=2)
    for apelido, modelo in llm.MODELOS.items():
        cache = llm.Cache(modelo)
        res = {}
        for r in alvo:
            corpo = llm.corpo_requisicao(modelo, sistema, r["texto"])
            rec = cache.get(llm.chave_cache(corpo, r["id"]))
            if rec is None and cliente is not None:
                gasto = sum(x.get("custo_usd", 0.0) for x in cache.dados.values() if x["id"] in idset)
                gasto += sum(x.get("custo_usd", 0.0) for m in llm.MODELOS.values() if m != modelo
                             for x in llm.Cache(m).dados.values() if x["id"] in idset)
                if gasto > TETO_USD:
                    raise SystemExit(f"PARADO: gasto nos 50 da revisão passou de US$ {TETO_USD}")
                rec = llm.chamar(cliente, corpo, r["id"], cache)
            if rec is None:
                res[r["id"]] = {"previsto": None, "confianca": None, "falta_no_cache": True}
                continue
            dados, _ = llm.interpretar(rec["resposta"])
            res[r["id"]] = {"previsto": dados["orgao"] if dados else None, "confianca": dados["confianca"] if dados else None}
        saida[apelido] = res
    return saida


def custo_llm(ids: set[str]) -> float:
    return round(sum(x.get("custo_usd", 0.0) for m in llm.MODELOS.values() for x in llm.Cache(m).dados.values()
                     if x["id"] in ids), 4)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chamar-api", action="store_true")
    a = ap.parse_args()
    df = ler_revisao()
    if (df["humano"] == "").all():
        saida = {"status": "pendente", "preenchidos": 0, "total": len(df)}
        (config.RESULTS / "revisao_manual.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
        print(saida)
        return

    ids = df["id"].tolist()
    maq = prever_maquinas(ids, a.chamar_api)
    df["acerto_humano"] = df["humano"] == df["orgao_base"]

    def taxa(mask):
        sub = df[mask]
        return {"acertos": int(sub["acerto_humano"].sum()), "n": int(len(sub))}

    por_cert = {c: taxa(df["certeza"] == c) for c in CERTEZAS}
    abord = {}
    for nome, preds in maq.items():
        ok = [preds[i]["previsto"] == b for i, b in zip(df["id"], df["orgao_base"])]
        abord[nome] = {"acertos": int(sum(ok)), "n": len(ok),
                       "acertos_por_certeza_humana": {c: int(sum(o for o, cc in zip(ok, df["certeza"]) if cc == c)) for c in CERTEZAS},
                       "faltam_no_cache": sum(bool(p.get("falta_no_cache")) for p in preds.values())}
    for apelido in llm.MODELOS:
        pc = {}
        for conf in llm.CONFIANCAS:
            sel = [(maq[apelido][i]["previsto"] == b) for i, b in zip(df["id"], df["orgao_base"]) if maq[apelido][i]["confianca"] == conf]
            if sel:
                pc[conf] = {"acertos": int(sum(sel)), "n": len(sel)}
        abord[apelido]["acertos_por_confianca_do_modelo"] = pc

    casos = []
    for r in df.itertuples(index=False):
        casos.append({"id": r.id, "base": r.orgao_base, "humano": r.humano, "certeza_humana": r.certeza,
                      **{n: maq[n][r.id]["previsto"] for n in maq},
                      "confianca_sonnet": maq["sonnet"][r.id]["confianca"], "confianca_haiku": maq["haiku"][r.id]["confianca"],
                      "prob_ml": maq["ml"][r.id]["confianca"]})
    disc = df[~df["acerto_humano"]]
    saida = {
        "status": "completo" if (df["humano"] != "").all() else "parcial",
        "origem_dos_50": "train_amostra (5 por órgão, sorteio com SEED); regras e ML retreinados sem eles",
        "normalizacao": {"sigla_antes_de": " – ", "mapa": MAPA, "outro": "conta como discordância"},
        "limitacao": ("a ferramenta de revisão listava MJSP e não PF; casos com gabarito PF podem ter ficado como "
                      "'Outro' por falta de opção. O resultado humano é um limite inferior."),
        "humano": {"acertos": int(df["acerto_humano"].sum()), "n": len(df), "por_certeza": por_cert,
                   "marcou_outro": int((df["humano"] == "OUTRO").sum()),
                   "marcou_outro_com_gabarito_pf": df.loc[(df["humano"] == "OUTRO") & (df["orgao_base"] == "PF"), "id"].tolist()},
        "abordagens": abord,
        "pares_discordancia_humano": [{"base": b, "humano": h, "n": n} for (b, h), n in
                                      Counter(zip(disc["orgao_base"], disc["humano"])).most_common()],
        "custo_llm_usd": custo_llm(set(ids)),
        "casos": casos,
    }
    (config.RESULTS / "revisao_manual.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    h = saida["humano"]
    print(f"humano: {h['acertos']}/{h['n']} | " + " | ".join(f"certeza {c}: {v['acertos']}/{v['n']}" for c, v in h["por_certeza"].items()))
    for n, v in abord.items():
        print(f"{n:7} {v['acertos']}/{v['n']} | por certeza humana {v['acertos_por_certeza_humana']} | "
              f"por confiança do modelo {v.get('acertos_por_confianca_do_modelo', '-')} | faltam {v['faltam_no_cache']}")
    print("custo LLM nos 50: US$", saida["custo_llm_usd"])


if __name__ == "__main__":
    main()
