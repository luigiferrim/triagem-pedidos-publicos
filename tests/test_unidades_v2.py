"""Marco 7: tabela do SIORG e laço da v2 (sem rede)."""
import inspect
import json

import pytest

from triagem import config, llm, llm_v2, unidades

TEM_TABELA = unidades.ARQ.exists()


@pytest.mark.skipif(not TEM_TABELA, reason="rode make unidades")
@pytest.mark.parametrize("consulta, orgao", [
    ("Arquivo Nacional", "MGI"), ("SESAI", "MS"), ("SEST", "MGI"), ("SPU", "MGI"), ("CARF", "MF"), ("PGFN", "MF"),
    ("Receita Federal", "MF"), ("Polícia Federal", "PF"),
])
def test_casos_da_analise_de_erros(consulta, orgao):
    assert unidades.consultar_unidade(consulta)[0]["orgao_entre_os_10"] == orgao


@pytest.mark.skipif(not TEM_TABELA, reason="rode make unidades")
def test_entidade_vinculada_nao_vai_para_o_orgao_pai():
    r = unidades.consultar_unidade("Fiocruz")[0]
    assert r["orgao_entre_os_10"] == "nenhum dos 10" and r["relacao"] == "vinculada (MS)"


def test_tabela_nao_usa_rotulos_de_treino():
    fonte = inspect.getsource(unidades)
    for proibido in ("ARQ_TREINO", "orgao_sigla", "ler_jsonl", "preparar"):
        assert proibido not in fonte


# ---------- laço da v2 com um cliente falso ----------
class Bloco:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def to_dict(self):
        return dict(self.__dict__)


class Resp:
    def __init__(self, stop, blocos):
        self.stop_reason, self.content = stop, blocos
        self.usage = Bloco(input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=100)
        self._request_id = "req"


FINAL = '{"orgao":"MGI","trecho":"SPU","justificativa":"SPU é do MGI","confianca":"alta"}'


class ClienteQuerSempreConsultar:
    """Pede a ferramenta sempre que pode; responde só quando tool_choice = none."""
    def __init__(self):
        self.pedidos = []
        cli = self

        class messages:
            @staticmethod
            def create(**corpo):
                cli.pedidos.append(corpo)
                if corpo["tool_choice"]["type"] == "none":
                    return Resp("end_turn", [Bloco(type="text", text=FINAL)])
                return Resp("tool_use", [Bloco(type="tool_use", id=f"t{len(cli.pedidos)}", name="consultar_unidade", input={"texto": "SPU"})])
        self.messages = messages


def test_laco_para_em_2_chamadas_e_cacheia(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path)
    monkeypatch.setattr(llm_v2, "consultar_unidade", lambda t: [{"unidade": "Secretaria do Patrimônio da União", "sigla": "SPU",
                                                                 "orgao_entre_os_10": "MGI", "relacao": "interna"}])
    cli = ClienteQuerSempreConsultar()
    cache = llm.Cache("teste-v2")
    r = llm_v2.classificar(cli, "sistema", "Pedido sobre imóvel da SPU.", "1", cache)
    assert r["n_chamadas"] == 2 and len(cli.pedidos) == 3
    assert [p["tool_choice"]["type"] for p in cli.pedidos] == ["auto", "auto", "none"]
    assert all(p["tool_choice"].get("disable_parallel_tool_use") for p in cli.pedidos[:2])
    assert llm.interpretar(r["resposta"])[0]["orgao"] == "MGI"
    assert r["chamadas_ferramenta"][0]["entrada"] == "SPU"
    # o resultado da ferramenta volta como tool_result ligado ao tool_use
    ultimo = cli.pedidos[2]["messages"]
    assert ultimo[-1]["content"][0]["type"] == "tool_result" and ultimo[-1]["content"][0]["tool_use_id"] == "t2"
    # o mesmo pedido de novo vem do cache, sem chamar a API
    r2 = llm_v2.classificar(cli, "sistema", "Pedido sobre imóvel da SPU.", "1", llm.Cache("teste-v2"))
    assert r2["do_cache"] and len(cli.pedidos) == 3


def test_corpo_v2_tem_ferramenta_estrita_e_mesmo_json_da_v1():
    c = llm_v2.corpo_base("s", "t")
    assert c["tools"][0]["strict"] is True and c["tools"][0]["input_schema"]["additionalProperties"] is False
    assert c["output_config"]["format"]["schema"] == llm.SCHEMA and c["thinking"] == {"type": "between_tools"}


def test_varredura_so_aceita_tabela_que_veio_do_siorg(tmp_path, monkeypatch):
    from triagem import varrer_versionados as v
    (tmp_path / "siorg").mkdir()
    (tmp_path / "siorg" / "estrutura_1.json").write_text(json.dumps({"unidades": [
        {"codigoUnidade": "https://x/id/unidade-organizacional/7", "nome": "Secretaria do Patrimônio da União", "sigla": "SPU"}]}))
    monkeypatch.setattr(config, "RAW", tmp_path)
    linha = {"codigo_siorg": 7, "nome": "Secretaria do Patrimônio da União", "sigla": "SPU", "orgao": "MGI",
             "relacao": "interna", "nivel": 1, "fonte": "estrutura_1"}
    ok = {"fonte": "SIORG", "unidades": [linha]}
    assert "Patrimônio" not in v._origem_siorg(json.dumps(ok))
    ruim = {"fonte": "SIORG", "unidades": [linha, dict(linha, codigo_siorg=8, nome="texto que não veio do SIORG")]}
    with pytest.raises(SystemExit):
        v._origem_siorg(json.dumps(ruim))
    # linha do SIORG, mas com uma coluna a mais (poderia esconder texto): falha
    with pytest.raises(SystemExit):
        v._origem_siorg(json.dumps({"fonte": "SIORG", "unidades": [dict(linha, obs="texto livre")]}))
    # relação fora do formato: falha
    with pytest.raises(SystemExit):
        v._origem_siorg(json.dumps({"fonte": "SIORG", "unidades": [dict(linha, relacao="qualquer texto")]}))
