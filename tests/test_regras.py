from triagem.regras import Regras, citacoes_de_nome, extrair_palavras_chave
from triagem.texto import termos


def _base():
    regs = []
    for i in range(20):
        regs.append({"orgao_sigla": "ANEEL", "texto": f"tarifa de energia da distribuidora caso {i}"})
        regs.append({"orgao_sigla": "PF", "texto": f"emissão de passaporte urgente caso {i}"})
    return regs


def test_palavras_chave_vem_do_orgao_certo():
    pk = extrair_palavras_chave(_base(), k=3, min_docs=5)
    assert {"tarifa", "energia", "distribuidora"} & {p["termo"] for p in pk["ANEEL"]}
    assert {"passaporte", "emissao", "urgente"} & {p["termo"] for p in pk["PF"]}
    # "caso" aparece igual nos dois órgãos: não pode ser palavra-chave de nenhum
    assert "caso" not in {p["termo"] for lst in pk.values() for p in lst}


def test_prever_e_explicar():
    pk = {"ANEEL": [{"termo": "tarifa"}], "PF": [{"termo": "passaporte"}]}
    r = Regras(pk, peso_alias=3)
    org, margem, exp = r.prever("Quero saber da tarifa")
    assert org == "ANEEL" and margem == 1 and exp["palavras"] == ["tarifa"]


def test_sem_regra_nao_decide():
    pk = {"ANEEL": [{"termo": "tarifa"}], "PF": [{"termo": "passaporte"}]}
    org, margem, exp = Regras(pk, peso_alias=3).prever("Texto sem nenhuma pista")
    assert org is None and margem == 0.0


def test_sigla_pesa_mais_que_palavra():
    pk = {"ANEEL": [{"termo": "tarifa"}], "PF": [{"termo": "passaporte"}]}
    org, _, _ = Regras(pk, peso_alias=3).prever("Pergunto à Polícia Federal sobre a tarifa")
    assert org == "PF"


def test_citacoes_de_nome():
    c = citacoes_de_nome("Banco Central (BCB), ANVISA, Ministério da Saúde e 300 ms de latência")
    assert c["BACEN"] == 2 and c["ANVISA"] == 1 and c["MS"] == 1


def test_termos_inclui_bigramas_sem_stopwords():
    t = termos("Solicito a tarifa de energia elétrica")
    assert "tarifa" in t and "energia eletrica" in t and "solicito" not in t
