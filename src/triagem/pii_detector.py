"""Detector offline de nomes de pessoa sem máscara em TODOS os textos enviados à API.

Textos enviados: dev (500), teste (500), os 50 da revisão manual e os 20 exemplos do prompt.
Dois detectores, ambos offline:
1. prenome da lista do IBGE (data/ref/prenomes_ibge.txt), com inicial maiúscula, seguido de outra palavra com
   inicial maiúscula (possível sobrenome);
2. pista de nome ("Proprietário:", "Nome:", "Sr.", "filho de", "naturalização de"…) seguida de palavras com
   inicial maiúscula. Pega nomes estrangeiros que não estão na lista do IBGE.

Os candidatos foram lidos à mão. O resultado da leitura está em CONFIRMADOS (ids com nome de pessoa real,
sem o nome). Todo o resto é falso alarme (órgão, lugar, rua, termo técnico).

Saída: results/pii_detector_offline.json (só ids e contagens; nenhum nome).
"""
import json
import re
import unicodedata

from triagem import config, llm
from triagem.preparar import ler_jsonl

# Leitura manual dos candidatos (10/11/2026). Rua com nome de pessoa não conta (é endereço público).
CONFIRMADOS = {
    "9614635": "nome completo de quem fez o pedido (estudante), escrito no meio do texto",
    "10016176": "prenome estrangeiro fora da lista do IBGE (titular de processo de naturalização antigo)",
    "10118069": "nome depois de 'Proprietário:' (dono de imóvel)",
}

PAL = r"[A-ZÀ-Ý][a-zà-ÿA-ZÀ-Ý']+"
PADRAO_IBGE = re.compile(rf"\b({PAL})((?:\s+(?:de|da|do|dos|das|e)?\s*{PAL})+)")
PADRAO_PISTA = re.compile(
    rf"(?i:propriet[áa]ri[oa]s?|nome|requerente|titular|interessad[oa]|falecid[oa]|filh[oa] de|net[oa] de|"
    rf"esposa de|marido de|vi[úu]v[oa] de|naturaliza[çc][ãa]o de|processo de|em nome de|sr\.?|sra\.?|senhor[a]?|"
    rf"dr\.?|dra\.?)\s*:?\s+({PAL}(?:\s+(?:de|da|do|dos|das|di|von|van)?\s*{PAL})+)")


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def textos_enviados() -> dict[str, dict[str, str]]:
    """{conjunto: {id: texto}} de tudo que foi para a API."""
    import csv
    amostra = {r["id"]: r for r in ler_jsonl(config.ARQ_TREINO_AMOSTRA)}
    ids_rev = [r["id"] for r in csv.DictReader(open(config.ARQ_REVISAO, encoding="utf-8-sig"))]
    return {
        "dev": {r["id"]: r["texto"] for r in ler_jsonl(config.ARQ_DEV)},
        "teste": {r["id"]: r["texto"] for r in ler_jsonl(config.ARQ_TESTE)},
        "revisao_50": {i: amostra[i]["texto"] for i in ids_rev},
        "exemplos_do_prompt": {e["id"]: e["texto"] for e in llm.escolher_exemplos(list(amostra.values()))},
    }


def candidatos(texto: str, prenomes: set[str]) -> dict[str, int]:
    ibge = sum(1 for m in PADRAO_IBGE.finditer(texto) if _sem_acento(m.group(1).lower()) in prenomes)
    pista = sum(1 for _ in PADRAO_PISTA.finditer(texto))
    return {"ibge": ibge, "pista": pista}


def main() -> None:
    prenomes = {_sem_acento(x.strip().lower()) for x in open(config.DATA / "ref" / "prenomes_ibge.txt", encoding="utf-8") if x.strip()}
    conj = textos_enviados()
    total = sum(len(v) for v in conj.values())
    por_conj, marcados = {}, {}
    for nome, textos in conj.items():
        m = {i: c for i, t in textos.items() if any((c := candidatos(t, prenomes)).values())}
        marcados.update(m)
        conf = sorted(i for i in textos if i in CONFIRMADOS)
        por_conj[nome] = {"textos": len(textos), "marcados_pelo_detector": len(m), "nome_confirmado_a_mao": len(conf), "ids_confirmados": conf}
    confirmados = sorted({i for v in por_conj.values() for i in v["ids_confirmados"]})
    nao_pegos = sorted(set(CONFIRMADOS) - set(marcados))
    saida = {
        "detectores": ["prenome IBGE + palavra com maiúscula", "pista de nome + palavras com maiúscula"],
        "textos_enviados": total,
        "marcados_pelo_detector": len(marcados),
        "ids_marcados": sorted(marcados),
        "nome_de_pessoa_confirmado_a_mao": len(confirmados),
        "taxa_confirmada_pct": round(100 * len(confirmados) / total, 2),
        "confirmados": {i: CONFIRMADOS[i] for i in confirmados},
        "confirmados_que_o_detector_nao_pegou": nao_pegos,
        "por_conjunto": por_conj,
        "limite": ("é um limite inferior: os detectores só veem nomes com inicial maiúscula e prenome do IBGE ou "
                   "depois de uma pista; um nome estrangeiro solto, sem pista, passaria."),
    }
    (config.RESULTS / "pii_detector_offline.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print({k: v for k, v in saida.items() if k not in ("ids_marcados", "por_conjunto")})
    print({k: {kk: vv for kk, vv in v.items() if kk != "ids_confirmados"} for k, v in por_conj.items()})


if __name__ == "__main__":
    main()
