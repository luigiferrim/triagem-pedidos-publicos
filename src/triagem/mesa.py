"""Mesa de Triagem (Marco 6): dados do site estático em mesa/.

Uso:
  python -m triagem.mesa dados        # mesa/dados/holdout.json: só números dos 500 do holdout (sem texto)
  python -m triagem.mesa selecionar   # escolhe os 30 exemplos e gera data/revisao_exemplos_mesa.csv (fora do git)
  python -m triagem.mesa substituir   # troca os marcados 'n' por outros do mesmo tipo e órgão (CSV só com eles)
  python -m triagem.mesa publicar     # depois da revisão do Luigi: mesa/dados/exemplos.json + hashes aprovados

A política é a v1 recomendada (Marco 4): o Sonnet encaminha sozinho se a confiança for "alta", ou "média" com o
ML concordando e probabilidade >= limiar. O limiar vem de results/marco4.json (escolhido no dev), nunca daqui.
"""
import argparse
import csv
import difflib
import hashlib
import json
import random
import re

from triagem import config, llm
from triagem.marco3 import _sistema
from triagem.preparar import ler_jsonl

DIR_MESA = config.RAIZ / "mesa"
DIR_DADOS = DIR_MESA / "dados"
ARQ_HOLDOUT = config.DATA / "holdout_2026.jsonl"
ARQ_PRED = config.RESULTS / "predicoes" / "holdout_2026.jsonl"
ARQ_CSV = config.DATA / "revisao_exemplos_mesa.csv"
ARQ_CSV_SUBST = config.DATA / "revisao_exemplos_mesa_substitutos.csv"
ARQ_RASCUNHO = config.DATA / "mesa_exemplos_rascunho.jsonl"
ARQ_APROVADOS = config.RESULTS / "mesa_exemplos_aprovados.json"
ARQ_EXEMPLOS = DIR_DADOS / "exemplos.json"
MAX_CARACTERES = 1200
SEMELHANCA_MAX = 0.6
# Pré-triagem de conteúdo (antes da revisão do Luigi): detalhe pessoal sensível mesmo com o nome mascarado.
EXCLUIDOS_POR_CONTEUDO = {"10286887": "relata antecedente criminal e situação pessoal do solicitante"}
# Removidos depois da aprovação, por decisão do Luigi, sem substituto.
REMOVIDOS_SEM_SUBSTITUTO = {"10265265": "um dos 3 erros da IA; relato longo e sensível (10/11/2026)"}
# Exemplos em que o próprio rótulo da base é discutível (pedido do Luigi na revisão externa de 11/11/2026).
NOTAS_ROTULO = {"10226343": "Rótulo discutível: quem decide a isenção de IR para doença grave é a Receita Federal (MF); a base diz MS."}
NIVEL = {"alta": 2, "media": 1, "baixa": 0, None: -1}


def limiares() -> dict:
    m4 = json.loads((config.RESULTS / "marco4.json").read_text())
    return {m: m4["estrategias"]["sonnet"]["por_meta"][m]["limiar"] for m in ("0.01", "0.02")}


def _br(x: float, casas: int = 2) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def seguranca(p: float, limiar: list) -> str:
    """Quão seguro o modelo estatístico está do órgão: alta a partir do limiar da política, média a partir de 0,5."""
    return "alta" if p >= limiar[2] else "média" if p >= 0.5 else "baixa"


