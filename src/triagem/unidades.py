"""Tabela "unidade/sigla -> órgão entre os 10" a partir do SIORG (Marco 7). Nunca a partir dos rótulos de treino.

Fonte: API de dados abertos do SIORG (Sistema de Organização e Inovação Institucional do Governo Federal),
https://estruturaorganizacional.dados.gov.br. O bruto fica em data/raw/siorg/ (fora do git).

Relações:
- "interna": unidade dentro da estrutura de um dos 10 órgãos (ex.: Arquivo Nacional no MGI, SESAI no MS).
- "vinculada": entidade vinculada a um dos 10, com estrutura e SIC próprios (ex.: Fiocruz, vinculada ao MS).
  No Fala.BR ela é outro órgão, então a ferramenta NÃO a manda para o órgão-pai.
- "fora": unidade do Ministério da Justiça fora da Polícia Federal (o MJSP não está entre os 10).

A PF não é órgão no SIORG: é unidade do MJSP. A subárvore dela vira "PF" (o órgão no Fala.BR).

Uso: python -m triagem.unidades   (baixa o que faltar e grava results/unidades_orgaos.json)
"""
import json
import re
import unicodedata
import urllib.request
from datetime import date

from triagem import config

API = "https://estruturaorganizacional.dados.gov.br/doc"
DIR = config.RAW / "siorg"
ARQ = config.RESULTS / "unidades_orgaos.json"
# Código SIORG de cada órgão entre os 10 (conferido na lista orgao-entidade/resumida). PF fica dentro do MJSP.
CODIGOS = {"MS": 304, "MF": 308800, "MGI": 308803, "MEC": 244, "BACEN": 89, "INSS": 1934,
           "ANVISA": 36687, "ANEEL": 21089, "PETROBRAS": 224}
CODIGO_MJSP = 235881
SIGLA_PF_NO_SIORG = "PF"


def _baixar(url: str, arq) -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    if not arq.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "triagem-pedidos-publicos"})
        with urllib.request.urlopen(req, timeout=300) as r:
            arq.write_bytes(r.read())
    d = json.loads(arq.read_text(encoding="utf-8"))
    if d["servico"]["codigoErro"] != 0:
        raise SystemExit(f"SIORG respondeu erro para {url}: {d['servico']['mensagem']}")
    return d


def _cod(url_ou_none) -> int | None:
    return int(url_ou_none.rsplit("/", 1)[-1]) if url_ou_none else None


