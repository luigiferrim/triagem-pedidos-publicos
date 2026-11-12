"""Um só número em todo lugar: site, relatório, README e DECISAO usam results/manchete.json.
Desde o Marco 10, a manchete é março a outubro de 2026; janeiro e fevereiro ficam como histórico no mesmo arquivo."""
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


@pytest.mark.skipif(not ARQ.exists(), reason="rode make manchete")
def test_manchete_e_mar_out_e_bate_com_o_marco8():
    m = json.loads(ARQ.read_text())
    m8 = json.loads((config.RESULTS / "marco8_resultado.json").read_text())["acumulado_mar_out"]["original"]
    assert (m["acumulado"]["cobertos"], m["acumulado"]["erros"]) == (m8["cobertos"], m8["erros"])
    assert m["acumulado"]["pedidos"] == 1200 and len(m["meses"]) == 8
    assert m["meta_atingida"] is False and m["acumulado"]["erro"] > m["meta"]


@pytest.mark.skipif(not ARQ.exists(), reason="rode make manchete")
def test_historico_jan_fev_preservado():
    m = json.loads(ARQ.read_text())
    h = m["historico_jan_fev"]
    assert h["acumulado"]["pedidos"] == 1000 and h["acumulado"]["erros"] == sum(x["erros"] for x in h["meses"].values())
    for doc in ("README.md", "DECISAO.md"):
        assert _br(100 * h["acumulado"]["erro"], 2) + "%" in (config.RAIZ / doc).read_text()


def test_frase_da_manchete_nos_docs():
    """A faixa de erro (sem o lote / com o lote) e o por 1.000 aparecem no README e na DECISAO."""
    m = json.loads(ARQ.read_text())
    for doc in ("README.md", "DECISAO.md"):
        t = (config.RAIZ / doc).read_text()
        assert _br(100 * m["sem_o_lote_do_inss"]["erro"], 2) + "%" in t
        assert _br(100 * m["acumulado"]["cobertura"], 1) + "%" in t or str(m["acumulado"]["por_1000"]["sem_pessoa"]) in t
