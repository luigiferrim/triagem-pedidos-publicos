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


def test_alerta_robusto_registrado_antes_das_chamadas():
    """O 2º alerta foi commitado antes de qualquer chamada do Sonnet na amostra do Marco 8."""
    import subprocess
    from datetime import datetime, timezone
    from triagem import llm
    from triagem.preparar import ler_jsonl
    arq_alertas = config.RESULTS / "marco8_alertas.json"
    if not arq_alertas.exists():
        pytest.skip("alertas não registrados")
    commit = subprocess.run(["git", "log", "--diff-filter=A", "--format=%cI", "--", "results/marco8_alertas.json"],
                            cwd=config.RAIZ, capture_output=True, text=True).stdout.split()
    amostra = config.DATA / "monitor_2026.jsonl"
    if not commit or not amostra.exists():
        pytest.skip("sem git ou sem amostra local")
    t = datetime.fromisoformat(commit[-1]).astimezone(timezone.utc)
    ids = {r["id"] for r in ler_jsonl(amostra)}
    quando = [r["quando"] for r in llm.Cache(llm.MODELOS["sonnet"]).dados.values() if r["id"] in ids]
    assert all(datetime.fromisoformat(q) > t for q in quando)
