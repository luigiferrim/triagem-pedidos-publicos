"""Marco 3: análise lado a lado de 20 erros reais dos LLMs no teste.

Escolha (determinística, SEED): todos os erros do Sonnet no teste entram no sorteio primeiro; se forem
menos de 20, completa com erros só do Haiku. Para cada caso, mostra o que as 4 abordagens previram.

Saídas:
- data/erros_lado_a_lado.csv (FORA do git): texto mascarado do pedido, trecho e justificativa dos modelos.
  É o material para a leitura manual.
- results/erros_lado_a_lado.json (no git): só ids, rótulos, previsões e confiança, sem texto.
  A classificação manual de cada erro fica em results/erros_classificacao_manual.json (escrita à mão
  depois de ler o CSV) e é resumida aqui quando existir.
"""
import csv
import json
import random
from collections import Counter

from triagem import config, llm
from triagem.marco2 import DIR_PRED
from triagem.marco3 import _sistema
from triagem.preparar import ler_jsonl

N_ERROS = 20
ARQ_CSV = config.DATA / "erros_lado_a_lado.csv"
ARQ_JSON = config.RESULTS / "erros_lado_a_lado.json"
ARQ_CLASSIF = config.RESULTS / "erros_classificacao_manual.json"


def _pred(nome: str) -> dict[str, dict]:
    return {r["id"]: r for r in ler_jsonl(DIR_PRED / f"{nome}_test.jsonl")}


def selecionar(son: dict, hai: dict) -> list[str]:
    rng = random.Random(f"{config.SEED}-erros")
    err_son = sorted(i for i, r in son.items() if r["previsto"] != r["verdadeiro"])
    err_hai = sorted(i for i, r in hai.items() if r["previsto"] != r["verdadeiro"] and i not in err_son)
    escolhidos = rng.sample(err_son, min(N_ERROS, len(err_son)))
    if len(escolhidos) < N_ERROS:
        escolhidos += rng.sample(err_hai, min(N_ERROS - len(escolhidos), len(err_hai)))
    return sorted(escolhidos)


def main() -> None:
    son, hai, ml, reg = _pred("sonnet"), _pred("haiku"), _pred("ml"), _pred("regras")
    textos = {r["id"]: r for r in ler_jsonl(config.ARQ_TESTE)}
    sistema = _sistema()
    respostas = {}
    for apelido in ("sonnet", "haiku"):
        modelo = llm.MODELOS[apelido]
        cache = llm.Cache(modelo)
        for i, r in textos.items():
            rec = cache.get(llm.chave_cache(llm.corpo_requisicao(modelo, sistema, r["texto"]), i))
            dados, _ = llm.interpretar(rec["resposta"])
            respostas[(apelido, i)] = dados or {}

    ids = selecionar(son, hai)
    linhas = []
    for i in ids:
        linhas.append({
            "id": i, "verdadeiro": son[i]["verdadeiro"], "reencaminhado": son[i]["reencaminhado"],
            "cita_sigla": son[i]["cita_sigla"],
            "sonnet": son[i]["previsto"], "sonnet_confianca": son[i]["confianca"],
            "haiku": hai[i]["previsto"], "haiku_confianca": hai[i]["confianca"],
            "ml": ml[i]["previsto"], "ml_probabilidade": ml[i]["confianca"],
            "regras": reg[i]["previsto"],
        })

    with open(ARQ_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "verdadeiro", "sonnet", "conf_s", "haiku", "conf_h", "ml", "p_ml", "regras", "reenc",
                    "texto_mascarado", "sonnet_trecho", "sonnet_justificativa", "haiku_justificativa"])
        for ln in linhas:
            i = ln["id"]
            w.writerow([i, ln["verdadeiro"], ln["sonnet"], ln["sonnet_confianca"], ln["haiku"], ln["haiku_confianca"],
                        ln["ml"], ln["ml_probabilidade"], ln["regras"], ln["reencaminhado"], textos[i]["texto"],
                        respostas[("sonnet", i)].get("trecho"), respostas[("sonnet", i)].get("justificativa"),
                        respostas[("haiku", i)].get("justificativa")])

    n_err = {k: sum(p[i]["previsto"] != p[i]["verdadeiro"] for i in son) for k, p in
             (("sonnet", son), ("haiku", hai), ("ml", ml), ("regras", reg))}
    resumo = {
        "criterio": "sorteio (SEED) entre os erros do Sonnet no teste; completa com erros só do Haiku",
        "erros_no_teste": n_err,
        "erros_sonnet_que_haiku_tambem_erra": sum(hai[i]["previsto"] != hai[i]["verdadeiro"] for i in son
                                                  if son[i]["previsto"] != son[i]["verdadeiro"]),
        "erros_sonnet_que_ml_acerta": sum(ml[i]["previsto"] == ml[i]["verdadeiro"] for i in son
                                         if son[i]["previsto"] != son[i]["verdadeiro"]),
        "nos_20": {
            "haiku_acerta": sum(ln["haiku"] == ln["verdadeiro"] for ln in linhas),
            "ml_acerta": sum(ln["ml"] == ln["verdadeiro"] for ln in linhas),
            "regras_acertam": sum(ln["regras"] == ln["verdadeiro"] for ln in linhas),
            "sonnet_confianca": dict(Counter(ln["sonnet_confianca"] for ln in linhas)),
            "reencaminhados": sum(ln["reencaminhado"] for ln in linhas),
        },
        "casos": linhas,
    }
    if ARQ_CLASSIF.exists():
        classif = json.loads(ARQ_CLASSIF.read_text())["casos"]
        assert set(classif) == set(ids), "a classificação manual não cobre os mesmos 20 casos"
        resumo["categorias"] = dict(Counter(c["categoria"] for c in classif.values()).most_common())
        for ln in linhas:
            ln["categoria"] = classif[ln["id"]]["categoria"]
    ARQ_JSON.write_text(json.dumps(resumo, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in resumo.items() if k != "casos"}, ensure_ascii=False, indent=1))
    print(f"texto para leitura (fora do git): {ARQ_CSV}")


if __name__ == "__main__":
    main()
