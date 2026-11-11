"""Marco 7: o que foi congelado antes de fevereiro continua igual."""
import json

import pytest

from triagem import config

ARQ = config.RESULTS / "marco7_congelado.json"


@pytest.mark.skipif(not ARQ.exists(), reason="ainda não congelado")
def test_nada_mudou_depois_do_congelamento():
    from triagem.marco7 import estado_congelavel
    reg = json.loads(ARQ.read_text())
    atual = estado_congelavel()
    for k, v in atual.items():
        assert reg[k] == v, f"{k} mudou depois do registro de fevereiro"


@pytest.mark.skipif(not ARQ.exists(), reason="ainda não congelado")
def test_hash_de_fevereiro_no_readme_e_no_arquivo():
    from triagem.preparar import sha256
    reg = json.loads(ARQ.read_text())
    assert reg["sha256_holdout_fev"] in (config.RAIZ / "README.md").read_text()
    arq = config.DATA / "holdout_2026_02.jsonl"
    if arq.exists():
        assert sha256(arq) == reg["sha256_holdout_fev"]
