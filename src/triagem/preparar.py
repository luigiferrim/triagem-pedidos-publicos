"""Monta os conjuntos de treino, dev e teste a partir da base com texto.

Passos (justificativa em DADOS.md):
1. Federal, 10 órgãos com mais pedidos, rótulo confiável (sem "não tem competência").
2. Remove duplicatas de texto. Textos idênticos enviados a órgãos diferentes são descartados (rótulo ambíguo).
3. Separação temporal: treino = jan-ago, dev = set-out, teste = nov-dez (data de registro).
4. Dev e teste: 500 pedidos cada, estratificados por órgão (proporcional, mínimo 25),
   no máximo 5 pedidos por solicitante identificado.
5. Mascara dados pessoais em tudo que é salvo.

O teste é congelado: se data/test.jsonl já existe, os ids dele são reaproveitados e o hash é conferido.
"""
import hashlib
import json
from collections import Counter

import numpy as np
import pandas as pd

from triagem import config, dados, orgaos, pii

MAX_POR_SOLICITANTE = 5
PERIODOS = {"train": (1, 8), "dev": (9, 10), "test": (11, 12)}


def _rng(nome: str) -> np.random.Generator:
    """Um gerador por conjunto: o sorteio do dev não depende de o teste ter sido sorteado ou reaproveitado."""
    return np.random.default_rng([config.SEED, sum(nome.encode())])


def _texto(df: pd.DataFrame) -> pd.Series:
    return (df["ResumoSolicitacao"] + "\n" + df["DetalhamentoSolicitacao"]).str.strip()


def _normalizar(s: pd.Series) -> pd.Series:
    return s.str.lower().str.replace(r"\s+", " ", regex=True).str.strip()


def cotas_estratificadas(contagem: dict[str, int], total: int, minimo: int) -> dict[str, int]:
    """Cota por órgão proporcional ao volume, com mínimo, somando exatamente `total`
    (método dos maiores restos). Órgãos ordenados pelo nome para ser determinístico."""
    nomes = sorted(contagem)
    soma = sum(contagem.values())
    cotas = {n: max(minimo, int(total * contagem[n] / soma)) for n in nomes}
    restos = sorted(nomes, key=lambda n: (-(total * contagem[n] / soma) % 1, n))
    i = 0
    while sum(cotas.values()) < total:
        cotas[restos[i % len(restos)]] += 1
        i += 1
    while sum(cotas.values()) > total:
        maior = max(nomes, key=lambda n: (cotas[n] - minimo, n))
        cotas[maior] -= 1
    for n in nomes:
        if cotas[n] > contagem[n]:
            raise ValueError(f"cota de {n} ({cotas[n]}) maior que o disponível ({contagem[n]})")
    return cotas


def amostrar(df: pd.DataFrame, total: int, minimo: int, rng: np.random.Generator) -> pd.DataFrame:
    """Amostra estratificada por órgão, com teto de pedidos por solicitante identificado."""
    df = df.sort_values("IdPedido").copy()
    df["_u"] = rng.random(len(df))
    df = df.sort_values(["_u", "IdPedido"])
    identificado = df["IdSolicitante"] != "0"
    ordem_no_solicitante = df.groupby("IdSolicitante").cumcount()
    elegivel = df[~identificado | (ordem_no_solicitante < MAX_POR_SOLICITANTE)]
    cotas = cotas_estratificadas(elegivel["OrgaoDestinatario"].value_counts().to_dict(), total, minimo)
    partes = [elegivel[elegivel["OrgaoDestinatario"] == o].head(q) for o, q in cotas.items()]
    return pd.concat(partes).drop(columns="_u")


def _registro(row, texto_mascarado: str) -> dict:
    return {
        "id": str(row.IdPedido),
        "orgao": row.OrgaoDestinatario,
        "orgao_sigla": orgaos.sigla(row.OrgaoDestinatario),
        "texto": texto_mascarado,
        "reencaminhado": row.FoiReencaminhado == "Sim",
        "decisao": row.Decisao,
        "data_registro": row.DataRegistro,
    }


