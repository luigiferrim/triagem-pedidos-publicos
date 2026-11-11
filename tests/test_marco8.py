"""Marco 8: o que foi congelado antes das chamadas continua igual."""
import json

import pytest

from triagem import config

ARQ = config.RESULTS / "marco8_congelado.json"


@pytest.mark.skipif(not ARQ.exists(), reason="ainda não congelado")
def test_regras_e_amostra_congeladas():
    from triagem.marco3 import _sistema, hash_prompt
    from triagem.preparar import sha256
    reg = json.loads(ARQ.read_text())
    regra = json.loads((config.RESULTS / "marco8_regra.json").read_text())
    assert reg["regra_original"] == regra["regra_original"]["limiar"]
    assert reg["regra_corrigida"] == regra["regra_corrigida"]["limiar"]
    assert reg["sha256_prompt_v1"] == hash_prompt(_sistema())
    assert reg["sha256_amostra"] in (config.RAIZ / "README.md").read_text()
    arq = config.DATA / "monitor_2026.jsonl"
    if arq.exists():
        assert sha256(arq) == reg["sha256_amostra"]


def test_regra_corrigida_usa_so_jan_fev():
    import inspect
    from triagem import marco8
    fonte = inspect.getsource(marco8.regra) + inspect.getsource(marco8._linhas_jan_fev)
    assert "monitor_2026" not in fonte and "ARQ_AMOSTRA" not in fonte
