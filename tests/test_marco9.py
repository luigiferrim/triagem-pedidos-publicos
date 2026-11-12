"""Marco 9 (Prefeitura de São Paulo): leitura da resposta, congelamento e ausência de chamadas no teste antes dele."""
import json

import pytest

from triagem import config, marco9

ARQ = marco9.ARQ_CONGELADO


def test_interpretar_aceita_siglas_de_sp_e_recusa_as_federais():
    d, erro = marco9.interpretar('{"orgao": "sptrans", "trecho": "t", "justificativa": "j", "confianca": "média"}')
    assert erro is None and d["orgao"] == "SPTrans" and d["confianca"] == "media"
    assert marco9.interpretar('{"orgao": "INSS", "trecho": "t", "justificativa": "j", "confianca": "alta"}')[1] == "orgao_invalido"
    assert marco9.interpretar("```json\n{\"orgao\": \"SMS\", \"confianca\": \"alta\"}\n```")[0]["orgao"] == "SMS"


def test_schema_de_sp_nao_altera_o_da_v1():
    from triagem import llm
    assert llm.SCHEMA["properties"]["orgao"]["enum"] == llm.SIGLAS
    assert marco9.SCHEMA["properties"]["orgao"]["enum"] == marco9.SIGLAS
    assert marco9.corpo_requisicao("s", "t")["model"] == llm.MODELOS["sonnet"]


def test_prompt_cita_os_10_orgaos_e_nao_tem_dado_estruturado():
    from triagem import pii
    if not marco9.ARQ_TREINO.exists():
        pytest.skip("conjuntos de SP não gerados")
    s = marco9.sistema()
    assert all(f"- {o}:" in s for o in marco9.SIGLAS)
    assert not pii.encontrar_pii_regex(s, matricula=True)


def test_teste_de_sp_nao_repete_texto_do_treino_nem_do_dev():
    from triagem.preparar import ler_jsonl
    if not marco9.ARQ_TESTE.exists():
        pytest.skip("conjuntos de SP não gerados")
    norm = lambda t: " ".join(t.lower().split())
    teste = {norm(r["texto"]) for r in ler_jsonl(marco9.ARQ_TESTE)}
    outros = {norm(r["texto"]) for a in (marco9.ARQ_TREINO, marco9.ARQ_DEV) for r in ler_jsonl(a)}
    assert not teste & outros
    ids_dev = {r["id"] for r in ler_jsonl(marco9.ARQ_DEV)}
    assert not ids_dev & {r["id"] for r in ler_jsonl(marco9.ARQ_TREINO)}


@pytest.mark.skipif(not ARQ.exists(), reason="ainda não congelado")
def test_congelamento_confere_e_hash_no_readme():
    reg = json.loads(ARQ.read_text())
    assert reg["sha256_teste"] in (config.RAIZ / "README.md").read_text()
    if marco9.ARQ_TESTE.exists():
        marco9.conferir_congelado()


@pytest.mark.skipif(not ARQ.exists(), reason="ainda não congelado")
def test_nenhuma_chamada_no_teste_antes_do_commit_do_congelamento():
    """Toda chamada do Sonnet num pedido do teste de SP é posterior ao commit que criou o registro congelado
    (a data do commit, não a escrita dentro do arquivo). Sem chamadas ainda, o teste passa trivialmente."""
    import subprocess
    from datetime import datetime, timezone
    from triagem import llm
    from triagem.preparar import ler_jsonl
    if not marco9.ARQ_TESTE.exists():
        pytest.skip("conjunto de teste de SP ausente")
    ids = {r["id"] for r in ler_jsonl(marco9.ARQ_TESTE)}
    quando = [r["quando"] for r in llm.Cache(llm.MODELOS["sonnet"]).dados.values() if r["id"] in ids]
    commit = subprocess.run(["git", "log", "--diff-filter=A", "--format=%cI", "--", "results/marco9_congelado.json"],
                            cwd=config.RAIZ, capture_output=True, text=True).stdout.split()
    if not commit:
        assert not quando, "há chamada no teste sem registro congelado commitado"
        return
    t = datetime.fromisoformat(commit[-1]).astimezone(timezone.utc)
    assert all(datetime.fromisoformat(q) > t for q in quando)


@pytest.mark.skipif(not marco9.ARQ_AUDITORIA.exists(), reason="auditoria não gerada")
def test_teste_avaliado_nao_repete_texto_de_2024_nem_com_norma_forte():
    from triagem.preparar import ler_jsonl
    if not marco9.ARQ_TESTE.exists():
        pytest.skip("conjuntos de SP não gerados")
    k24 = {marco9.norma_forte(r["texto"]) for a in (marco9.ARQ_TREINO, marco9.ARQ_DEV) for r in ler_jsonl(a)}
    assert not [r["id"] for r in marco9.ler("teste") if marco9.norma_forte(r["texto"]) in k24]
    orgs = {}
    for r in marco9.ler("treino") + marco9.ler("dev"):
        orgs.setdefault(marco9.norma_forte(r["texto"]), set()).add(r["orgao_sigla"])
    assert all(len(o) == 1 for o in orgs.values())