def politica(confianca: str | None, sonnet: str | None, ml: str, p_ml_do_sonnet: float, limiar: list) -> tuple[bool, str]:
    """Decisão da política v1 e o motivo em uma linha, sem jargão (o modelo estatístico é a 2ª opinião)."""
    nota = (NIVEL[confianca], int(sonnet == ml), p_ml_do_sonnet)
    automatico = sonnet is not None and nota >= tuple(limiar)
    if confianca == "alta":
        return automatico, "confiança alta"
    if automatico:
        return True, "confiança média, mas o modelo estatístico concordou com segurança alta"
    if confianca == "media" and sonnet == ml:
        return False, f"incerto, foi para pessoa (confiança média; o modelo estatístico concordou, mas com segurança {seguranca(p_ml_do_sonnet, limiar)})"
    if confianca == "media":
        return False, f"incerto, foi para pessoa (confiança média; o modelo estatístico sugeriu {ml})"
    return False, "incerto, foi para pessoa (confiança baixa)"


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _periodo_texto(periodo: str) -> str:
    """'2026-01 a 2026-01' -> 'janeiro de 2026'."""
    a, b = [x.strip() for x in periodo.split(" a ")]
    ma, mb = int(a[5:7]), int(b[5:7])
    return f"{MESES[ma - 1]} de {a[:4]}" if a == b else f"{MESES[ma - 1]} a {MESES[mb - 1]} de {b[:4]}"


def _fevereiro() -> dict | None:
    """A mesma regra em fevereiro de 2026 (Marco 7), quando já avaliada."""
    arq = config.RESULTS / "marco7_fev.json"
    if not arq.exists():
        return None
    m = json.loads(arq.read_text())["v1"]["meta_1pct"]
    return {k: m[k] for k in ("cobertura", "erro", "erro_ic95", "erros", "cobertos")} | {"n": 500}


def dados() -> dict:
    preds = ler_jsonl(ARQ_PRED)
    res = json.loads((config.RESULTS / "holdout_2026_resultado.json").read_text())
    dor = json.loads((config.RESULTS / "dor.json").read_text())
    lim = limiares()
    saida = {
        "dor": {"pct_errado": dor["federal_concluida"]["pct_chegaram_ao_orgao_errado"],
                "atraso_dias": dor["federal_concluida_atraso"]["atraso_extra_mediana_dias"],
                "pct_reencaminhados_10_orgaos": dor["federal_concluida_top10"]["pct_reencaminhados"]},
        "fonte": "holdout de 2026 (regra congelada); sem texto de pedido",
        "periodo_texto": _periodo_texto(json.loads((config.RESULTS / "holdout_2026.json").read_text())["periodo"]),
        "orgaos": sorted({p["verdadeiro"] for p in preds}),
        "limiares": {"1%": lim["0.01"], "2%": lim["0.02"]},
        "custo_por_1000_usd": res["custo_sonnet_por_1000_usd"],
        "resultado_1pct": {k: res["regras_congeladas"]["sonnet_0.01"]["holdout"][k] for k in ("cobertura", "erro", "erro_ic95", "erros", "cobertos")},
        "resultado_2pct": {k: res["regras_congeladas"]["sonnet_0.02"]["holdout"][k] for k in ("cobertura", "erro", "erro_ic95", "erros", "cobertos")},
        "fevereiro_1pct": _fevereiro(),
        "pedidos": [{"id": p["id"], "rotulo": p["verdadeiro"], "sonnet": p["sonnet"], "confianca": p["confianca"],
                     "ml": p["ml"], "p_ml": p["p_ml_do_sonnet"], "reencaminhado": p["reencaminhado"]} for p in preds],
    }
    DIR_DADOS.mkdir(parents=True, exist_ok=True)
    (DIR_DADOS / "holdout.json").write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"mesa/dados/holdout.json: {len(saida['pedidos'])} pedidos, só números")
    # O relatório do projeto (já versionado e sem texto de pedido) vai junto com o site.
    import shutil
    shutil.copyfile(config.RAIZ / "report.html", DIR_MESA / "relatorio.html")
    return saida


def _respostas_sonnet(regs: list[dict]) -> dict[str, dict]:
    modelo = llm.MODELOS["sonnet"]
    sistema = _sistema()
    cache = llm.Cache(modelo)
    out = {}
    for r in regs:
        rec = cache.get(llm.chave_cache(llm.corpo_requisicao(modelo, sistema, r["texto"]), r["id"]))
        dados_, _ = llm.interpretar(rec["resposta"])
        out[r["id"]] = dados_ or {}
    return out


