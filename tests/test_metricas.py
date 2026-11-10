import pytest

from triagem.metricas import avaliar, cita_sigla, confusoes_principais, intervalo_wilson, matriz_confusao

CLASSES = ["A", "B", "C"]


def test_acerto_total():
    m = avaliar(["A", "B", "C"], ["A", "B", "C"], CLASSES)
    assert m["acuracia"] == 1.0 and m["f1_macro"] == 1.0 and m["acertos"] == 3


def test_caso_conhecido():
    # A: 2 de 2 certos; B: 1 de 2 (um virou C); C: 0 de 1 (virou A)
    verdade = ["A", "A", "B", "B", "C"]
    pred = ["A", "A", "B", "C", "A"]
    m = avaliar(verdade, pred, CLASSES)
    assert m["acuracia"] == 0.6
    # A: P=2/3 R=1 F1=0.8 ; B: P=1 R=0.5 F1=0.6667 ; C: P=0 R=0 F1=0
    assert m["por_classe"]["A"]["f1"] == 0.8
    assert m["por_classe"]["B"]["f1"] == pytest.approx(0.6667, abs=1e-4)
    assert m["por_classe"]["C"]["f1"] == 0.0
    assert m["f1_macro"] == pytest.approx((0.8 + 2 / 3 + 0) / 3, abs=1e-4)


def test_sem_resposta_conta_como_erro():
    m = avaliar(["A", "B"], ["A", None], CLASSES)
    assert m["acuracia"] == 0.5
    assert m["n_sem_resposta"] == 1


def test_matriz_e_confusoes():
    verdade = ["A", "A", "B", "C"]
    pred = ["A", "B", "B", None]
    mat = matriz_confusao(verdade, pred, CLASSES)
    assert mat == [[1, 1, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]]
    top = confusoes_principais(verdade, pred)
    assert {"verdadeiro": "A", "previsto": "B", "n": 1} in top


def test_tamanhos_diferentes_falha():
    with pytest.raises(ValueError):
        avaliar(["A"], ["A", "B"], CLASSES)


@pytest.mark.parametrize("texto, sigla, esperado", [
    ("Solicito dados da ANVISA sobre registro", "ANVISA", True),
    ("dados da Anvisa", "ANVISA", True),
    ("pedido ao MS sobre vacinas", "MS", True),
    ("tempo de 300 ms na API", "MS", False),
    ("o MEC informou", "MEC", True),
    ("mecânica de fluidos", "MEC", False),
    ("Polícia Federal (PF)", "PF", True),
    ("petrobras e a Petrobras", "PETROBRAS", True),
    ("INSS/DIRBEN", "INSS", True),
    ("Banco Central", "BACEN", False),
])
def test_cita_sigla(texto, sigla, esperado):
    assert cita_sigla(texto, sigla) is esperado


def test_intervalo_wilson_caso_conhecido():
    # 90 acertos em 100: Wilson 95% ~ [0.8256, 0.9448]
    lo, hi = intervalo_wilson(90, 100)
    assert lo == pytest.approx(0.8256, abs=1e-3) and hi == pytest.approx(0.9448, abs=1e-3)
    assert intervalo_wilson(0, 0) == (0.0, 0.0)
