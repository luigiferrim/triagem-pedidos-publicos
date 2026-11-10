"""Marco 2: baselines (regras e ML clássico). Escolhas só no dev; o teste só com --teste.

Abordagens:
- so_sigla:   só o nome ou a sigla do órgão citado no texto (sem palavras-chave). Mede o ganho "grátis" da sigla.
- regras:     nome/sigla + palavras-chave extraídas da amostra de treino.
- ml:         TF-IDF + regressão logística no treino completo (16.778 pedidos).
- ml_amostra: o mesmo modelo treinado só na amostra de 2.000 (referência para quem vê poucos exemplos).

Para cada abordagem e conjunto: acurácia, F1 macro, matriz de confusão e subgrupos
(cita a sigla literal / cita nome ou sigla / reencaminhados). Análise do ganho da sigla com bootstrap.

O teste só é calculado com --teste. Cada cálculo do teste é registrado em
results/registro_avaliacoes_teste.jsonl (data, abordagens, parâmetros escolhidos no dev, acurácia).
Saídas: results/marco2.json, results/regras_palavras_chave.json, results/predicoes/*.jsonl (sem texto).
"""
import argparse
import hashlib
import json
import random
import time
from datetime import datetime, timezone

from triagem import config, metricas, ml
from triagem.preparar import ler_jsonl
from triagem.regras import ALIASES, Regras, citacoes_de_nome, extrair_palavras_chave

GRADE_K = [10, 25, 50, 100, 200, 400, 800, 1600]
GRADE_PESO = [1, 3, 5, 10, 20, 40]
GRADE_C = [1, 3, 10, 30, 100, 300, 1000]
MAX_TERMOS_EXPLICACAO = 8
N_BOOTSTRAP = 2000
DIR_PRED = config.RESULTS / "predicoes"
REGISTRO_TESTE = config.RESULTS / "registro_avaliacoes_teste.jsonl"


def marcas_subgrupo(regs) -> dict[str, list[bool]]:
    literal = [metricas.cita_sigla(r["texto"], r["orgao_sigla"]) for r in regs]
    nome_ou_sigla = [citacoes_de_nome(r["texto"]).get(r["orgao_sigla"], 0) > 0 or lit
                     for r, lit in zip(regs, literal)]
    return {
        "cita_sigla_literal": literal,
        "nao_cita_sigla_literal": [not x for x in literal],
        "cita_nome_ou_sigla": nome_ou_sigla,
        "nao_cita_nome_ou_sigla": [not x for x in nome_ou_sigla],
        "reencaminhados": [r["reencaminhado"] for r in regs],
    }


def avaliar_completo(regs, pred, classes) -> dict:
    verdade = [r["orgao_sigla"] for r in regs]

    def sub(mask):
        v = [x for x, k in zip(verdade, mask) if k]
        p = [x for x, k in zip(pred, mask) if k]
        m = metricas.avaliar(v, p, classes)
        m.pop("por_classe", None)
        return m

    geral = metricas.avaliar(verdade, pred, classes)
    return {
        **geral,
        "matriz_confusao": {"classes": classes,
                            "linhas_verdadeiro_colunas_previsto": metricas.matriz_confusao(verdade, pred, classes)},
        "confusoes_principais": metricas.confusoes_principais(verdade, pred),
        "subgrupos": {nome: sub(mask) for nome, mask in marcas_subgrupo(regs).items()},
    }


