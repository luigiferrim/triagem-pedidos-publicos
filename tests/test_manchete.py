"""Um só número em todo lugar: site, relatório, README e DECISAO usam results/manchete.json."""
import json
import re

import pytest

from triagem import config

ARQ = config.RESULTS / "manchete.json"


def _br(x, c):
    return f"{x:.{c}f}".replace(".", ",")


@pytest.mark.skipif(not ARQ.exists(), reason="rode make manchete")
def test_mesmos_numeros_em_todo_lugar():
    m = json.loads(ARQ.read_text())
    a = m["acumulado"]
    erro = _br(100 * a["erro"], 2) + "%"
    for doc in ("README.md", "DECISAO.md"):
        texto = (config.RAIZ / doc).read_text()
        assert erro in texto, f"{doc} sem o erro acumulado {erro}"
        assert re.search(rf"\b{round(a['por_1000']['erros'])}\b", texto)
    # site e relatório embutem o mesmo arquivo
    site = json.loads((config.RAIZ / "mesa" / "dados" / "holdout.json").read_text())["manchete"]
    assert site == m
    rel = (config.RAIZ / "report.html").read_text()
    assert json.dumps(m["acumulado"], ensure_ascii=False) in rel


@pytest.mark.skipif(not ARQ.exists(), reason="rode make manchete")
def test_acumulado_e_soma_dos_meses():
    m = json.loads(ARQ.read_text())
    meses = list(m["meses"].values())
    assert m["acumulado"]["pedidos"] == sum(x["pedidos"] for x in meses)
    assert m["acumulado"]["erros"] == sum(x["erros"] for x in meses)
    assert m["acumulado"]["cobertos"] == sum(x["cobertos"] for x in meses)
