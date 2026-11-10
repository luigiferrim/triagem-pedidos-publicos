"""As métricas de results/marco2.json batem com os arquivos de previsão (sem texto)."""
import json

import pytest

from triagem import config
from triagem.preparar import ler_jsonl

ABORDAGENS = ["so_sigla", "regras", "ml", "ml_amostra"]


@pytest.fixture(scope="module")
def resultado():
    return json.loads((config.RESULTS / "marco2.json").read_text())


@pytest.mark.parametrize("ab", ABORDAGENS)
@pytest.mark.parametrize("conj", ["dev", "test"])
def test_acuracia_bate_com_predicoes(resultado, ab, conj):
    preds = ler_jsonl(config.RESULTS / "predicoes" / f"{ab}_{conj}.jsonl")
    acertos = sum(p["previsto"] == p["verdadeiro"] for p in preds)
    assert len(preds) == 500
    assert resultado["abordagens"][ab][conj]["acertos"] == acertos
    cita = [p for p in preds if p["cita_sigla"]]
    sub = resultado["abordagens"][ab][conj]["subgrupos"]["cita_sigla_literal"]
    assert sub["n"] == len(cita) and sub["acertos"] == sum(p["previsto"] == p["verdadeiro"] for p in cita)


def test_ids_das_predicoes_sao_os_do_teste():
    ids_teste = {r["id"] for r in ler_jsonl(config.ARQ_TESTE)}
    for ab in ABORDAGENS:
        assert {p["id"] for p in ler_jsonl(config.RESULTS / "predicoes" / f"{ab}_test.jsonl")} == ids_teste


def test_escolhas_feitas_no_dev(resultado):
    for ab in ("regras", "ml", "ml_amostra"):
        esc = resultado["abordagens"][ab]["escolha_no_dev"]
        melhor = max(g["acuracia_dev"] for g in resultado["abordagens"][ab]["grade_dev"])
        assert esc["acuracia_dev"] == melhor


def test_registro_do_teste_existe_e_bate(resultado):
    linhas = [json.loads(x) for x in (config.RESULTS / "registro_avaliacoes_teste.jsonl").read_text().splitlines() if x.strip()]
    ultimo = linhas[-1]
    for ab in ABORDAGENS:
        assert ultimo["acuracia_teste"][ab] == resultado["abordagens"][ab]["test"]["acuracia"]
