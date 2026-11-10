"""Testes do módulo LLM sem chamar a API."""
import pytest

from triagem import config, llm
from triagem.preparar import ler_jsonl


@pytest.mark.parametrize("resposta, orgao, erro", [
    ('{"orgao": "MS", "trecho": "vacina", "justificativa": "saúde", "confianca": "alta"}', "MS", None),
    ('```json\n{"orgao": "pf", "trecho": "x", "justificativa": "y", "confianca": "média"}\n```', "PF", None),
    ('Claro! Aqui está: {"orgao": "ANEEL", "trecho": "t", "justificativa": "j", "confianca": "baixa"} ok', "ANEEL", None),
    ('{"orgao": "INEP", "trecho": "t", "justificativa": "j", "confianca": "alta"}', None, "orgao_invalido"),
    ('{"orgao": "MS", "trecho": "t"', None, "sem_json"),
    ('{"orgao": "MS", "trecho": "t", }', None, "json_invalido"),
    ("", None, "vazia"),
    (None, None, "vazia"),
    ("[1, 2]", None, "nao_objeto"),
    ("texto sem json nenhum", None, "sem_json"),
])
def test_interpretar(resposta, orgao, erro):
    dados, e = llm.interpretar(resposta)
    assert e == erro
    assert (dados["orgao"] if dados else None) == orgao


def test_confianca_invalida_vira_none():
    dados, e = llm.interpretar('{"orgao": "MS", "trecho": "t", "justificativa": "j", "confianca": "talvez"}')
    assert e is None and dados["confianca"] is None


def test_custo_caso_conhecido():
    uso = {"input_tokens": 1_000_000, "output_tokens": 1_000_000,
           "cache_creation_input_tokens": 1_000_000, "cache_read_input_tokens": 1_000_000}
    assert llm.custo_usd("claude-sonnet-5-5", uso) == pytest.approx(2.0 + 10.0 + 2.5 + 0.10)
    assert llm.custo_usd("claude-haiku-5-5", uso) == pytest.approx(0.10 + 0.50 + 0.125 + 0.01)


def test_trecho_esta_no_pedido():
    texto = "Solicito a relação de apreensões de cigarros em 2024."
    assert llm.trecho_esta_no_pedido("apreensões de cigarros", texto)
    assert llm.trecho_esta_no_pedido("APREENSOES DE CIGARROS", texto)
    assert not llm.trecho_esta_no_pedido("apreensões de armas", texto)
    assert not llm.trecho_esta_no_pedido("de", texto)


@pytest.fixture(scope="module")
def sistema():
    return llm.prompt_sistema(llm.escolher_exemplos(ler_jsonl(config.ARQ_TREINO_AMOSTRA)))


def test_exemplos_so_do_treino_e_deterministicos():
    amostra = ler_jsonl(config.ARQ_TREINO_AMOSTRA)
    a, b = llm.escolher_exemplos(amostra), llm.escolher_exemplos(amostra)
    assert [e["id"] for e in a] == [e["id"] for e in b]
    ids_treino = {r["id"] for r in amostra}
    ids_avaliacao = {r["id"] for r in ler_jsonl(config.ARQ_TESTE) + ler_jsonl(config.ARQ_DEV)}
    assert all(e["id"] in ids_treino and e["id"] not in ids_avaliacao for e in a)
    assert len(a) == 2 * len(llm.SIGLAS)


def test_nada_com_dado_pessoal_vai_para_a_api(sistema):
    """O prompt e todos os pedidos de dev e teste passam pela checagem de PII sem erro."""
    llm.checar_pii(sistema)
    for r in ler_jsonl(config.ARQ_DEV) + ler_jsonl(config.ARQ_TESTE):
        corpo = llm.corpo_requisicao(llm.MODELOS["haiku"], sistema, r["texto"])
        llm.checar_pii(corpo["messages"][0]["content"])


def test_checar_pii_bloqueia():
    with pytest.raises(ValueError):
        llm.checar_pii("meu cpf é 123.456.789-09")


