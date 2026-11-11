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


ARQ_FEV = config.RESULTS / "marco7_fev.json"


@pytest.mark.skipif(not ARQ_FEV.exists(), reason="fevereiro não avaliado")
def test_fevereiro_usou_os_limiares_congelados():
    reg = json.loads(ARQ.read_text())
    fev = json.loads(ARQ_FEV.read_text())
    assert fev["limiar_v1"] == reg["limiar_v1"] and fev["limiar_v2"] == reg["limiar_v2"]
    # todas as chamadas (v1 e v2) em pedidos de fevereiro são posteriores ao COMMIT que registrou o congelamento
    import subprocess
    from datetime import datetime, timezone
    from triagem import llm, llm_v2
    from triagem.preparar import ler_jsonl
    arq = config.DATA / "holdout_2026_02.jsonl"
    if not arq.exists():
        pytest.skip("holdout local ausente")
    commit = subprocess.run(["git", "log", "--diff-filter=A", "--format=%cI", "--", "results/marco7_congelado.json"],
                            cwd=config.RAIZ, capture_output=True, text=True).stdout.split()
    if not commit:
        pytest.skip("sem git")
    t_commit = datetime.fromisoformat(commit[-1]).astimezone(timezone.utc)
    ids = {r["id"] for r in ler_jsonl(arq)}
    quando = [r["quando"] for c in (llm_v2.cache_v2(), llm.Cache(llm.MODELOS["sonnet"])) for r in c.dados.values() if r["id"] in ids]
    assert len(quando) == 2 * len(ids)
    assert all(datetime.fromisoformat(q) > t_commit for q in quando)