def escrever_jsonl(caminho, registros: list[dict]) -> None:
    registros = sorted(registros, key=lambda r: int(r["id"]))
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def ler_jsonl(caminho) -> list[dict]:
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def sha256(caminho) -> str:
    return hashlib.sha256(open(caminho, "rb").read()).hexdigest()


def main() -> None:
    passos = {}

    filtrada = dados.ler_filtrada()
    lista = orgaos.top_orgaos(filtrada)
    base = filtrada[(filtrada["Esfera"] == "Federal") & filtrada["OrgaoDestinatario"].isin(lista)].copy()
    passos["base_com_texto_10_orgaos"] = len(base)

    # Concentração de solicitantes (motivo do teto por solicitante e da separação temporal).
    ident = base[base["IdSolicitante"] != "0"]["IdSolicitante"].value_counts()
    frequentes = ident[ident >= 10]
    solicitantes = {
        "pedidos_solicitante_nao_identificado": int((base["IdSolicitante"] == "0").sum()),
        "solicitantes_identificados": int(len(ident)),
        "solicitantes_com_10_ou_mais_pedidos": int(len(frequentes)),
        "pedidos_desses_solicitantes": int(frequentes.sum()),
        "pct_da_base_10_orgaos": round(100 * frequentes.sum() / len(base), 1),
        "max_pedidos_de_um_solicitante": int(ident.max()),
    }
    confiaveis = filtrada[(filtrada["Esfera"] == "Federal") & orgaos.rotulo_confiavel(filtrada)]
    ranking = [{"posicao": i + 1, "orgao": orgaos.sigla(k), "pedidos": int(v)}
               for i, (k, v) in enumerate(sorted(confiaveis["OrgaoDestinatario"].value_counts().items(),
                                                 key=lambda kv: (-kv[1], kv[0]))[:12])]

    fora = base[~orgaos.rotulo_confiavel(base)].copy()
    pool = base[orgaos.rotulo_confiavel(base)].copy()
    passos["sem_competencia_separados"] = len(fora)

    pool["_texto"] = _texto(pool)
    pool["_norm"] = _normalizar(pool["_texto"])
    n_orgaos_por_texto = pool.groupby("_norm")["OrgaoDestinatario"].transform("nunique")
    passos["descartados_texto_em_orgaos_diferentes"] = int((n_orgaos_por_texto > 1).sum())
    pool = pool[n_orgaos_por_texto == 1]
    antes = len(pool)
    pool = pool.sort_values("IdPedido", key=lambda s: s.astype(int)).drop_duplicates("_norm", keep="first")
    passos["descartados_duplicatas_mesmo_orgao"] = antes - len(pool)
    passos["pool_final"] = len(pool)

    mes = pd.to_datetime(pool["DataRegistro"], format="%d/%m/%Y").dt.month
    periodo = {nome: pool[mes.between(a, b)] for nome, (a, b) in PERIODOS.items()}

    if config.ARQ_TESTE.exists():
        esperado = config.ARQ_HASH_TESTE.read_text().split()[0]
        if sha256(config.ARQ_TESTE) != esperado:
            raise SystemExit("ERRO: data/test.jsonl foi alterado (hash não confere). Não continuo.")
        ids_teste = {r["id"] for r in ler_jsonl(config.ARQ_TESTE)}
        teste = periodo["test"][periodo["test"]["IdPedido"].isin(ids_teste)]
        if len(teste) != len(ids_teste):
            raise SystemExit("ERRO: ids do teste congelado não estão todos na base atual.")
        teste_congelado = True
    else:
        teste = amostrar(periodo["test"], config.N_TESTE, config.MIN_POR_ORGAO_TESTE, _rng("test"))
        teste_congelado = False
    dev = amostrar(periodo["dev"], config.N_DEV, config.MIN_POR_ORGAO_TESTE, _rng("dev"))
    treino = periodo["train"]
    treino_amostra = amostrar(treino, config.N_TREINO_AMOSTRA, 50, _rng("train_amostra"))

    # Mascara tudo de uma vez (o NER é o passo lento).
    todos = pd.concat([treino, dev, teste, fora.assign(_texto=_texto(fora))])
    todos = todos[~todos.index.duplicated()]
    contagem = Counter()
    mascarados = dict(zip(todos.index, pii.mascarar(todos["_texto"].tolist(), contagem)))

    def regs(df):
        return [_registro(r, mascarados[i]) for i, r in zip(df.index, df.itertuples())]

    if not teste_congelado:
        escrever_jsonl(config.ARQ_TESTE, regs(teste))
        config.ARQ_HASH_TESTE.write_text(f"{sha256(config.ARQ_TESTE)}  test.jsonl\n")
    escrever_jsonl(config.ARQ_DEV, regs(dev))
    escrever_jsonl(config.ARQ_TREINO, regs(treino))
    escrever_jsonl(config.ARQ_TREINO_AMOSTRA, regs(treino_amostra))
    escrever_jsonl(config.ARQ_FORA_COMPETENCIA, regs(fora))

    # Revisão manual às cegas: 5 por órgão, do treino amostrado. O rótulo da base fica num arquivo à parte.
    rev = pd.concat([
        treino_amostra[treino_amostra["OrgaoDestinatario"] == o].sample(
            config.N_REVISAO_MANUAL // len(lista), random_state=config.SEED)
        for o in sorted(lista)
    ]).sample(frac=1, random_state=config.SEED)
    pd.DataFrame({
        "id": rev["IdPedido"].values,
        "texto": [mascarados[i] for i in rev.index],
        "orgao_luigi": "",
        "certeza_1a3": "",
        "observacao": "",
    }).to_csv(config.ARQ_REVISAO, index=False, encoding="utf-8-sig")
    pd.DataFrame({"id": rev["IdPedido"].values, "orgao_base": [orgaos.sigla(o) for o in rev["OrgaoDestinatario"]]}) \
        .to_csv(config.DATA / "revisao_manual_50_gabarito.csv", index=False, encoding="utf-8-sig")

    def por_orgao(df):
        return {orgaos.sigla(k): int(v) for k, v in sorted(df["OrgaoDestinatario"].value_counts().items())}

    def max_solic(df):
        ident = df[df["IdSolicitante"] != "0"]
        return int(ident["IdSolicitante"].value_counts().max()) if len(ident) else 0

    resumo = {
        "seed": config.SEED,
        "orgaos": [{"sigla": orgaos.sigla(o), "nome": o} for o in lista],
        "ranking_base_com_texto_rotulo_confiavel": ranking,
        "passos": passos,
        "solicitantes_base_10_orgaos": solicitantes,
        "disponivel_por_periodo": {k: len(v) for k, v in periodo.items()},
        "conjuntos": {
            nome: {"n": len(df), "por_orgao": por_orgao(df),
                   "reencaminhados": int((df["FoiReencaminhado"] == "Sim").sum()),
                   "max_pedidos_mesmo_solicitante": max_solic(df)}
            for nome, df in [("test", teste), ("dev", dev), ("train", treino),
                             ("train_amostra", treino_amostra), ("fora_competencia", fora)]
        },
        "pii_mascaramentos": dict(sorted(contagem.items())),
        "teste_congelado_reaproveitado": teste_congelado,
        "sha256_test": sha256(config.ARQ_TESTE),
    }
    (config.RESULTS / "preparacao.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: resumo[k] for k in ("passos", "solicitantes_base_10_orgaos", "disponivel_por_periodo",
                                         "pii_mascaramentos", "sha256_test")},
                     ensure_ascii=False, indent=2))
    for nome, c in resumo["conjuntos"].items():
        print(nome, c["n"], c["por_orgao"], "reenc:", c["reencaminhados"], "max/solic:", c["max_pedidos_mesmo_solicitante"])


if __name__ == "__main__":
    main()
