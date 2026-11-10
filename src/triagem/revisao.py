"""Concordância entre a revisão manual do Luigi (às cegas) e o rótulo da base.

Lê data/revisao_manual_50.csv (coluna orgao_luigi preenchida) e o gabarito.
Enquanto a coluna estiver vazia, só informa que a revisão está pendente.
Saída: results/revisao_manual.json (só contagens e pares de discordância, sem texto).
"""
import json
from collections import Counter

import pandas as pd

from triagem import config


def main() -> None:
    rev = pd.read_csv(config.ARQ_REVISAO, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    gab = pd.read_csv(config.DATA / "revisao_manual_50_gabarito.csv", dtype=str, encoding="utf-8-sig")
    df = rev.merge(gab, on="id")
    preenchidos = df[df["orgao_luigi"].str.strip() != ""].copy()
    if preenchidos.empty:
        saida = {"status": "pendente", "preenchidos": 0, "total": len(df)}
    else:
        preenchidos["orgao_luigi"] = preenchidos["orgao_luigi"].str.strip().str.upper()
        conc = preenchidos["orgao_luigi"] == preenchidos["orgao_base"]
        cert = preenchidos["certeza_1a3"].str.strip()
        saida = {
            "status": "completo" if len(preenchidos) == len(df) else "parcial",
            "preenchidos": int(len(preenchidos)),
            "total": int(len(df)),
            "concordancia": round(float(conc.mean()), 3),
            "concordancia_com_certeza_3": round(float(conc[cert == "3"].mean()), 3) if (cert == "3").any() else None,
            "luigi_marcou_outro": int((preenchidos["orgao_luigi"] == "OUTRO").sum()),
            "discordancias": [{"id": i, "base": b, "luigi": l} for i, b, l in
                              preenchidos.loc[~conc, ["id", "orgao_base", "orgao_luigi"]].itertuples(index=False)],
            "pares_mais_comuns": [{"base": b, "luigi": l, "n": n} for (b, l), n in Counter(
                zip(preenchidos.loc[~conc, "orgao_base"], preenchidos.loc[~conc, "orgao_luigi"])).most_common(5)],
        }
    (config.RESULTS / "revisao_manual.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in saida.items() if k != "discordancias"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
