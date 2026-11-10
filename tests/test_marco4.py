"""Testes da abstenção (Marco 4) com casos conhecidos."""
import json

import pytest

from triagem import config
from triagem.marco4 import aplicar, curva, escolher_limiar


def _linhas():
    # 5 pedidos; a nota é uma tupla; o 3º (nota 0.7) e o 5º (nota 0.2) estão errados.
    dados = [(0.9, True), (0.8, True), (0.7, False), (0.7, True), (0.2, False)]
    return [{"id": str(k), "verdadeiro": "MS", "reencaminhado": k == 0,
             "x": ("MS" if ok else "PF", (nota,))} for k, (nota, ok) in enumerate(dados)]


def test_curva_trata_empates_juntos():
    pts = curva(_linhas(), "x")
    assert [p["cobertos"] for p in pts] == [1, 2, 4, 5]
    assert [p["erros"] for p in pts] == [0, 0, 1, 2]
    assert pts[2]["erro"] == pytest.approx(0.25)


def test_escolher_limiar_maior_cobertura_dentro_da_meta():
    pts = curva(_linhas(), "x")
    assert escolher_limiar(pts, 0.0)["cobertos"] == 2
    assert escolher_limiar(pts, 0.25)["cobertos"] == 4
    assert escolher_limiar(pts, 1.0)["cobertos"] == 5


def test_aplicar_conta_fila_e_erro():
    r = aplicar(_linhas(), "x", [0.7])
    assert r["cobertos"] == 4 and r["erros"] == 1 and r["fila_humana"] == 1
    assert r["acerto_que_a_maquina_teria_na_fila"] == 0.0
    assert r["reencaminhados_cobertos"] == 1


ARQ = config.RESULTS / "marco4.json"


@pytest.mark.skipif(not ARQ.exists(), reason="Marco 4 ainda não rodou")
def test_recomendacao_bate_com_a_curva_do_dev():
    m4 = json.loads(ARQ.read_text())
    rec = m4["recomendacao"]
    curva_dev = m4["estrategias"][rec["estrategia"]]["curva_dev"]
    ponto = next(p for p in curva_dev if p["limiar"] == rec["limiar"])
    assert ponto["erro"] <= m4["meta_recomendada"]
    assert not any(p["erro"] <= m4["meta_recomendada"] and p["cobertura"] > ponto["cobertura"] for p in curva_dev)
    assert m4["regra_pre_registrada"]["meta_cumprida_no_teste"] is False  # registrado como falhou


def test_ordem_lexicografica_com_tres_componentes():
    from triagem.marco4 import curva as c
    # confiança alta (2) vem antes de média (1) mesmo com probabilidade menor; concordância desempata a seguir.
    linhas = [{"id": "a", "verdadeiro": "MS", "reencaminhado": False, "x": ("MS", (2, 0, 0.10))},
              {"id": "b", "verdadeiro": "MS", "reencaminhado": False, "x": ("PF", (1, 1, 0.99))},
              {"id": "c", "verdadeiro": "MS", "reencaminhado": False, "x": ("MS", (2, 1, 0.05))}]
    pts = c(linhas, "x")
    assert [p["limiar"] for p in pts] == [[2, 1, 0.05], [2, 0, 0.10], [1, 1, 0.99]]
    assert [p["erros"] for p in pts] == [0, 0, 1]


def test_pesos_distribuicao_real():
    from triagem.marco4 import pesos_distribuicao_real
    linhas = [{"verdadeiro": "MS"}] * 3 + [{"verdadeiro": "PF"}]
    dor = {"federal_concluida_por_orgao_top10": [{"orgao": "MS", "n_pedidos": 90}, {"orgao": "PF", "n_pedidos": 10}]}
    w = pesos_distribuicao_real(linhas, dor)
    assert w["MS"] == pytest.approx(0.9 / 0.75) and w["PF"] == pytest.approx(0.1 / 0.25)


def test_custo_do_erro_caso_conhecido():
    from triagem.marco4 import custo_do_erro
    dor = {"federal_concluida_atraso": {"atraso_extra_mediana_dias": 4, "reencaminhados": {"mediana_dias": 17},
                                        "chegaram_certo": {"mediana_dias": 13}},
           "federal_concluida_top10": {"pct_reencaminhados": 5.0, "pct_sem_competencia": 2.0}}
    ponto = {"ponderado_distribuicao_real": {"cobertura": 0.8, "erro": 0.01}, "erro_ic95": [0.005, 0.02]}
    r = custo_do_erro(ponto, dor, 2.5)["por_1000_pedidos"]
    assert r["encaminhados_automaticamente"] == 800 and r["para_a_fila_humana"] == 200
    assert r["erros_automaticos_esperados"] == 8.0 and r["erros_automaticos_faixa_ic95"] == [4.0, 16.0]
    assert r["dias_de_atraso_dos_erros_automaticos"] == 32.0
    assert r["hoje_reencaminhados"] == 50.0 and r["hoje_dias_de_atraso"] == 200.0 and r["hoje_sem_competencia"] == 20.0