def test_prefixo_identico_e_chave_deterministica(sistema):
    a = llm.corpo_requisicao(llm.MODELOS["sonnet"], sistema, "pedido A")
    b = llm.corpo_requisicao(llm.MODELOS["sonnet"], sistema, "pedido B")
    assert a["system"] == b["system"]
    assert llm.chave_cache(a, "1") == llm.chave_cache(a, "1") != llm.chave_cache(b, "1")
    assert a["thinking"] == {"type": "between_tools"}
    assert llm.corpo_requisicao(llm.MODELOS["haiku"], sistema, "x")["thinking"] == {"type": "disabled"}


def test_cache_nao_chama_api_de_novo(tmp_path, monkeypatch, sistema):
    monkeypatch.setattr(config, "CACHE", tmp_path)
    cache = llm.Cache("teste")
    corpo = llm.corpo_requisicao(llm.MODELOS["haiku"], sistema, "pedido")
    cache.put({"chave": llm.chave_cache(corpo, "9"), "id": "9", "resposta": "{}"})

    class ClienteQueFalha:
        class messages:
            @staticmethod
            def create(**_):
                raise AssertionError("não devia chamar a API")

    r = llm.chamar(ClienteQueFalha(), corpo, "9", llm.Cache("teste"))
    assert r["do_cache"] is True


def test_comparacao_pareada_caso_conhecido():
    from triagem.marco3 import comparacao_pareada
    a = [True] * 8 + [False] * 2
    b = [True] * 6 + [False] * 4
    r = comparacao_pareada(a, b, n_boot=200)
    assert r["diferenca_pp"] == 20.0 and r["so_a_acerta"] == 2 and r["so_b_acerta"] == 0
    assert r["ic95_pp"][0] <= 20.0 <= r["ic95_pp"][1]


ARQ_M3 = config.RESULTS / "marco3.json"


@pytest.mark.skipif(not ARQ_M3.exists(), reason="Marco 3 ainda não rodou")
def test_predicoes_llm_batem_com_marco3_e_nao_tem_texto():
    import json
    from triagem.marco2 import DIR_PRED
    m3 = json.loads(ARQ_M3.read_text())
    permitidos = {"id", "verdadeiro", "previsto", "confianca", "erro_resposta", "trecho_literal", "cita_sigla", "reencaminhado"}
    for ap in llm.MODELOS:
        for conj, dados in m3["modelos"][ap].items():
            if conj == "id_modelo" or "acuracia" not in dados:
                continue
            linhas = ler_jsonl(DIR_PRED / f"{ap}_{conj}.jsonl")
            assert all(set(ln) <= permitidos for ln in linhas)
            acur = sum(ln["previsto"] == ln["verdadeiro"] for ln in linhas) / len(linhas)
            assert round(acur, 4) == dados["acuracia"]


@pytest.mark.skipif(not (config.RESULTS / "erros_lado_a_lado.json").exists(), reason="análise de erros não rodou")
def test_analise_de_erros_sem_texto_e_com_classificacao_completa():
    import json
    resumo = json.loads((config.RESULTS / "erros_lado_a_lado.json").read_text())
    assert len(resumo["casos"]) == 20
    assert all(c["sonnet"] != c["verdadeiro"] or c["haiku"] != c["verdadeiro"] for c in resumo["casos"])
    campos_texto = {"texto", "trecho", "justificativa", "texto_mascarado"}
    assert not any(campos_texto & set(c) for c in resumo["casos"])
    assert sum(resumo["categorias"].values()) == 20


def test_registro_do_teste_tem_um_so_prompt():
    """Todas as avaliações do teste do Marco 3 usaram o mesmo prompt (não houve ajuste depois de ver o teste)."""
    import json
    from triagem.marco2 import REGISTRO_TESTE
    from triagem.marco3 import _sistema, hash_prompt
    regs = [json.loads(l) for l in open(REGISTRO_TESTE, encoding="utf-8") if '"marco": 3' in l]
    if not regs:
        pytest.skip("teste do Marco 3 ainda não avaliado")
    assert {r["hash_prompt"] for r in regs} == {hash_prompt(_sistema())}
