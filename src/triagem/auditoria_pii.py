"""Auditoria da máscara de dados pessoais no dev e no teste.

1. Varredura de nomes que escaparam: prenome do IBGE seguido de palavra com cara de sobrenome, sem máscara.
2. Amostra de 80 trechos trocados por [NOME], com o texto ORIGINAL ao lado, para classificação manual
   (é nome de cidadão? ou é empresa, lugar, termo técnico?).

A amostra contém nomes reais e por isso fica fora do git (results/auditoria_pii_amostra.csv).
O resultado da classificação manual está descrito em DADOS.md, seção 7.
"""
import difflib
import json
import random
import re

import pandas as pd

from triagem import config, dados, pii
from triagem.preparar import ler_jsonl

_PAR = re.compile(r"\b([A-ZÀ-Ý][a-zà-ÿ]+|[A-ZÀ-Ý]{2,})\s+(?:d[aeo]s?\s+)?([A-ZÀ-Ý][a-zà-ÿ]+|[A-ZÀ-Ý]{2,})\b")


def main() -> None:
    regs = {r["id"]: r for nome in ("test", "dev") for r in ler_jsonl(config.DATA / f"{nome}.jsonl")}
    bruto = dados.ler_filtrada().set_index("IdPedido")

    suspeitos = []
    for r in regs.values():
        for m in _PAR.finditer(r["texto"]):
            if pii._eh_prenome(m.group(1)) and pii._parece_parte_de_nome(m.group(2)):
                suspeitos.append(r["id"])
                break

    trocas = []
    for i, r in regs.items():
        original = pii.mascarar_regex(
            (bruto.loc[i, "ResumoSolicitacao"] + "\n" + bruto.loc[i, "DetalhamentoSolicitacao"]).strip())
        sm = difflib.SequenceMatcher(None, original, r["texto"], autojunk=False)
        for op, a1, a2, b1, b2 in sm.get_opcodes():
            if op == "replace" and "[NOME]" in r["texto"][b1:b2]:
                trocas.append({"id": i, "orgao": r["orgao_sigla"], "trecho_original": original[a1:a2].strip()})

    amostra = random.Random(config.SEED).sample(trocas, min(80, len(trocas)))
    pd.DataFrame(amostra).assign(e_nome_de_cidadao="").to_csv(
        config.RESULTS / "auditoria_pii_amostra.csv", index=False, encoding="utf-8-sig")

    resumo = {
        "textos_auditados": len(regs),
        "textos_com_prenome_sobrenome_sem_mascara": len(suspeitos),
        "ids_suspeitos": suspeitos,
        "textos_com_[NOME]": sum("[NOME]" in r["texto"] for r in regs.values()),
        "trechos_trocados_por_[NOME]": len(trocas),
        "amostra_para_classificacao_manual": len(amostra),
    }
    (config.RESULTS / "auditoria_pii.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