def ganho_da_sigla(regs, acertos_regras, acertos_ml, marca) -> dict:
    """Diferença entre diferenças: (regras cita - regras não cita) - (ML cita - ML não cita).
    Mede quanto as regras dependem da sigla além do que o subgrupo já é mais fácil para qualquer um.
    O valor vale DENTRO do subgrupo 'cita'. Intervalo de 95% por bootstrap (seed fixa)."""
    def dd(idx):
        c = [i for i in idx if marca[i]]
        n = [i for i in idx if not marca[i]]
        if not c or not n:
            return None
        acc = lambda a, ii: sum(a[i] for i in ii) / len(ii)  # noqa: E731
        return (acc(acertos_regras, c) - acc(acertos_regras, n)) - (acc(acertos_ml, c) - acc(acertos_ml, n))

    todos = list(range(len(regs)))
    rng = random.Random(config.SEED)
    amostras = sorted(x for x in (dd([rng.randrange(len(regs)) for _ in todos]) for _ in range(N_BOOTSTRAP)) if x is not None)
    return {"pontos_percentuais": round(100 * dd(todos), 1),
            "ic95": [round(100 * amostras[int(0.025 * len(amostras))], 1), round(100 * amostras[int(0.975 * len(amostras))], 1)],
            "n_cita": sum(marca), "n_nao_cita": len(marca) - sum(marca)}


def salvar_predicoes(nome, conjunto, regs, pred, conf, expl):
    DIR_PRED.mkdir(parents=True, exist_ok=True)
    marcas = marcas_subgrupo(regs)
    with open(DIR_PRED / f"{nome}_{conjunto}.jsonl", "w", encoding="utf-8") as f:
        for i, (r, p, c, e) in enumerate(zip(regs, pred, conf, expl)):
            f.write(json.dumps({"id": r["id"], "verdadeiro": r["orgao_sigla"], "previsto": p,
                                "confianca": c, "explicacao": e,
                                "cita_sigla": marcas["cita_sigla_literal"][i],
                                "cita_nome_ou_sigla": marcas["cita_nome_ou_sigla"][i],
                                "reencaminhado": r["reencaminhado"]}, ensure_ascii=False, sort_keys=True) + "\n")


def prever_so_sigla(regs):
    pred, conf, expl = [], [], []
    for r in regs:
        cit = citacoes_de_nome(r["texto"])
        ordem = sorted(cit.items(), key=lambda kv: (-kv[1], kv[0]))
        if ordem[0][1] == 0 or ordem[0][1] == ordem[1][1]:
            pred.append(None)  # nenhum órgão citado, ou empate
            conf.append(0.0)
            expl.append([])
        else:
            pred.append(ordem[0][0])
            conf.append(float(ordem[0][1] - ordem[1][1]))
            expl.append([f"cita {ordem[0][0]} {ordem[0][1]}x"])
    return pred, conf, expl


def prever_regras(modelo: Regras, regs):
    pred, conf, expl = [], [], []
    for r in regs:
        p, margem, e = modelo.prever(r["texto"])
        pred.append(p)
        conf.append(margem)
        cit = [f"cita nome/sigla {e['nome_ou_sigla']}x"] if e.get("nome_ou_sigla") else []
        expl.append(cit + e.get("palavras", [])[:MAX_TERMOS_EXPLICACAO])
    return pred, conf, expl


def prever_ml(modelo, regs):
    textos = [r["texto"] for r in regs]
    pred, prob = ml.prever(modelo, textos)
    conf = [round(float(x), 4) for x in prob.max(axis=1)]
    expl = [ml.explicar(modelo, t, p) for t, p in zip(textos, pred)]
    probs = [{c: round(float(v), 4) for c, v in zip(modelo.classes_, linha)} for linha in prob]
    return pred, conf, expl, probs


