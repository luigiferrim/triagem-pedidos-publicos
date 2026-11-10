"""O holdout de 2026 foi registrado antes de rodar e não mudou depois."""
import json

import pytest

from triagem import config
from triagem.preparar import sha256

RES = config.RESULTS / "holdout_2026.json"
ARQ = config.DATA / "holdout_2026.jsonl"


def test_hash_do_holdout_no_readme_e_no_registro():
    reg = json.loads(RES.read_text())
    assert reg["sha256"] in (config.RAIZ / "README.md").read_text()
    if ARQ.exists():
        assert sha256(ARQ) == reg["sha256"]


def test_limiares_congelados_sao_os_do_marco4():
    reg = json.loads(RES.read_text())["limiares_congelados"]
    m4 = json.loads((config.RESULTS / "marco4.json").read_text())
    for nome, lim in reg.items():
        assert lim["limiar"] == m4["estrategias"][lim["estrategia"]]["por_meta"][str(lim["meta"])]["limiar"]


@pytest.mark.skipif(not (config.RESULTS / "holdout_2026_resultado.json").exists(), reason="holdout não avaliado")
def test_resultado_usa_o_mesmo_holdout_e_os_mesmos_limiares():
    reg = json.loads(RES.read_text())
    res = json.loads((config.RESULTS / "holdout_2026_resultado.json").read_text())
    assert res["sha256"] == reg["sha256"]
    for nome, r in res["regras_congeladas"].items():
        assert r["limiar"] == reg["limiares_congelados"][nome]["limiar"]


def test_holdout_disjunto_de_2025():
    if not ARQ.exists():
        pytest.skip("holdout local ausente")
    from triagem.preparar import ler_jsonl
    ids = {r["id"] for r in ler_jsonl(ARQ)}
    for arq in (config.ARQ_TREINO, config.ARQ_DEV, config.ARQ_TESTE):
        assert not ids & {r["id"] for r in ler_jsonl(arq)}
    assert all(r["data_registro"].endswith("/01/2026") for r in ler_jsonl(ARQ))
