"""Testes da Mesa de Triagem (Marco 6): política, dados públicos, exceção da varredura e modo ao vivo sem rede."""
import json

import numpy as np
import pytest

from triagem import config
from triagem.mesa import hash_exemplo, politica

LIM = [1, 1, 0.8035]


@pytest.mark.parametrize("conf, sonnet, ml, p, auto, motivo", [
    ("alta", "MS", "MF", 0.10, True, "confiança alta"),
    ("media", "MS", "MS", 0.93, True, "média, mas o ML concordou (p = 0,93)"),
    ("media", "MS", "MS", 0.80, False, "incerto, foi para pessoa (média; o ML concordou, mas com p = 0,80)"),
    ("media", "MS", "MF", 0.99, False, "incerto, foi para pessoa (média; o ML sugeriu MF)"),
    ("baixa", "MS", "MS", 0.99, False, "incerto, foi para pessoa (confiança baixa)"),
    (None, None, "MS", 0.0, False, "incerto, foi para pessoa (confiança baixa)"),
])
def test_politica_e_motivo(conf, sonnet, ml, p, auto, motivo):
    assert politica(conf, sonnet, ml, p, LIM) == (auto, motivo)


ARQ_HOLDOUT_PUB = config.RAIZ / "mesa" / "dados" / "holdout.json"


@pytest.mark.skipif(not ARQ_HOLDOUT_PUB.exists(), reason="rode make mesa")
def test_dados_publicos_sem_texto_e_batem_com_o_holdout():
    pub = json.loads(ARQ_HOLDOUT_PUB.read_text())
    permitidos = {"id", "rotulo", "sonnet", "confianca", "ml", "p_ml", "reencaminhado"}
    assert len(pub["pedidos"]) == 500 and all(set(p) == permitidos for p in pub["pedidos"])
    res = json.loads((config.RESULTS / "holdout_2026_resultado.json").read_text())
    h = res["regras_congeladas"]["sonnet_0.01"]["holdout"]
    # a política aplicada aos números públicos reproduz o resultado do holdout (o que o painel mostra)
    auto = [p for p in pub["pedidos"] if politica(p["confianca"], p["sonnet"], p["ml"], p["p_ml"], pub["limiares"]["1%"])[0]]
    assert len(auto) == h["cobertos"]
    assert sum(p["sonnet"] != p["rotulo"] for p in auto) == h["erros"]
    assert pub["resultado_1pct"]["erro"] == h["erro"]


def test_selecao_dos_exemplos():
    from triagem.mesa import ARQ_RASCUNHO
    from triagem.preparar import ler_jsonl
    if not ARQ_RASCUNHO.exists():
        pytest.skip("seleção local ausente")
    ex = ler_jsonl(ARQ_RASCUNHO)[:30]
    tipos = [e["tipo"] for e in ex]
    assert tipos.count("erro da IA (automático)") == 3 and tipos.count("para pessoa") == 6


def test_varredura_aceita_exemplo_aprovado_e_recusa_alterado(tmp_path, monkeypatch):
    from triagem import varrer_versionados as v
    monkeypatch.setattr(config, "RESULTS", tmp_path)
    e = {"id": "1", "texto": "Solicito a lista de contratos do bloco Z.", "trecho": "lista de contratos", "justificativa": "j", "rotulo": "MGI"}
    (tmp_path / "mesa_exemplos_aprovados.json").write_text(json.dumps({"exemplos_aprovados_sha256": {"1": hash_exemplo(e)}}))
    ok = v.conteudo_para_varredura(v.ARQ_EXEMPLOS_MESA, json.dumps({"exemplos": [e]}))
    assert "contratos" not in ok and "MGI" in ok  # o texto aprovado sai da busca; o resto continua
    e2 = dict(e, texto="Solicito a lista de contratos do bloco Y.")
    with pytest.raises(SystemExit):
        v.conteudo_para_varredura(v.ARQ_EXEMPLOS_MESA, json.dumps({"exemplos": [e2]}))
    assert v.conteudo_para_varredura("outro.json", "texto qualquer") == "texto qualquer"


def test_ao_vivo_manda_texto_mascarado_e_aplica_politica(tmp_path, monkeypatch):
    from triagem import mesa_ao_vivo as av
    monkeypatch.setattr(config, "CACHE", tmp_path)

    class ML:
        classes_ = np.array(["INSS", "MS"])

        def predict_proba(self, textos):
            return np.array([[0.05, 0.95]])

    monkeypatch.setattr(av, "_modelo_ml", lambda: ML())
    enviados = []

    class Cliente:
        class messages:
            @staticmethod
            def create(**corpo):
                enviados.append(corpo["messages"][0]["content"])

                class R:
                    content = [type("B", (), {"type": "text", "text": '{"orgao":"MS","trecho":"vacina","justificativa":"saúde","confianca":"media"}'})()]
                    stop_reason = "end_turn"
                    usage = type("U", (), {"input_tokens": 10, "output_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})()
                    id = "x"
                return R()

    r = av.classificar("Meu nome é Valdemar Quintanilha Brito, CPF 123.456.789-09. Quero dados da vacina.", cliente=Cliente())
    assert "Valdemar" not in enviados[0] and "123.456" not in enviados[0] and "[NOME]" in enviados[0]
    assert r["status"] == "encaminhado automaticamente" and r["motivo"].startswith("média, mas o ML concordou")


ARQ_EX = config.RAIZ / "mesa" / "dados" / "exemplos.json"


@pytest.mark.skipif(not ARQ_EX.exists(), reason="exemplos ainda não publicados")
def test_exemplos_publicados_sao_os_aprovados():
    ex = json.loads(ARQ_EX.read_text())["exemplos"]
    aprov = json.loads((config.RESULTS / "mesa_exemplos_aprovados.json").read_text())
    assert len(ex) == 30
    assert {e["id"] for e in ex} == set(aprov["exemplos_aprovados_sha256"])
    assert all(aprov["exemplos_aprovados_sha256"][e["id"]] == hash_exemplo(e) for e in ex)
    assert not {e["id"] for e in ex} & set(aprov["nao_aprovados"])
    tipos = [e["tipo"] for e in ex]
    assert tipos.count("erro da IA (automático)") == 3 and tipos.count("para pessoa") == 6 and tipos.count("automático") == 21


@pytest.mark.parametrize("host, origem, ok", [
    ("127.0.0.1:8765", None, True),
    ("localhost:8765", "http://localhost:8765", True),
    ("127.0.0.1:8765", "https://site-qualquer.com", False),
    ("exemplo.com", None, False),
])
def test_ao_vivo_so_aceita_a_mesa_local(host, origem, ok):
    from triagem.mesa_ao_vivo import Handler

    class Falso:
        headers = {"Host": host, **({"Origin": origem} if origem else {})}

    assert Handler._origem_local(Falso()) is ok
