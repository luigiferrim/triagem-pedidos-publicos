"""Revisão manual dirigida de nomes que escaparam da máscara (feita no Marco 3).

Seleciona, em dev e teste, os textos com tema de naturalização, genealogia ou certidão (onde nomes estrangeiros
e de terceiros são mais prováveis). Esses textos foram lidos à mão. O resultado da leitura (quais tinham nome de
pessoa sem máscara) está em ACHADOS, escrito à mão.

Saída: results/pii_revisao_dirigida.json (só ids, sem texto).
"""
import json
import re

from triagem import config
from triagem.preparar import ler_jsonl

PADRAO = r"naturaliza|imigra|trisav|bisav|genealog|cidadania italiana|certid"
# Leitura manual (10/11/2026): ids com nome de pessoa sem máscara e o motivo (sem o nome).
ACHADOS = {
    "10016176": "prenome estrangeiro fora da lista do IBGE; o NER pegou 1 de 3 ocorrências",
    "10118069": "nome depois de 'Proprietário:', que não é pista da máscara",
}


def main() -> None:
    regs = ler_jsonl(config.ARQ_DEV) + ler_jsonl(config.ARQ_TESTE)
    ids = sorted(r["id"] for r in regs if re.search(PADRAO, r["texto"], re.I))
    assert set(ACHADOS) <= set(ids)
    saida = {"criterio": f"regex (sem maiúsculas/minúsculas): {PADRAO}", "textos_em_dev_e_teste": len(regs),
             "textos_revistos_a_mao": len(ids), "ids_revistos": ids,
             "com_nome_sem_mascara": len(ACHADOS), "achados": ACHADOS,
             "nao_revistos": "os outros textos de dev e teste e os 20 exemplos do prompt não foram lidos à mão; "
                             "a taxa de escape fora deste recorte é desconhecida"}
    (config.RESULTS / "pii_revisao_dirigida.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print({k: v for k, v in saida.items() if k != "ids_revistos"})


if __name__ == "__main__":
    main()
