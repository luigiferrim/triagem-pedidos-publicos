"""Holdout de 2026: confirmação do limiar escolhido no Marco 4, com dados que ninguém viu.

Motivo: no Marco 4, a meta de 1% foi adotada depois de ver o teste. Este conjunto mede o limiar CONGELADO em
pedidos novos, sem reajustar nada.

Passos (iguais ao preparar.py):
1. Base com texto de 2026 (arquivo filtrado da CGU), esfera federal, os mesmos 10 órgãos de 2025, rótulo confiável.
2. Remove textos repetidos, inclusive os iguais a algum pedido de 2025 (treino, dev ou teste).
3. Período: o mais antigo de 2026 com pedidos suficientes. Janeiro já basta (mínimo de 108 por órgão).
4. 500 pedidos estratificados por órgão (proporcional, mínimo 25), no máximo 5 por solicitante identificado.
5. Mesma máscara de dados pessoais.

O hash de data/holdout_2026.jsonl e os limiares congelados vão para results/holdout_2026.json e para o
README ANTES de rodar qualquer modelo.

Uso:
  python -m triagem.holdout preparar
  python -m triagem.holdout estimar        # custo do Sonnet, sem chamar a API para gerar
  python -m triagem.holdout rodar          # Sonnet (API) + ML, só depois da aprovação
  python -m triagem.holdout avaliar
"""
import argparse
import hashlib
import json
from collections import Counter

import numpy as np
import pandas as pd

from triagem import config, dados, orgaos, pii
from triagem.preparar import (_normalizar, _registro, _texto, amostrar, escrever_jsonl, ler_jsonl, sha256)

ANO_HOLDOUT = 2026
MESES = (1, 1)  # janeiro de 2026
URL = f"{config.URL_BASE}/Arquivos_FalaBR_Filtrado/Arquivos_csv_{ANO_HOLDOUT}.zip"
DIR_RAW = config.RAW / f"filtrada_{ANO_HOLDOUT}"
ARQ = config.DATA / f"holdout_{ANO_HOLDOUT}.jsonl"
ARQ_RES = config.RESULTS / f"holdout_{ANO_HOLDOUT}.json"
TETO_USD = 2.0


def _csv() -> "Path":
    cand = sorted(DIR_RAW.glob(f"*_Pedidos_csv_{ANO_HOLDOUT}.csv"))
    if not cand:
        raise SystemExit(f"Baixe e extraia {URL} em {DIR_RAW}")
    return cand[-1]


def limiares_congelados() -> dict:
    """Os limiares escolhidos no dev (Marco 4), lidos de results/marco4.json. Nada é reescolhido aqui."""
    m4 = json.loads((config.RESULTS / "marco4.json").read_text())
    out = {}
    for est in ("sonnet", "ml"):
        for meta in ("0.01", "0.02"):
            p = m4["estrategias"][est]["por_meta"][meta]
            out[f"{est}_{meta}"] = {"estrategia": est, "meta": float(meta), "limiar": p["limiar"],
                                    "teste": {"cobertura": p["teste"]["cobertura"], "erro": p["teste"]["erro"]}}
    return out


def preparar() -> None:
    if ARQ.exists():
        raise SystemExit(f"{ARQ} já existe. O holdout é congelado; apague à mão só se tiver certeza.")
    zip_path = DIR_RAW / f"Arquivos_csv_{ANO_HOLDOUT}.zip"
    df = dados.ler_csv(_csv())
    lista = orgaos.top_orgaos(dados.ler_filtrada())  # os 10 de 2025, sem recalcular
    passos = {"linhas_2026": len(df)}
    base = df[(df["Esfera"] == "Federal") & df["OrgaoDestinatario"].isin(lista)].copy()
    pool = base[orgaos.rotulo_confiavel(base)].copy()
    passos["federal_10_orgaos_rotulo_confiavel"] = len(pool)

    pool["_texto"] = _texto(pool)
    pool["_norm"] = _normalizar(pool["_texto"])
    n_org = pool.groupby("_norm")["OrgaoDestinatario"].transform("nunique")
    pool = pool[n_org == 1]
    pool = pool.sort_values("IdPedido", key=lambda s: s.astype(int)).drop_duplicates("_norm", keep="first")
    b25 = dados.ler_filtrada()
    norm_2025 = set(_normalizar(_texto(b25)))
    antes = len(pool)
    pool = pool[~pool["_norm"].isin(norm_2025)]
    passos["descartados_texto_igual_a_2025"] = antes - len(pool)
    passos["pool_sem_duplicatas"] = len(pool)

    mes = pd.to_datetime(pool["DataRegistro"], format="%d/%m/%Y").dt.month
    periodo = pool[mes.between(*MESES)]
    passos["pool_periodo"] = len(periodo)
    rng = np.random.default_rng([config.SEED, sum(b"holdout_2026")])
    amostra = amostrar(periodo, config.N_TESTE, config.MIN_POR_ORGAO_TESTE, rng)

    contagem = Counter()
    mascarados = pii.mascarar(amostra["_texto"].tolist(), contagem)
    regs = [_registro(r, t) for r, t in zip(amostra.itertuples(), mascarados)]
    ids_2025 = {r["id"] for arq in (config.ARQ_TREINO, config.ARQ_DEV, config.ARQ_TESTE) for r in ler_jsonl(arq)}
    assert not ids_2025 & {r["id"] for r in regs}
    escrever_jsonl(ARQ, regs)

    saida = {
        "fonte": {"url": URL, "arquivo_zip_sha256": dados.sha256_arquivo(zip_path) if zip_path.exists() else None,
                  "csv": _csv().name},
        "periodo": f"{ANO_HOLDOUT}-{MESES[0]:02d} a {ANO_HOLDOUT}-{MESES[1]:02d}",
        "passos": passos,
        "n": len(regs),
        "por_orgao": dict(sorted(Counter(r["orgao_sigla"] for r in regs).items())),
        "reencaminhados": sum(r["reencaminhado"] for r in regs),
        "pii_mascarada": dict(contagem),
        "sha256": sha256(ARQ),
        "limiares_congelados": limiares_congelados(),
        "registrado_antes_de_rodar_modelos": True,
    }
    ARQ_RES.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in saida.items() if k != "limiares_congelados"}, ensure_ascii=False, indent=1))


def estimar() -> dict:
    from triagem import llm
    from triagem.marco3 import _sistema
    regs = ler_jsonl(ARQ)
    m3 = json.loads((config.RESULTS / "marco3.json").read_text())
    t = m3["modelos"]["sonnet"]["test"]
    por_pedido = t["custo_usd"] / len(ler_jsonl(config.ARQ_TESTE))
    car_ratio = sum(len(r["texto"]) for r in regs) / sum(len(r["texto"]) for r in ler_jsonl(config.ARQ_TESTE))
    sistema = _sistema()
    for r in regs:
        llm.checar_pii(llm.corpo_requisicao(llm.MODELOS["sonnet"], sistema, r["texto"])["messages"][0]["content"])
    est = {"pedidos": len(regs), "custo_por_pedido_no_teste_usd": round(por_pedido, 5),
           "razao_de_tamanho_dos_textos_holdout_sobre_teste": round(car_ratio, 3),
           "estimativa_usd": round(por_pedido * len(regs) * max(1.0, car_ratio), 2), "teto_usd": TETO_USD,
           "checagem_de_pii_regex": "ok"}
    print(est)
    return est


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["preparar", "estimar"])
    a = ap.parse_args()
    {"preparar": preparar, "estimar": estimar}[a.cmd]()


if __name__ == "__main__":
    main()