def selecionar() -> list[dict]:
    """30 exemplos: os 3 erros automáticos, 6 da fila humana (3 certos, 3 errados), 21 automáticos certos.

    Os 3 erros entram todos, sem o filtro `elegivel` (tamanho, detector, trecho literal): são os únicos erros da
    parte automática no holdout. Os outros 27 passam pelo filtro."""
    from triagem import pii_detector
    regs = {r["id"]: r for r in ler_jsonl(ARQ_HOLDOUT)}
    preds = {p["id"]: p for p in ler_jsonl(ARQ_PRED)}
    lim = limiares()["0.01"]
    det = json.loads((config.RESULTS / "pii_detector_offline.json").read_text())
    marcados = set(det["ids_marcados"])
    prenomes = {pii_detector._sem_acento(x.strip().lower()) for x in open(config.DATA / "ref" / "prenomes_ibge.txt", encoding="utf-8") if x.strip()}

    for p in preds.values():
        p["automatico"], p["motivo"] = politica(p["confianca"], p["sonnet"], p["ml"], p["p_ml_do_sonnet"], lim)
        p["certo"] = p["sonnet"] == p["verdadeiro"]

    def elegivel(i):
        return len(regs[i]["texto"]) <= MAX_CARACTERES and i not in marcados and preds[i]["trecho_literal"]

    rng = random.Random(f"{config.SEED}-mesa")
    ids = sorted(preds, key=int)
    erros_auto = [i for i in ids if preds[i]["automatico"] and not preds[i]["certo"]]
    humano_certo = [i for i in ids if not preds[i]["automatico"] and preds[i]["certo"] and elegivel(i)]
    humano_errado = [i for i in ids if not preds[i]["automatico"] and not preds[i]["certo"] and elegivel(i)]
    escolhidos = erros_auto + rng.sample(humano_certo, 3) + rng.sample(humano_errado, 3)
    auto_certo = [i for i in ids if preds[i]["automatico"] and preds[i]["certo"] and elegivel(i)]
    por_orgao = {}
    for i in auto_certo:
        por_orgao.setdefault(preds[i]["verdadeiro"], []).append(i)
    def parecido(i):  # evita dois textos quase iguais (mesmo modelo de pedido)
        return any(difflib.SequenceMatcher(None, regs[i]["texto"], regs[j]["texto"]).ratio() > SEMELHANCA_MAX
                   for j in escolhidos)

    def pegar(candidatos, n):
        candidatos = list(candidatos)
        rng.shuffle(candidatos)
        pegos = 0
        for i in candidatos:
            if pegos == n:
                break
            if i not in escolhidos and not parecido(i):
                escolhidos.append(i)
                pegos += 1

    for o in sorted(por_orgao):
        pegar(por_orgao[o], 2)
    pegar(auto_certo, 30 - len(escolhidos))
    assert len(set(escolhidos)) == 30

    resp = _respostas_sonnet([regs[i] for i in escolhidos])
    linhas = []
    for i in sorted(escolhidos, key=int):
        p, t = preds[i], regs[i]["texto"]
        alertas = [m.group(0)[:50] for m in pii_detector.PADRAO_IBGE.finditer(t)
                   if pii_detector._sem_acento(m.group(1).lower()) in prenomes]
        alertas += [m.group(0)[:50] for m in pii_detector.PADRAO_PISTA.finditer(t)]
        alertas += [m.group(0)[:40] for m in pii_detector.PADRAO_SOBRENOME.finditer(t)]
        alertas += [f"{tipo}: {v}" for tipo, v in __import__("triagem.pii", fromlist=["x"]).encontrar_pii_regex(t)]
        linhas.append({
            "id": i, "tipo": ("erro da IA (automático)" if p["automatico"] and not p["certo"]
                              else "automático" if p["automatico"] else "para pessoa"),
            "status": "encaminhado automaticamente" if p["automatico"] else "aguardando servidor",
            "rotulo": p["verdadeiro"], "sonnet": p["sonnet"], "confianca": p["confianca"], "ml": p["ml"],
            "p_ml": p["p_ml_do_sonnet"], "motivo": p["motivo"], "reencaminhado": p["reencaminhado"],
            "texto": t, "trecho": resp[i].get("trecho", ""), "justificativa": resp[i].get("justificativa", ""),
            "alertas_detector": alertas,
        })
    with open(ARQ_RASCUNHO, "w", encoding="utf-8") as f:
        for ln in linhas:
            f.write(json.dumps(ln, ensure_ascii=False) + "\n")
    with open(ARQ_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "tipo", "status", "rotulo_base", "sugestao_sonnet", "confianca", "ml", "motivo",
                    "texto_mascarado", "trecho_citado", "justificativa_ia", "alertas_do_detector", "aprovado_s_n", "observacao"])
        for ln in linhas:
            w.writerow([ln["id"], ln["tipo"], ln["status"], ln["rotulo"], ln["sonnet"], ln["confianca"], ln["ml"], ln["motivo"],
                        ln["texto"], ln["trecho"], ln["justificativa"], " | ".join(ln["alertas_detector"]), "", ""])
    print(f"{ARQ_CSV}: {len(linhas)} exemplos")
    print(dict(__import__("collections").Counter(ln["tipo"] for ln in linhas)))
    return linhas