def cronometrar(funcao, regs, repeticoes=1):
    ini = time.perf_counter()
    for _ in range(repeticoes):
        saida = funcao(regs)
    seg = (time.perf_counter() - ini) / repeticoes
    return saida, round(1000 * seg / len(regs), 4)  # segundos por 1.000 pedidos


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teste", action="store_true", help="calcula também o teste (registrado)")
    usar_teste = ap.parse_args().teste

    treino = ler_jsonl(config.ARQ_TREINO)
    amostra = ler_jsonl(config.ARQ_TREINO_AMOSTRA)
    dev = ler_jsonl(config.ARQ_DEV)
    conjuntos = [("dev", dev)] + ([("test", ler_jsonl(config.ARQ_TESTE))] if usar_teste else [])
    classes = sorted({r["orgao_sigla"] for r in treino})
    resultado = {"classes": classes, "teste_calculado": usar_teste, "abordagens": {}}
    acertos = {}

    # --- só nome/sigla (sem parâmetro)
    res = {}
    for nome_c, regs in conjuntos:
        (pred, conf, expl), t = cronometrar(prever_so_sigla, regs, repeticoes=3)
        res[nome_c] = avaliar_completo(regs, pred, classes) | {"segundos_por_1000": t}
        salvar_predicoes("so_sigla", nome_c, regs, pred, conf, expl)
    resultado["abordagens"]["so_sigla"] = res

    # --- regras: escolhe k e peso no dev
    todas = extrair_palavras_chave(amostra, k=max(GRADE_K))
    grade = []
    for k in GRADE_K:
        pk = {org: lst[:k] for org, lst in todas.items()}
        for peso in GRADE_PESO:
            pred, _, _ = prever_regras(Regras(pk, peso), dev)
            m = metricas.avaliar([r["orgao_sigla"] for r in dev], pred, classes)
            grade.append({"k": k, "peso_alias": peso, "acuracia_dev": m["acuracia"], "f1_macro_dev": m["f1_macro"]})
    melhor_r = max(grade, key=lambda g: (g["acuracia_dev"], g["f1_macro_dev"], -g["k"]))
    pk = {org: lst[: melhor_r["k"]] for org, lst in todas.items()}
    (config.RESULTS / "regras_palavras_chave.json").write_text(
        json.dumps({"k": melhor_r["k"], "peso_alias": melhor_r["peso_alias"], "aliases": ALIASES,
                    "palavras_chave": pk}, ensure_ascii=False, indent=1) + "\n")
    modelo_r = Regras(pk, melhor_r["peso_alias"])
    sem_sigla = Regras(pk, 0)  # análise: as mesmas regras sem o peso do nome/sigla
    res = {"escolha_no_dev": melhor_r, "grade_dev": grade}
    for nome_c, regs in conjuntos:
        (pred, conf, expl), t = cronometrar(lambda rr: prever_regras(modelo_r, rr), regs, repeticoes=3)
        res[nome_c] = avaliar_completo(regs, pred, classes) | {"segundos_por_1000": t}
        salvar_predicoes("regras", nome_c, regs, pred, conf, expl)
        acertos[("regras", nome_c)] = [p == r["orgao_sigla"] for p, r in zip(pred, regs)]
        pred0, _, _ = prever_regras(sem_sigla, regs)
        res[nome_c]["analise_peso_sigla_zero"] = avaliar_completo(regs, pred0, classes)
        res[nome_c]["analise_peso_sigla_zero"].pop("matriz_confusao")
    resultado["abordagens"]["regras"] = res

    # --- ML: escolhe C no dev, para treino completo e para a amostra
    escolhas_ml = {}
    for nome_ab, base in (("ml", treino), ("ml_amostra", amostra)):
        textos, rotulos = [r["texto"] for r in base], [r["orgao_sigla"] for r in base]
        grade, modelos = [], {}
        for c in GRADE_C:
            t0 = time.perf_counter()
            mdl = ml.treinar(textos, rotulos, c)
            seg_treino = time.perf_counter() - t0
            pred, _ = ml.prever(mdl, [r["texto"] for r in dev])
            m = metricas.avaliar([r["orgao_sigla"] for r in dev], pred, classes)
            grade.append({"C": c, "acuracia_dev": m["acuracia"], "f1_macro_dev": m["f1_macro"],
                          "segundos_treino": round(seg_treino, 1)})
            modelos[c] = mdl
        melhor = max(grade, key=lambda g: (g["acuracia_dev"], g["f1_macro_dev"], -g["C"]))
        escolhas_ml[nome_ab] = melhor["C"]
        mdl = modelos[melhor["C"]]
        res = {"escolha_no_dev": melhor, "grade_dev": grade, "n_treino": len(base)}
        for nome_c, regs in conjuntos:
            # O tempo mede só a classificação; a explicação é gerada à parte.
            _, t = cronometrar(lambda rr: ml.prever(mdl, [x["texto"] for x in rr]), regs, repeticoes=3)
            pred, conf, expl, probs = prever_ml(mdl, regs)
            res[nome_c] = avaliar_completo(regs, pred, classes) | {"segundos_por_1000": t}
            salvar_predicoes(nome_ab, nome_c, regs, pred, conf, expl)
            acertos[(nome_ab, nome_c)] = [p == r["orgao_sigla"] for p, r in zip(pred, regs)]
            if nome_ab == "ml":
                acertos[("ml_pred", nome_c)] = pred
            with open(DIR_PRED / f"{nome_ab}_{nome_c}_probabilidades.jsonl", "w", encoding="utf-8") as f:
                for r, p in zip(regs, probs):
                    f.write(json.dumps({"id": r["id"], "prob": p}, sort_keys=True) + "\n")
        resultado["abordagens"][nome_ab] = res

    # --- análises: ganho da sigla e concordância regras x ML
    resultado["analises"] = {}
    for nome_c, regs in conjuntos:
        marcas = marcas_subgrupo(regs)
        pred_r = [json.loads(x)["previsto"] for x in open(DIR_PRED / f"regras_{nome_c}.jsonl", encoding="utf-8")]
        pred_m = acertos[("ml_pred", nome_c)]
        concordam = [a == b for a, b in zip(pred_r, pred_m)]
        acerto_concordam = [a == r["orgao_sigla"] for a, b, r in zip(pred_r, pred_m, regs) if a == b]
        ar, am = acertos[("regras", nome_c)], acertos[("ml", nome_c)]
        resultado["analises"][nome_c] = {
            "ganho_sigla_sigla_literal": ganho_da_sigla(regs, ar, am, marcas["cita_sigla_literal"]),
            "ganho_sigla_nome_ou_sigla": ganho_da_sigla(regs, ar, am, marcas["cita_nome_ou_sigla"]),
            "regras_x_ml": {
                "concordam": sum(concordam),
                "acuracia_quando_concordam": round(sum(acerto_concordam) / len(acerto_concordam), 4),
                "so_ml_acerta": sum(m and not r for r, m in zip(ar, am)),
                "so_regras_acerta": sum(r and not m for r, m in zip(ar, am)),
                "ambos_erram": sum(not r and not m for r, m in zip(ar, am)),
            },
        }

    (config.RESULTS / "marco2.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n")

    if usar_teste:
        codigo = hashlib.sha256("".join(open(f, encoding="utf-8").read() for f in sorted(
            (config.RAIZ / "src" / "triagem").glob("*.py"))).encode()).hexdigest()[:12]
        with open(REGISTRO_TESTE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"), "marco": 2,
                "hash_codigo": codigo,
                "escolhas_no_dev": {"regras": {"k": melhor_r["k"], "peso": melhor_r["peso_alias"]}, **{f"{k}_C": v for k, v in escolhas_ml.items()}},
                "acuracia_teste": {ab: r["test"]["acuracia"] for ab, r in resultado["abordagens"].items()},
            }, ensure_ascii=False, sort_keys=True) + "\n")

    print(f"{'abordagem':12} {'conj':5} {'acur':>6} {'F1mac':>6} | {'sigla lit.':>12} {'nome/sigla':>12} {'reenc':>10} | s/1000")
    for ab, r in resultado["abordagens"].items():
        for c, _ in conjuntos:
            m = r[c]
            s = m["subgrupos"]
            print(f"{ab:12} {c:5} {m['acuracia']:6.3f} {m['f1_macro']:6.3f} | "
                  f"{s['cita_sigla_literal']['acuracia']:.3f}/{s['nao_cita_sigla_literal']['acuracia']:.3f} "
                  f"{s['cita_nome_ou_sigla']['acuracia']:.3f}/{s['nao_cita_nome_ou_sigla']['acuracia']:.3f} "
                  f"{s['reencaminhados']['acertos']:2d}/{s['reencaminhados']['n']:2d} | {m['segundos_por_1000']}")
    print(json.dumps(resultado["analises"], ensure_ascii=False))


if __name__ == "__main__":
    main()