def normalizar(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def montar() -> dict:
    linhas, fontes = [], {}
    lista = _baixar(f"{API}/orgao-entidade/resumida", DIR / "orgao_entidade_resumida.json")
    fontes["orgao_entidade_resumida"] = {"url": f"{API}/orgao-entidade/resumida", "data_consulta": lista["servico"]["data"]}

    def estrutura(cod):
        """Unidades da estrutura, cada uma com o nível na árvore (0 = o próprio órgão)."""
        url = f"{API}/estrutura-organizacional/completa?codigoUnidade={cod}"
        d = _baixar(url, DIR / f"estrutura_{cod}.json")
        fontes[f"estrutura_{cod}"] = {"url": url, "data_consulta": d["servico"]["data"], "unidades": len(d["unidades"])}
        pai = {_cod(u["codigoUnidade"]): _cod(u.get("codigoUnidadePai")) for u in d["unidades"]}

        def nivel(c, n=0):
            while c in pai and c != cod and n < 50:
                c, n = pai[c], n + 1
            return n
        for u in d["unidades"]:
            u["_nivel"] = nivel(_cod(u["codigoUnidade"]))
        return d["unidades"]

    for orgao, cod in CODIGOS.items():
        for u in estrutura(cod):
            linhas.append({"sigla": u.get("sigla") or "", "nome": u["nome"], "orgao": orgao, "relacao": "interna",
                           "nivel": u["_nivel"], "codigo_siorg": _cod(u["codigoUnidade"]), "fonte": f"estrutura_{cod}"})

    # PF: subárvore da unidade "PF" dentro do MJSP; o resto do MJSP fica "fora".
    mj = estrutura(CODIGO_MJSP)
    filhos = {}
    for u in mj:
        filhos.setdefault(_cod(u.get("codigoUnidadePai")), []).append(_cod(u["codigoUnidade"]))
    raiz_pf = [_cod(u["codigoUnidade"]) for u in mj if (u.get("sigla") or "").upper() == SIGLA_PF_NO_SIORG]
    if len(raiz_pf) != 1:
        raise SystemExit(f"esperava 1 unidade PF no MJSP, achei {len(raiz_pf)}")
    sub_pf, pilha = set(), list(raiz_pf)
    while pilha:
        c = pilha.pop()
        if c not in sub_pf:
            sub_pf.add(c)
            pilha += filhos.get(c, [])
    for u in mj:
        c = _cod(u["codigoUnidade"])
        linhas.append({"sigla": u.get("sigla") or "", "nome": u["nome"],
                       "orgao": "PF" if c in sub_pf else None, "relacao": "interna" if c in sub_pf else "fora",
                       "nivel": u["_nivel"], "codigo_siorg": c, "fonte": f"estrutura_{CODIGO_MJSP}"})

    # Entidades vinculadas a um dos 10 (com SIC próprio): registradas, mas sem órgão entre os 10.
    codigos_10 = set(CODIGOS.values())
    for u in lista["unidades"]:
        c, pai = _cod(u["codigoUnidade"]), _cod(u.get("codigoUnidadePai"))
        if c not in codigos_10 and pai in codigos_10:
            dono = next(o for o, k in CODIGOS.items() if k == pai)
            linhas.append({"sigla": u.get("sigla") or "", "nome": u["nome"], "orgao": None,
                           "relacao": f"vinculada ({dono})", "nivel": 1, "codigo_siorg": c, "fonte": "orgao_entidade_resumida"})

    vistos, unicas = set(), []
    for ln in linhas:
        k = (ln["codigo_siorg"], ln["orgao"], ln["relacao"])
        if k not in vistos:
            vistos.add(k)
            unicas.append(ln)
    saida = {"fonte": "SIORG, API de dados abertos (estruturaorganizacional.dados.gov.br)", "gerado_em": date.today().isoformat(),
             "consultas": fontes, "por_orgao": {}, "unidades": unicas}
    for ln in unicas:
        k = ln["orgao"] or ln["relacao"].split(" ")[0]
        saida["por_orgao"][k] = saida["por_orgao"].get(k, 0) + 1
    ARQ.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"{ARQ}: {len(unicas)} unidades; por órgão: {saida['por_orgao']}")
    return saida


_TABELA = None


def _tabela() -> list[dict]:
    global _TABELA
    if _TABELA is None:
        _TABELA = [dict(u, _ns=normalizar(u["sigla"]), _ns1=normalizar(u["sigla"].split("/")[0]), _nn=normalizar(u["nome"]))
                   for u in json.loads(ARQ.read_text())["unidades"]]
    return _TABELA


def consultar_unidade(texto: str, limite: int = 3) -> list[dict]:
    """Procura uma unidade pela sigla (exata) ou pelo nome (trecho). Devolve até `limite` resultados.

    Ordem: sigla exata (ou a parte antes da barra, como em "CARF/MF") > nome exato > nome que contém o texto;
    dentro de cada grupo, a unidade mais alta na árvore primeiro (secretaria antes de seção), depois o nome mais curto."""
    q = normalizar(texto)
    if len(q) < 2:
        return []
    achados = []
    for u in _tabela():
        if u["_ns"] and (u["_ns"] == q or u["_ns1"] == q):
            achados.append((0, u["nivel"], len(u["_nn"]), u))
        elif u["_nn"] == q:
            achados.append((1, u["nivel"], len(u["_nn"]), u))
        elif len(q) >= 4 and re.search(rf"\b{re.escape(q)}\b", u["_nn"]):
            achados.append((2, u["nivel"], len(u["_nn"]), u))
    achados.sort(key=lambda x: x[:3])
    saida, vistos = [], set()
    for *_, u in achados:
        chave = (u["sigla"], u["nome"], u["orgao"])
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append({"unidade": u["nome"], "sigla": u["sigla"], "orgao_entre_os_10": u["orgao"] or "nenhum dos 10",
                      "relacao": u["relacao"]})
        if len(saida) == limite:
            break
    return saida


if __name__ == "__main__":
    montar()
