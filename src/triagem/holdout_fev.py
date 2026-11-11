"""Holdout de fevereiro de 2026 (Marco 7): o teste final de v1 x v2.

Mesmo recorte, estratificação e máscara do holdout de janeiro (triagem.holdout). Sem textos repetidos de pedidos
anteriores: tira os iguais a qualquer pedido de 2025 ou de janeiro de 2026.

O hash vai para results/holdout_2026_02.json e para o README num commit feito ANTES de rodar qualquer modelo,
junto com o prompt, a ferramenta, a tabela do SIORG e os limiares congelados (v1 e v2).

Uso: python -m triagem.holdout_fev preparar
"""
import argparse
import json
from collections import Counter

import numpy as np
import pandas as pd

from triagem import config, dados, orgaos, pii
from triagem.holdout import DIR_RAW, _csv
from triagem.preparar import _normalizar, _registro, _texto, amostrar, escrever_jsonl, ler_jsonl, sha256

MES = 2
ARQ = config.DATA / "holdout_2026_02.jsonl"
ARQ_RES = config.RESULTS / "holdout_2026_02.json"


def preparar() -> None:
    if ARQ.exists():
        raise SystemExit(f"{ARQ} já existe. O holdout é congelado.")
    df = dados.ler_csv(_csv())
    lista = orgaos.top_orgaos(dados.ler_filtrada())
    base = df[(df["Esfera"] == "Federal") & df["OrgaoDestinatario"].isin(lista)].copy()
    pool = base[orgaos.rotulo_confiavel(base)].copy()
    passos = {"linhas_2026": len(df), "federal_10_orgaos_rotulo_confiavel": len(pool)}
    pool["_texto"] = _texto(pool)
    pool["_norm"] = _normalizar(pool["_texto"])
    pool = pool[pool.groupby("_norm")["OrgaoDestinatario"].transform("nunique") == 1]
    pool = pool.sort_values("IdPedido", key=lambda s: s.astype(int)).drop_duplicates("_norm", keep="first")

    mes = pd.to_datetime(pool["DataRegistro"], format="%d/%m/%Y").dt.month
    # textos anteriores: todo 2025 e todo pedido de 2026 registrado antes de fevereiro (inclui o holdout de janeiro)
    anteriores = set(_normalizar(_texto(dados.ler_filtrada())))
    todos_2026 = df.copy()
    todos_2026["_mes"] = pd.to_datetime(todos_2026["DataRegistro"], format="%d/%m/%Y").dt.month
    anteriores |= set(_normalizar(_texto(todos_2026[todos_2026["_mes"] < MES])))
    periodo = pool[mes == MES]
    antes = len(periodo)
    periodo = periodo[~periodo["_norm"].isin(anteriores)]
    passos["descartados_texto_igual_a_anterior"] = antes - len(periodo)
    passos["pool_periodo"] = len(periodo)

    rng = np.random.default_rng([config.SEED, sum(b"holdout_2026_02")])
    amostra = amostrar(periodo, config.N_TESTE, config.MIN_POR_ORGAO_TESTE, rng)
    contagem = Counter()
    mascarados = pii.mascarar(amostra["_texto"].tolist(), contagem)
    regs = [_registro(r, t) for r, t in zip(amostra.itertuples(), mascarados)]
    anteriores_ids = {r["id"] for a in (config.ARQ_TREINO, config.ARQ_DEV, config.ARQ_TESTE, config.DATA / "holdout_2026.jsonl")
                      for r in ler_jsonl(a)}
    assert not anteriores_ids & {r["id"] for r in regs}
    escrever_jsonl(ARQ, regs)
    saida = {
        "fonte": {"csv": _csv().name, "arquivo_zip_sha256": dados.sha256_arquivo(DIR_RAW / "Arquivos_csv_2026.zip")},
        "periodo": "2026-02 a 2026-02", "passos": passos, "n": len(regs),
        "por_orgao": dict(sorted(Counter(r["orgao_sigla"] for r in regs).items())),
        "reencaminhados": sum(r["reencaminhado"] for r in regs), "pii_mascarada": dict(contagem),
        "sha256": sha256(ARQ),
        "registrado_antes_de_rodar_modelos": False,  # vira True no commit de registro, com prompt/ferramenta/limiares
    }
    ARQ_RES.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in saida.items() if k != "fonte"}, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["preparar"])
    ap.parse_args()
    preparar()


if __name__ == "__main__":
    main()