def _ler_revisoes() -> list[dict]:
    revs = []
    for arq in (ARQ_CSV, ARQ_CSV_SUBST):
        if arq.exists():
            with open(arq, encoding="utf-8-sig") as f:
                revs += list(csv.DictReader(f))
    return revs


def substituir() -> None:
    """Para cada exemplo marcado 'n', escolhe um substituto do mesmo tipo e órgão, pelo mesmo critério."""
    from triagem import pii_detector
    regs = {r["id"]: r for r in ler_jsonl(ARQ_HOLDOUT)}
    preds = {p["id"]: p for p in ler_jsonl(ARQ_PRED)}
    lim = limiares()["0.01"]
    marcados = set(json.loads((config.RESULTS / "pii_detector_offline.json").read_text())["ids_marcados"])
    rascunho = {ln["id"]: ln for ln in ler_jsonl(ARQ_RASCUNHO)}
    revs = _ler_revisoes()
    rejeitados = [r for r in revs if r["aprovado_s_n"].strip().lower() == "n" and r["id"] not in REMOVIDOS_SEM_SUBSTITUTO]
    ja_revistos = {r["id"] for r in revs}
    aprovados = [r["id"] for r in revs if r["aprovado_s_n"].strip().lower() in ("s", "sim")]
    rng = random.Random(f"{config.SEED}-mesa-substitutos")
    novos = []
    for rej in rejeitados:
        if any(n["substitui"] == rej["id"] for n in novos):
            continue
        alvo = rascunho[rej["id"]]
        cands = []
        for i, p in preds.items():
            auto, motivo = politica(p["confianca"], p["sonnet"], p["ml"], p["p_ml_do_sonnet"], lim)
            certo = p["sonnet"] == p["verdadeiro"]
            tipo = "erro da IA (automático)" if auto and not certo else "automático" if auto else "para pessoa"
            if (tipo == alvo["tipo"] and p["verdadeiro"] == alvo["rotulo"] and i not in ja_revistos and i not in marcados
                    and i not in EXCLUIDOS_POR_CONTEUDO
                    and len(regs[i]["texto"]) <= MAX_CARACTERES and p["trecho_literal"]):
                cands.append((i, p, motivo))
        rng.shuffle(cands)
        base = [regs[j]["texto"] for j in aprovados + [n["id"] for n in novos]]
        for i, p, motivo in cands:
            if all(difflib.SequenceMatcher(None, regs[i]["texto"], t).ratio() <= SEMELHANCA_MAX for t in base):
                resp = _respostas_sonnet([regs[i]])[i]
                novos.append({"id": i, "substitui": rej["id"], "tipo": alvo["tipo"],
                              "status": "encaminhado automaticamente" if alvo["tipo"] != "para pessoa" else "aguardando servidor",
                              "rotulo": p["verdadeiro"], "sonnet": p["sonnet"], "confianca": p["confianca"], "ml": p["ml"],
                              "p_ml": p["p_ml_do_sonnet"], "motivo": motivo, "reencaminhado": p["reencaminhado"],
                              "texto": regs[i]["texto"], "trecho": resp.get("trecho", ""), "justificativa": resp.get("justificativa", ""),
                              "alertas_detector": [m.group(0)[:50] for m in pii_detector.PADRAO_PISTA.finditer(regs[i]["texto"])]})
                break
    with open(ARQ_RASCUNHO, "a", encoding="utf-8") as f:
        for n in novos:
            f.write(json.dumps({k: v for k, v in n.items() if k != "substitui"}, ensure_ascii=False) + "\n")
    with open(ARQ_CSV_SUBST, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "substitui", "tipo", "status", "rotulo_base", "sugestao_sonnet", "confianca", "ml", "motivo",
                    "texto_mascarado", "trecho_citado", "justificativa_ia", "alertas_do_detector", "aprovado_s_n", "observacao"])
        for n in novos:
            w.writerow([n["id"], n["substitui"], n["tipo"], n["status"], n["rotulo"], n["sonnet"], n["confianca"], n["ml"],
                        n["motivo"], n["texto"], n["trecho"], n["justificativa"], " | ".join(n["alertas_detector"]), "", ""])
    print(f"{ARQ_CSV_SUBST}: {len(novos)} substitutos")


