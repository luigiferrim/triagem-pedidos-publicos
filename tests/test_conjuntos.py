"""Integridade dos conjuntos gerados por `make preparar`."""
import hashlib
from collections import Counter
from datetime import datetime

import pandas as pd
import pytest

from triagem import config
from triagem.pii import encontrar_pii_regex
from triagem.preparar import cotas_estratificadas, ler_jsonl

# Registrado no README. Se este teste falhar, o conjunto de teste foi alterado.
SHA256_TESTE = "d38c70d75a229b3d2e961b39a5b6d504ad226da644ba0d09d574aa5a9b261956"


@pytest.fixture(scope="module")
def conjuntos():
    return {
        "test": ler_jsonl(config.ARQ_TESTE),
        "dev": ler_jsonl(config.ARQ_DEV),
        "train": ler_jsonl(config.ARQ_TREINO),
        "train_amostra": ler_jsonl(config.ARQ_TREINO_AMOSTRA),
    }


def test_hash_do_teste_nao_mudou():
    atual = hashlib.sha256(config.ARQ_TESTE.read_bytes()).hexdigest()
    assert atual == SHA256_TESTE
    assert config.ARQ_HASH_TESTE.read_text().split()[0] == SHA256_TESTE


def test_tamanhos_e_estratificacao(conjuntos):
    assert len(conjuntos["test"]) == config.N_TESTE
    assert len(conjuntos["dev"]) == config.N_DEV
    assert len(conjuntos["train_amostra"]) == config.N_TREINO_AMOSTRA
    for nome in ("test", "dev"):
        cont = Counter(r["orgao"] for r in conjuntos[nome])
        assert len(cont) == config.N_ORGAOS
        assert min(cont.values()) >= config.MIN_POR_ORGAO_TESTE


def test_conjuntos_disjuntos(conjuntos):
    ids = {k: {r["id"] for r in v} for k, v in conjuntos.items()}
    assert not ids["test"] & ids["dev"]
    assert not ids["test"] & ids["train"]
    assert not ids["dev"] & ids["train"]
    assert ids["train_amostra"] <= ids["train"]


def test_sem_texto_repetido_entre_conjuntos(conjuntos):
    def norm(t):
        return " ".join(t.lower().split())
    treino = {norm(r["texto"]) for r in conjuntos["train"]}
    assert not any(norm(r["texto"]) in treino for r in conjuntos["test"] + conjuntos["dev"])


def test_separacao_temporal(conjuntos):
    def meses(nome):
        return {datetime.strptime(r["data_registro"], "%d/%m/%Y").month for r in conjuntos[nome]}
    assert meses("train") <= set(range(1, 9))
    assert meses("dev") <= {9, 10}
    assert meses("test") <= {11, 12}


def test_rotulo_nao_vem_de_sem_competencia(conjuntos):
    for nome in ("test", "dev", "train"):
        assert all(r["decisao"] != config.DECISAO_SEM_COMPETENCIA for r in conjuntos[nome])


def test_sem_dado_pessoal_estruturado_no_que_pode_ir_para_api(conjuntos):
    """Nada que case com as regex de CPF, e-mail, telefone etc. pode sobrar no texto."""
    sobras = [(nome, r["id"], encontrar_pii_regex(r["texto"]))
              for nome in ("test", "dev", "train_amostra") for r in conjuntos[nome]
              if encontrar_pii_regex(r["texto"])]
    assert sobras == []


def test_revisao_manual_as_cegas():
    rev = pd.read_csv(config.ARQ_REVISAO, dtype=str, encoding="utf-8-sig")
    gab = pd.read_csv(config.DATA / "revisao_manual_50_gabarito.csv", dtype=str, encoding="utf-8-sig")
    assert len(rev) == config.N_REVISAO_MANUAL
    assert "orgao_base" not in rev.columns and "orgao" not in rev.columns
    assert set(rev["id"]) == set(gab["id"])
    assert gab["orgao_base"].value_counts().min() == config.N_REVISAO_MANUAL // config.N_ORGAOS


def test_cotas_estratificadas_caso_conhecido():
    cotas = cotas_estratificadas({"A": 700, "B": 200, "C": 100}, total=100, minimo=25)
    assert sum(cotas.values()) == 100
    assert cotas["C"] == 25 and cotas["B"] == 25 and cotas["A"] == 50


def test_cotas_proporcionais_sem_minimo_ativo():
    cotas = cotas_estratificadas({"A": 500, "B": 300, "C": 200}, total=100, minimo=5)
    assert cotas == {"A": 50, "B": 30, "C": 20}


def test_auditoria_manual_consistente():
    import json
    d = json.loads((config.RESULTS / "auditoria_pii_manual.json").read_text())
    assert d["nao_eram_nome_de_pessoa"] == len(d["itens"])
    assert d["pct_excesso_de_mascara"] == round(100 * len(d["itens"]) / d["amostra"], 1)
    assert len({i["linha"] for i in d["itens"]}) == len(d["itens"])