def hash_exemplo(e: dict) -> str:
    """Hash do que o Luigi revisou: texto mascarado, trecho citado e justificativa da IA."""
    return hashlib.sha256(json.dumps([e["texto"], e.get("trecho", ""), e.get("justificativa", "")], ensure_ascii=False).encode("utf-8")).hexdigest()


def publicar() -> None:
    """Só os exemplos com aprovado_s_n = s entram no site. Grava o hash de cada texto aprovado."""
    rascunho = {ln["id"]: ln for ln in ler_jsonl(ARQ_RASCUNHO)}
    rev = _ler_revisoes()
    aprovados = [r["id"] for r in rev if r["aprovado_s_n"].strip().lower() in ("s", "sim")]
    pendentes = [r["id"] for r in rev if r["aprovado_s_n"].strip() == ""]
    if pendentes:
        raise SystemExit(f"revisão incompleta: {len(pendentes)} exemplos sem 's' ou 'n'")
    for r in rev:  # o texto revisado tem de ser o mesmo do rascunho
        if r["id"] in aprovados and r["texto_mascarado"] != rascunho[r["id"]]["texto"]:
            raise SystemExit(f"o texto do exemplo {r['id']} foi editado no CSV; refaça a seleção")
    lim = limiares()["0.01"]
    exemplos = []
    for i in sorted(aprovados, key=int):
        e = {k: v for k, v in rascunho[i].items() if k != "alertas_detector"}
        e["motivo"] = politica(e["confianca"], e["sonnet"], e["ml"], e["p_ml"], lim)[1]  # texto atual do motivo
        if i in NOTAS_ROTULO:
            e["nota_rotulo"] = NOTAS_ROTULO[i]
        exemplos.append(e)
    DIR_DADOS.mkdir(parents=True, exist_ok=True)
    ARQ_EXEMPLOS.write_text(json.dumps({"exemplos": exemplos}, ensure_ascii=False, indent=1) + "\n")
    ARQ_APROVADOS.write_text(json.dumps({
        "aprovado_por": "Luigi (revisão manual de nomes)", "arquivo": "mesa/dados/exemplos.json",
        "exemplos_aprovados_sha256": {e["id"]: hash_exemplo(e) for e in exemplos},
        "nao_aprovados": sorted(set(rascunho) - set(aprovados), key=int),
    }, ensure_ascii=False, indent=1) + "\n")
    print(f"{ARQ_EXEMPLOS}: {len(exemplos)} exemplos aprovados")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["dados", "selecionar", "substituir", "publicar"])
    a = ap.parse_args()
    {"dados": dados, "selecionar": selecionar, "substituir": substituir, "publicar": publicar}[a.cmd]()


if __name__ == "__main__":
    main()
