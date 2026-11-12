"""Marco 9: a mesma triagem numa prefeitura (São Paulo, base do e-SIC municipal).

Fonte: dados.prefeitura.sp.gov.br, conjunto "Pedidos de informação protocolados à Prefeitura via sistema e-SIC"
(Controladoria Geral do Município, anonimizado pela prefeitura, CC0). Os arquivos ficam em data/raw/sp/ (fora do git).

1. Órgãos: os 10 com mais pedidos em 2025. Rótulo: o órgão que respondeu (o final, depois de um encaminhamento).
   Pedidos de outros órgãos ficam fora. Textos idênticos em órgãos diferentes são descartados.
2. Conjuntos (texto mascarado com a máscara do projeto, matricula=True):
   - teste: 500 pedidos de 2025, estratificado (mínimo 25 por órgão), sem textos iguais a algum de 2024;
   - dev: 300 pedidos de 2024, estratificado (mínimo 15), para escolher o limiar e ajustar o prompt;
   - treino: o resto de 2024 (ML e exemplos do prompt);
   - piloto: 20 pedidos do treino (2 por órgão), fora dos exemplos do prompt, só para achar bug.
   A base de SP não identifica o solicitante. No dev, no teste e no piloto, entram no máximo 5 pedidos com o
   mesmo "modelo de texto" (os mesmos 120 primeiros caracteres normalizados).
3. ML: TF-IDF + regressão logística, treinado no treino de SP; C escolhido no dev.
4. Prompt: o da v1 (mesmas regras, mesmo schema), com os 10 órgãos de SP e 2 exemplos por órgão do treino.
5. Dor municipal (sem custo): pedidos com "Encaminhamento Deferido" / pedidos, por ano.
   - Tabelas do sistema e-SIC: pedidos abertos de 2012 a jan/2020 (os arquivos foram atualizados em 2023).
   - Bases anuais de 2021 a 2024 (uma linha por movimentação, com o status). A de 2025 não tem status.

Uso:
  python -m triagem.marco9 baixar | dor | preparar | auditar | ml | prompt | estimar | congelar
  python -m triagem.marco9 rodar --conjunto piloto|dev|teste
  python -m triagem.marco9 avaliar --conjunto piloto|dev|teste
"""
import argparse
import hashlib
import json
import random
import re
import urllib.request
from collections import Counter

import numpy as np
import pandas as pd

from triagem import config, llm, pii
from triagem.preparar import cotas_estratificadas, ler_jsonl, sha256

DIR_RAW = config.RAW / "sp"
CKAN = "https://dados.prefeitura.sp.gov.br/dataset"
PEDIDOS = f"{CKAN}/0683c3e5-8ffc-4e89-b903-c36567165a00/resource"
ESIC = f"{CKAN}/32836e19-1def-4bf5-aaf4-53bee558541e/resource"
ARQUIVOS = {
    "pedidos_2025.csv": f"{PEDIDOS}/ff89d143-248d-470a-bf80-f2820b194979/download/base-esic-pedidos-quali-2025.csv",
    "pedidos_2024.csv": f"{PEDIDOS}/e7a201b1-3ff0-485f-8545-56983143717c/download/base-de-pedidos-de-informacao-2024.csv",
    "pedidos_2023.csv": f"{PEDIDOS}/7918376b-7671-4be2-b797-b61b17e68760/download/base-de-pedidos-de-informacao-2023.csv",
    "pedidos_2022.csv": f"{PEDIDOS}/90da0b44-93aa-4984-a6a3-2f0f64e14b00/download/e-sic_anon2022-002.csv",
    "pedidos_2021.csv": f"{PEDIDOS}/f5d4e997-d62a-4bc3-9403-97886b875c7b/download/pedidosrespondidosanonimizadosgeral2021.csv",
    "dicionario.csv": f"{PEDIDOS}/cd941a2d-76c5-49eb-a001-0f4d2313bdfc/download/dicionariodados.csv",
    "esic_pedidos.csv": f"{ESIC}/6314a7f3-12c6-4a72-bb7d-6be097afa626/download/tabela-de-pedidos-base-de-dados.csv",
    "esic_atendimento.csv": f"{ESIC}/9da1ab1c-1f3c-48c5-835f-df976b04c807/download/e-sicatendimentopedidos.csv",
    "esic_status.csv": f"{ESIC}/1df57651-ca16-49d7-888c-f2a155fa222b/download/e-sicstatuspedidos.csv",
}
ARQ_MANIFESTO = config.RESULTS / "marco9_manifesto.json"
ARQ_DOR = config.RESULTS / "marco9_dor.json"
ARQ_CONJUNTOS = config.RESULTS / "marco9_conjuntos.json"
ARQ_ML = config.RESULTS / "marco9_ml.json"
ARQ_ESTIMATIVA = config.RESULTS / "estimativa_custo_marco9.json"
ARQ_TREINO = config.DATA / "sp_treino.jsonl"
ARQ_DEV = config.DATA / "sp_dev.jsonl"
ARQ_TESTE = config.DATA / "sp_teste.jsonl"
ARQ_PILOTO = config.DATA / "sp_piloto.jsonl"

N_TESTE, MIN_TESTE = 500, 25
N_DEV, MIN_DEV = 300, 15
N_PILOTO = 20
MAX_POR_MODELO_DE_TEXTO, PREFIXO_MODELO = 5, 120
STATUS_ENCAMINHAMENTO = "encaminhamento deferido"     # código 18 no sistema e-SIC
GRADE_C = [1, 3, 10, 30, 100, 300, 1000, 3000, 10000]   # ampliada duas vezes: a escolha no dev caiu na borda (100, depois 1000)
ENC = "cp1252"

# Descrição de uma linha de cada órgão (conhecimento público sobre a estrutura da prefeitura, não tirado dos pedidos).
ORGAOS = {
    "CET": "Companhia de Engenharia de Tráfego: operação do trânsito, sinalização, semáforos, radares e fiscalização de trânsito, Zona Azul, contagem de veículos, acidentes.",
    "SF": "Secretaria Municipal da Fazenda: IPTU, ISS, ITBI, taxas, dívida ativa, Nota Fiscal Paulistana, orçamento e finanças do município.",
    "SMC": "Secretaria Municipal de Cultura e Economia Criativa: bibliotecas, teatros e centros culturais municipais, editais e fomento à cultura, eventos culturais, patrimônio histórico.",
    "SME": "Secretaria Municipal de Educação: escolas municipais (EMEF, EMEI, CEI), creches, vagas e matrículas, professores, alimentação e material escolar.",
    "SMS": "Secretaria Municipal da Saúde: UBS, AMA, hospitais municipais, consultas e exames, vacinação, vigilância em saúde, medicamentos, profissionais da saúde.",
    "SMSU": "Secretaria Municipal de Segurança Urbana: Guarda Civil Metropolitana (GCM), Defesa Civil, videomonitoramento, proteção de próprios municipais.",
    "SMSUB": "Secretaria Municipal das Subprefeituras: zeladoria dos bairros (poda, tapa-buraco, limpeza de bueiros, calçadas), feiras livres, comércio ambulante, fiscalização local nas subprefeituras.",
    "SMUL": "Secretaria Municipal de Urbanismo e Licenciamento: alvarás e licenças de obras e de funcionamento, zoneamento, Plano Diretor, regularização de edificações, habite-se.",
    "SPTrans": "São Paulo Transporte S/A: ônibus municipais, linhas e itinerários, Bilhete Único, tarifas, frota, contratos com as empresas de ônibus, terminais.",
    "SVMA": "Secretaria Municipal do Verde e do Meio Ambiente: parques municipais, manejo e corte de árvores, licenciamento ambiental, áreas verdes, fauna, poluição.",
}
SIGLAS = sorted(ORGAOS)
SCHEMA = llm.SCHEMA | {"properties": llm.SCHEMA["properties"] | {"orgao": {"type": "string", "enum": SIGLAS}}}


def sigla(nome) -> str:
    return re.split(r"\s+[–-]\s+", str(nome), maxsplit=1)[0].strip()


def _norm(s: pd.Series) -> pd.Series:
    return s.fillna("").str.lower().str.replace(r"\s+", " ", regex=True).str.strip()


# ---------------------------------------------------------------- download e manifesto

def baixar() -> dict:
    DIR_RAW.mkdir(parents=True, exist_ok=True)
    manifesto = {}
    for nome, url in ARQUIVOS.items():
        destino = DIR_RAW / nome
        if not destino.exists():
            print("baixando", nome)
            urllib.request.urlretrieve(url, destino)
        manifesto[nome] = {"url": url, "sha256": sha256(destino), "bytes": destino.stat().st_size}
    saida = {"fonte": "https://dados.prefeitura.sp.gov.br (CKAN da Prefeitura de São Paulo), licença CC0",
             "baixado_em": "2026-11-12", "arquivos": manifesto}
    ARQ_MANIFESTO.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v["sha256"][:12] for k, v in manifesto.items()}, indent=1))
    return saida


# ---------------------------------------------------------------- leitura das bases

def _movimentacoes(ano: int) -> pd.DataFrame:
    """Bases de 2021 a 2024: uma linha por movimentação do pedido. Ids corrompidos pela anonimização são descartados."""
    df = pd.read_csv(DIR_RAW / f"pedidos_{ano}.csv", sep=";", encoding=ENC, dtype=str)
    df = df[df["cd_pedido"].fillna("").str.fullmatch(r"\d+")].copy()
    df["_status"] = df["dc_status_pedido"].str.strip().str.lower()
    return df


def pedidos_2024() -> pd.DataFrame:
    """Um registro por pedido de 2024: texto, órgão final e se houve encaminhamento deferido."""
    mov = _movimentacoes(2024)
    enc = set(mov.loc[mov["_status"] == STATUS_ENCAMINHAMENTO, "cd_pedido"])
    if (mov.groupby("cd_pedido")["nm_orgao"].nunique() > 1).any():
        raise SystemExit("pedido de 2024 com mais de um órgão: o rótulo não seria único")
    txt = mov.dropna(subset=["dc_pedido"]).drop_duplicates("cd_pedido")
    return pd.DataFrame({"id": "sp-" + txt["cd_pedido"], "orgao": txt["nm_orgao"].str.replace(r"\s+", " ", regex=True),
                         "sigla": txt["nm_orgao"].map(sigla), "texto": txt["dc_pedido"].str.strip(),
                         "reencaminhado": txt["cd_pedido"].isin(enc), "ano": 2024, "natureza": None})


def pedidos_2025() -> pd.DataFrame:
    """Base de 2025 (uma linha por pedido, sem status; linhas vazias de enchimento e protocolos corrompidos saem)."""
    df = pd.read_csv(DIR_RAW / "pedidos_2025.csv", sep=";", encoding=ENC, dtype=str)
    df = df[df["PROTOCOLO"].fillna("").str.fullmatch(r"\d+")].drop_duplicates()
    if df["PROTOCOLO"].duplicated().any():
        raise SystemExit("protocolo repetido em 2025")
    return pd.DataFrame({"id": "sp-" + df["PROTOCOLO"], "orgao": df["ÓRGÃO"].str.replace(r"\s+", " ", regex=True),
                         "sigla": df["ÓRGÃO"].map(sigla), "texto": df["PEDIDO"].fillna("").str.strip(),
                         "reencaminhado": None, "ano": 2025, "natureza": df["NATUREZA"]})


def top_orgaos(df25: pd.DataFrame, n: int = 10) -> list[str]:
    cont = df25["sigla"].value_counts()
    return [s for s, _ in sorted(cont.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


# ---------------------------------------------------------------- dor municipal

_MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                                      "setembro", "outubro", "novembro", "dezembro"], 1)}


def _data_extenso(s: str) -> pd.Timestamp:
    m = re.search(r"(\d+) de (\w+) de (\d{4})", s)
    return pd.Timestamp(int(m[3]), _MESES[m[2]], int(m[1]))


def _taxa(g: pd.DataFrame) -> dict:
    from triagem.metricas import intervalo_wilson
    n, k = len(g), int(g["enc"].sum())
    return {"pedidos": n, "encaminhamento_deferido": k, "taxa": round(k / n, 4) if n else None,
            "ic95": list(intervalo_wilson(k, n)) if n else None}


def dor() -> dict:
    top = top_orgaos(pedidos_2025())
    # 1) tabelas do sistema e-SIC (pedidos abertos de ago/2012 a jan/2020)
    pe = pd.read_csv(DIR_RAW / "esic_pedidos.csv", sep=";", encoding=ENC, dtype=str)
    at = pd.read_csv(DIR_RAW / "esic_atendimento.csv", sep=";", encoding=ENC, dtype=str)
    pe["ano"] = pe["dt_abertura_pedido"].map(_data_extenso).dt.year
    pe["sigla"] = pe["dbo_orgao.nm_orgao"].map(sigla)
    pe["enc"] = pe["cd_pedido"].isin(set(at.loc[at["cd_status_atendimento_pedido"] == "18", "cd_pedido"]))
    datas = pe["dt_abertura_pedido"].map(_data_extenso)
    sistema = {"periodo_dos_pedidos": [str(datas.min().date()), str(datas.max().date())],
               "por_ano": {int(a): {"todos": _taxa(g), "10_orgaos": _taxa(g[g["sigla"].isin(top)])}
                           for a, g in pe.groupby("ano") if 2013 <= a <= 2019},
               "nota": "2012 (início do sistema, sem encaminhamentos registrados) e 2020 (7 pedidos) ficam fora; SMUL não existe com essa sigla nessas tabelas"}
    # 2) bases anuais com o status de cada movimentação
    anuais = {}
    for ano in (2021, 2022, 2023, 2024):
        mov = _movimentacoes(ano)
        enc = set(mov.loc[mov["_status"] == STATUS_ENCAMINHAMENTO, "cd_pedido"])
        g = mov.groupby("cd_pedido")["nm_orgao"].first().map(sigla).rename("sigla").to_frame()
        g["enc"] = g.index.isin(enc)
        por_org = {o: _taxa(g[g["sigla"] == o]) for o in top}
        anuais[ano] = {"todos": _taxa(g), "10_orgaos": _taxa(g[g["sigla"].isin(top)]),
                       "por_orgao": {o: {"pedidos": v["pedidos"], "taxa": v["taxa"]} for o, v in por_org.items()}}
    saida = {
        "definicao": "pedidos com pelo menos uma movimentação 'Encaminhamento Deferido' (status 18) / pedidos; o órgão é o final",
        "orgaos": top,
        "bases_anuais_2021_2024": anuais,
        "tabelas_do_sistema_esic_2013_2019": sistema,
        "nota": ("encaminhamento deferido = a CGM aceitou transferir o pedido a outro órgão; pedidos que o órgão respondeu "
                 "sem pedir transferência não entram. A base de 2025 não tem status. É a régua municipal equivalente "
                 "aos 'reencaminhados' do Fala.BR."),
    }
    ARQ_DOR.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    for a, v in anuais.items():
        print(a, v["todos"]["taxa"], "| 10 órgãos", v["10_orgaos"]["taxa"], v["10_orgaos"]["pedidos"])
    for a, v in sistema["por_ano"].items():
        print(a, v["todos"]["taxa"], "| 10 órgãos", v["10_orgaos"]["taxa"])
    return saida


# ---------------------------------------------------------------- conjuntos

def _amostrar(df: pd.DataFrame, total: int, minimo: int, nome: str) -> pd.DataFrame:
    """Estratificada por órgão, no máximo MAX_POR_MODELO_DE_TEXTO por modelo de texto, seed fixa."""
    rng = np.random.default_rng([config.SEED, sum(f"sp_{nome}".encode())])
    df = df.sort_values("id").copy()
    df["_u"] = rng.random(len(df))
    df = df.sort_values(["_u", "id"])
    df = df[df.groupby(df["_norm"].str[:PREFIXO_MODELO]).cumcount() < MAX_POR_MODELO_DE_TEXTO]
    cotas = cotas_estratificadas(df["sigla"].value_counts().to_dict(), total, minimo)
    return pd.concat([df[df["sigla"] == o].head(q) for o, q in cotas.items()]).drop(columns="_u")


def _limpar(df: pd.DataFrame, top: list[str]) -> tuple[pd.DataFrame, dict]:
    passos = {"pedidos": len(df)}
    df = df[df["sigla"].isin(top)].copy()
    passos["nos_10_orgaos"] = len(df)
    df = df[df["texto"].str.len() >= 10]
    passos["com_texto"] = len(df)
    df["_norm"] = _norm(df["texto"])
    amb = df.groupby("_norm")["sigla"].transform("nunique") > 1
    passos["texto_igual_em_orgaos_diferentes"] = int(amb.sum())
    df = df[~amb].sort_values("id").drop_duplicates("_norm", keep="first")
    passos["sem_duplicatas"] = len(df)
    return df, passos


def escrever_jsonl(caminho, registros: list[dict]) -> None:
    """Como preparar.escrever_jsonl, com ids 'sp-<protocolo>' ordenados pelo número."""
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        for r in sorted(registros, key=lambda r: int(r["id"][3:])):
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def _registros(df: pd.DataFrame, contagem: Counter) -> list[dict]:
    textos = pii.mascarar(df["texto"].tolist(), contagem, matricula=True)
    return [{"id": r.id, "orgao": r.orgao, "orgao_sigla": r.sigla, "texto": t, "reencaminhado": r.reencaminhado,
             "ano": int(r.ano)} | ({"natureza": r.natureza} if r.natureza else {})
            for r, t in zip(df.itertuples(), textos)]


def escolher_exemplos(treino: list[dict]) -> list[dict]:
    """2 pedidos por órgão do treino, de tamanho médio, com seed fixa (mesmo critério da v1)."""
    rng = random.Random(config.SEED)
    exemplos = []
    for org in SIGLAS:
        cand = sorted((r for r in treino if r["orgao_sigla"] == org and 150 <= len(r["texto"]) <= 600),
                      key=lambda r: int(r["id"][3:]))
        exemplos += rng.sample(cand, llm.EXEMPLOS_POR_ORGAO)
    rng.shuffle(exemplos)
    return exemplos


def preparar() -> dict:
    if ARQ_TESTE.exists():
        raise SystemExit(f"{ARQ_TESTE} já existe: os conjuntos de SP não são refeitos")
    d25, d24 = pedidos_2025(), pedidos_2024()
    top = top_orgaos(d25)
    if sorted(top) != SIGLAS:
        raise SystemExit(f"os 10 maiores de 2025 mudaram: {top}")
    d24, passos24 = _limpar(d24, top)
    d25, passos25 = _limpar(d25, top)
    iguais = d25["_norm"].isin(set(d24["_norm"]))
    passos25["iguais_a_algum_de_2024"] = int(iguais.sum())
    d25 = d25[~iguais]
    teste = _amostrar(d25, N_TESTE, MIN_TESTE, "teste")
    dev = _amostrar(d24, N_DEV, MIN_DEV, "dev")
    treino = d24[~d24["id"].isin(set(dev["id"]))]
    contagem = Counter()
    regs = {"teste": _registros(teste, contagem), "dev": _registros(dev, contagem), "treino": _registros(treino, contagem)}
    ex = {e["id"] for e in escolher_exemplos(regs["treino"])}
    pool_piloto = treino[~treino["id"].isin(ex)]
    piloto_ids = set(_amostrar(pool_piloto, N_PILOTO, 2, "piloto")["id"])
    regs["piloto"] = [r for r in regs["treino"] if r["id"] in piloto_ids]
    for nome, arq in (("teste", ARQ_TESTE), ("dev", ARQ_DEV), ("treino", ARQ_TREINO), ("piloto", ARQ_PILOTO)):
        escrever_jsonl(arq, regs[nome])
    resumo = lambda rs: {"n": len(rs), "por_orgao": dict(sorted(Counter(r["orgao_sigla"] for r in rs).items())),
                         "encaminhamento_deferido": sum(bool(r["reencaminhado"]) for r in rs),
                         "caracteres_mediana": int(np.median([len(r["texto"]) for r in rs]))}
    saida = {
        "orgaos": top, "passos_2024": passos24, "passos_2025": passos25,
        "conjuntos": {k: resumo(v) for k, v in regs.items()},
        "teste_natureza": dict(Counter(r.get("natureza") for r in regs["teste"])),
        "teto_por_modelo_de_texto": f"no máximo {MAX_POR_MODELO_DE_TEXTO} pedidos com os mesmos {PREFIXO_MODELO} primeiros caracteres normalizados (dev, teste, piloto)",
        "mascara": "pii.mascarar(..., matricula=True)", "pii_mascarada": dict(contagem),
        "sha256": {k: sha256(a) for k, a in (("teste", ARQ_TESTE), ("dev", ARQ_DEV), ("treino", ARQ_TREINO), ("piloto", ARQ_PILOTO))},
    }
    ARQ_CONJUNTOS.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in saida.items() if k != "conjuntos"} | {"n": {k: v["n"] for k, v in saida["conjuntos"].items()}},
                     ensure_ascii=False, indent=1))
    return saida


# ---------------------------------------------------------------- exclusões (correção da verificação)

ARQ_AUDITORIA = config.RESULTS / "marco9_auditoria.json"


def norma_forte(texto: str) -> str:
    """Sem caixa, sem acento, só letras e números: 'texto igual' passa a pegar diferenças de acento e pontuação."""
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", t))


def auditar() -> dict:
    """A limpeza do `preparar` comparava textos só depois de minúsculas e espaços. Com a norma forte, aplica as mesmas
    regras já aprovadas, sem sortear de novo (os conjuntos e o prompt ficam iguais; o cache do dev continua valendo):
    - texto igual em órgãos diferentes (2024: treino + dev) -> fora do treino do ML e da avaliação do dev;
    - texto do teste igual a algum de 2024 -> fora da avaliação do teste.
    Também registra ressalvas: pedidos do teste sem resposta na base e quase gêmeos entre dev e treino."""
    from collections import defaultdict
    tr, dv, te = ler_jsonl(ARQ_TREINO), ler_jsonl(ARQ_DEV), ler_jsonl(ARQ_TESTE)
    orgs, ids = defaultdict(set), defaultdict(list)
    for r in tr + dv:
        k = norma_forte(r["texto"])
        orgs[k].add(r["orgao_sigla"])
        ids[k].append(r["id"])
    conflito = sorted({i for k, o in orgs.items() if len(o) > 1 for i in ids[k]}, key=lambda i: int(i[3:]))
    teste_igual = sorted((r["id"] for r in te if norma_forte(r["texto"]) in orgs), key=lambda i: int(i[3:]))
    exemplos = {e["id"] for e in escolher_exemplos(tr)}
    if exemplos & set(conflito):
        raise SystemExit("um exemplo do prompt cairia nas exclusões: o prompt mudaria")
    # ressalvas (só contagens)
    d25 = pedidos_2025().set_index("id")
    resposta = pd.read_csv(DIR_RAW / "pedidos_2025.csv", sep=";", encoding=ENC, dtype=str)
    resposta = resposta[resposta["PROTOCOLO"].fillna("").str.fullmatch(r"\d+")].drop_duplicates()
    sem_resp = set("sp-" + resposta.loc[resposta["RESPOSTA"].fillna("").str.strip() == "", "PROTOCOLO"])
    te_ids = [r["id"] for r in te]

    def cinco(t):
        w = norma_forte(t).split()
        return {tuple(w[i:i + 5]) for i in range(max(1, len(w) - 4))}
    g_tr = [cinco(r["texto"]) for r in tr]
    gemeos = {}
    for nome, rs in (("dev", dv), ("teste", te)):
        n = 0
        for r in rs:
            a = cinco(r["texto"])
            if any(len(a & b) / len(a | b) >= 0.8 for b in g_tr if b):
                n += 1
        gemeos[nome] = n
    saida = {
        "norma": "minúsculas, sem acento, só letras e números (a do preparar só juntava espaços e tirava maiúsculas)",
        "excluir_do_treino_do_ml_e_do_dev": conflito,
        "conflitos_no_dev": [i for i in conflito if i in {r["id"] for r in dv}],
        "excluir_do_teste": teste_igual,
        "exemplos_do_prompt_afetados": 0,
        "ressalvas": {
            "teste_sem_resposta_na_base_2025": {"n": sum(i in sem_resp for i in te_ids), "de": len(te_ids),
                                                "por_orgao": dict(Counter(d25.loc[i, "sigla"] for i in te_ids if i in sem_resp).most_common())},
            "quase_gemeos_no_treino": {"criterio": "Jaccard de 5-gramas (norma forte) >= 0,8 com algum pedido do treino",
                                       "dev": gemeos["dev"], "teste": gemeos["teste"]},
        },
    }
    ARQ_AUDITORIA.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


def ler(conjunto: str) -> list[dict]:
    """O conjunto sem as exclusões da auditoria (o arquivo em data/ não muda; o prompt usa o treino inteiro)."""
    arq = {"treino": ARQ_TREINO, "dev": ARQ_DEV, "teste": ARQ_TESTE, "piloto": ARQ_PILOTO}[conjunto]
    aud = json.loads(ARQ_AUDITORIA.read_text())
    fora = set(aud["excluir_do_teste"] if conjunto == "teste" else aud["excluir_do_treino_do_ml_e_do_dev"])
    return [r for r in ler_jsonl(arq) if r["id"] not in fora]


# ---------------------------------------------------------------- ML

def modelo_ml():
    """ML de SP: treinado no treino de SP (sem as exclusões) com o C escolhido no dev (results/marco9_ml.json)."""
    from triagem import ml
    c = json.loads(ARQ_ML.read_text())["c_escolhido"]
    tr = ler("treino")
    return ml.treinar([r["texto"] for r in tr], [r["orgao_sigla"] for r in tr], c)


def treinar_ml() -> dict:
    """Escolhe C no dev. O teste não é tocado aqui."""
    from triagem import ml
    from triagem.metricas import intervalo_wilson
    tr, dv = ler("treino"), ler("dev")
    xs, ys = [r["texto"] for r in tr], [r["orgao_sigla"] for r in tr]
    grade = {}
    for c in GRADE_C:
        pred, _ = ml.prever(ml.treinar(xs, ys, c), [r["texto"] for r in dv])
        grade[c] = round(sum(p == r["orgao_sigla"] for p, r in zip(pred, dv)) / len(dv), 4)
    c_esc = max(GRADE_C, key=lambda c: (grade[c], -c))
    ac = grade[c_esc]
    saida = {"treino": len(tr), "dev": len(dv), "grade_acuracia_dev": grade, "c_escolhido": c_esc,
             "acuracia_dev": ac, "acuracia_dev_ic95": list(intervalo_wilson(round(ac * len(dv)), len(dv)))}
    ARQ_ML.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


# ---------------------------------------------------------------- prompt e requisição

def prompt_sistema(exemplos: list[dict]) -> str:
    """O prompt da v1, com os órgãos da Prefeitura de São Paulo."""
    linhas = [
        "Você faz a triagem de pedidos de acesso à informação enviados por cidadãos à Prefeitura de São Paulo.",
        "Sua tarefa: indicar para qual destes 10 órgãos municipais o pedido deve ser encaminhado.",
        "",
        "Órgãos:",
        *[f"- {s}: {d}" for s, d in ORGAOS.items()],
        "",
        "Regras:",
        "- Escolha sempre um dos 10 órgãos, o mais provável.",
        "- Em 'trecho', copie literalmente um trecho curto do pedido (até 20 palavras) que justifica a escolha.",
        "- Em 'justificativa', explique em uma frase curta, para um servidor público.",
        "- Em 'confianca', use 'alta' se o pedido é claramente do órgão, 'media' se há outro órgão plausível,"
        " 'baixa' se é um chute.",
        "- Marcadores como [NOME], [CPF], [EMAIL], <DADO ANONIMIZADO> e xxxx substituem dados pessoais removidos.",
        "",
        "Exemplos de pedidos já encaminhados:",
    ]
    for i, e in enumerate(exemplos, 1):
        linhas += [f"<exemplo {i}>", f"Pedido: {e['texto']}", f"Órgão: {e['orgao_sigla']}", f"</exemplo {i}>"]
    return "\n".join(linhas)


def sistema() -> str:
    return prompt_sistema(escolher_exemplos(ler_jsonl(ARQ_TREINO)))


def corpo_requisicao(sistema_: str, texto: str) -> dict:
    """Igual ao da v1 (llm.corpo_requisicao, Sonnet), com o schema dos órgãos de SP."""
    corpo = llm.corpo_requisicao(llm.MODELOS["sonnet"], sistema_, texto)
    corpo["output_config"] = {"format": {"type": "json_schema", "schema": SCHEMA}, "effort": "low"}
    return corpo


def hash_prompt(sistema_: str) -> str:
    return hashlib.sha256(sistema_.encode("utf-8")).hexdigest()[:12]


def interpretar(texto_resposta: str | None) -> tuple[dict | None, str | None]:
    """llm.interpretar, com a lista de órgãos de SP (o JSON é lido do mesmo jeito)."""
    if not texto_resposta or not texto_resposta.strip():
        return None, "vazia"
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto_resposta.strip())
    try:
        dados = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, flags=re.DOTALL)
        if not m:
            return None, "sem_json"
        try:
            dados = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None, "json_invalido"
    if not isinstance(dados, dict):
        return None, "nao_objeto"
    org = next((s for s in SIGLAS if s.upper() == str(dados.get("orgao", "")).strip().upper()), None)
    if org is None:
        return None, "orgao_invalido"
    conf = str(dados.get("confianca", "")).strip().lower().replace("é", "e")
    return {"orgao": org, "trecho": str(dados.get("trecho", "")).strip(),
            "justificativa": str(dados.get("justificativa", "")).strip(),
            "confianca": conf if conf in llm.CONFIANCAS else None}, None


def mostrar_prompt() -> None:
    s = sistema()
    print(s)
    print("\nhash:", hash_prompt(s), "| caracteres:", len(s))
    achados = pii.encontrar_pii_regex(s, matricula=True)
    print("dados estruturados no prompt:", achados or "nenhum")


# ---------------------------------------------------------------- estimativa (sem chamar a API)

def _calibrar_tokens() -> dict:
    """Tokens por caractere e saída média, medidos nas chamadas reais da v1 (Sonnet) em jan, fev e mar–out/2026."""
    from triagem.marco3 import _sistema
    s1 = _sistema()
    modelo = llm.MODELOS["sonnet"]
    cache = llm.Cache(modelo)
    regs = (ler_jsonl(config.DATA / "holdout_2026.jsonl") + ler_jsonl(config.DATA / "holdout_2026_02.jsonl")
            + ler_jsonl(config.DATA / "monitor_2026.jsonl"))
    xs, ys, saida, prefixo = [], [], [], []
    for r in regs:
        rec = cache.get(llm.chave_cache(llm.corpo_requisicao(modelo, s1, r["texto"]), r["id"]))
        if rec is None:
            continue
        u = rec["uso"]
        xs.append(len(r["texto"]))
        ys.append(u["input_tokens"])
        saida.append(u["output_tokens"])
        prefixo.append(u["cache_read_input_tokens"] + u["cache_creation_input_tokens"])
    b, a = np.polyfit(xs, ys, 1)   # tokens não cacheados = a + b * caracteres do pedido
    pref = int(np.median(prefixo))
    return {"chamadas": len(xs), "tokens_fixos_por_chamada": round(float(a), 1), "tokens_por_caractere_do_pedido": round(float(b), 4),
            "tokens_do_prefixo_v1": pref, "caracteres_do_prefixo_v1": len(s1), "tokens_por_caractere_do_prefixo": round(pref / len(s1), 4),
            "saida_media": round(float(np.mean(saida)), 1), "saida_p90": int(np.percentile(saida, 90))}


def estimar() -> dict:
    from triagem.marco7 import gasto_fase
    cal = _calibrar_tokens()
    p = llm.PRECOS[llm.MODELOS["sonnet"]]
    s = sistema()
    prefixo = len(s) * cal["tokens_por_caractere_do_prefixo"]
    rodadas = {}
    for nome, arq in (("piloto", ARQ_PILOTO), ("dev", ARQ_DEV), ("teste", ARQ_TESTE)):
        rs = ler_jsonl(arq)
        entrada = sum(cal["tokens_fixos_por_chamada"] + cal["tokens_por_caractere_do_pedido"] * len(r["texto"]) for r in rs)
        saida_ = cal["saida_p90"] * len(rs)            # conservador: o p90 da saída em todas as chamadas
        com_cache = (entrada * p["entrada"] + prefixo * (len(rs) - 1) * p["leitura_cache"]
                     + prefixo * p["escrita_cache_5m"] + saida_ * p["saida"]) / 1e6
        sem_cache = (entrada * p["entrada"] + prefixo * len(rs) * p["entrada"] + saida_ * p["saida"]) / 1e6
        rodadas[nome] = {"pedidos": len(rs), "caracteres_medios": round(float(np.mean([len(r["texto"]) for r in rs])), 1),
                         "usd_com_cache_de_prompt": round(com_cache, 3), "usd_se_o_cache_falhar": round(sem_cache, 3)}
    total = sum(r["usd_com_cache_de_prompt"] for r in rodadas.values())
    pior = sum(r["usd_se_o_cache_falhar"] for r in rodadas.values())
    g = gasto_fase()
    saida = {"calibracao_nas_chamadas_reais_da_v1": cal, "prefixo_sp": {"caracteres": len(s), "tokens_estimados": round(prefixo),
             "hash_prompt": hash_prompt(s)}, "precos_usd_por_milhao": p, "fonte_precos": llm.FONTE_PRECOS,
             "rodadas": rodadas, "total_usd": round(total, 2), "total_se_o_cache_falhar_usd": round(pior, 2),
             "gasto_da_fase_ate_agora_usd": round(g, 2), "gasto_previsto_ao_fim_usd": round(g + total, 2),
             "gasto_previsto_ao_fim_se_o_cache_falhar_usd": round(g + pior, 2), "teto_da_fase_usd": 12.0}
    ARQ_ESTIMATIVA.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


# ---------------------------------------------------------------- rodada (só com aprovação do Luigi)

TETO_FASE_USD = 12.0
CONJUNTOS = {"piloto": ARQ_PILOTO, "dev": ARQ_DEV}   # o teste só roda depois de conferir_congelado()


def _checar_pii_sp(corpo: dict) -> None:
    """Além da checagem de llm.chamar: matrícula funcional também bloqueia o envio."""
    for t in (corpo["system"][0]["text"], corpo["messages"][0]["content"]):
        achados = pii.encontrar_pii_regex(t, matricula=True)
        if achados:
            raise SystemExit(f"PARADO: dado pessoal estruturado no texto a enviar: {[x for x, _ in achados]}")


def _conferir_commit_do_congelamento() -> None:
    """O teste só roda depois de o registro congelado estar commitado, sem mudança local nele nem no que ele cita."""
    import subprocess
    git = lambda *a: subprocess.run(["git", *a], cwd=config.RAIZ, capture_output=True, text=True, check=True).stdout
    if not git("log", "--diff-filter=A", "--format=%H", "--", "results/marco9_congelado.json").strip():
        raise SystemExit("PARADO: results/marco9_congelado.json ainda não foi commitado")
    arquivos = ["results/marco9_congelado.json", "results/marco9_auditoria.json", "results/marco9_ml.json",
                "results/marco9_dev.json", "src/triagem/marco9.py"]
    if git("status", "--porcelain", "--", *arquivos).strip():
        raise SystemExit("PARADO: há mudança não commitada no congelamento ou no código do Marco 9")


def rodar(conjunto: str, paralelo: int = 6) -> None:
    """Uma rodada do Sonnet (prompt da v1 com os órgãos de SP). Para se passar do teto da fase ou se o cache de
    prompt não funcionar na 2ª chamada (sem cache, o custo seria cerca de 4 vezes maior)."""
    import anthropic
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from triagem.marco7 import gasto_fase
    if conjunto == "teste":
        conferir_congelado()                  # para se algo mudou depois do congelamento
        _conferir_commit_do_congelamento()
    regs = ler(conjunto)                      # sem as exclusões da auditoria
    s = sistema()
    est = json.loads(ARQ_ESTIMATIVA.read_text())
    if est["prefixo_sp"]["hash_prompt"] != hash_prompt(s):
        raise SystemExit("PARADO: o prompt mudou depois da estimativa; rode `estimar` de novo")
    cache = llm.Cache(llm.MODELOS["sonnet"])
    corpos = {r["id"]: corpo_requisicao(s, r["texto"]) for r in regs}
    for c in corpos.values():
        _checar_pii_sp(c)
    pend = [r for r in regs if cache.get(llm.chave_cache(corpos[r["id"]], r["id"])) is None]
    por_pedido = est["rodadas"][conjunto]["usd_com_cache_de_prompt"] / est["rodadas"][conjunto]["pedidos"]
    previsto = gasto_fase() + por_pedido * len(pend)
    print(f"marco 9 / {conjunto}: {len(pend)} de {len(regs)} a chamar; gasto da fase previsto ao fim: US$ {previsto:.2f} (teto {TETO_FASE_USD})")
    if previsto > TETO_FASE_USD:
        raise SystemExit("PARADO: passaria do teto da fase")
    if not pend:
        return
    cli = anthropic.Anthropic(max_retries=2)
    # as duas primeiras em série: a 1ª grava o prefixo no cache de prompt; a 2ª tem de lê-lo
    for r in pend[:2]:
        rec = llm.chamar(cli, corpos[r["id"]], r["id"], cache)
    if len(pend) > 1 and not rec.get("do_cache") and rec["uso"]["cache_read_input_tokens"] == 0:
        raise SystemExit("PARADO: a 2ª chamada não leu o cache de prompt (custo sairia ~4 vezes maior)")
    with ThreadPoolExecutor(max_workers=paralelo) as ex:
        fut = [ex.submit(llm.chamar, cli, corpos[r["id"]], r["id"], cache) for r in pend[2:]]
        try:
            for k, f in enumerate(as_completed(fut), 3):
                f.result()
                if k % 25 == 0:
                    g = gasto_fase()
                    print(f"  {k}/{len(pend)}, gasto da fase US$ {g:.3f}")
                    if g > TETO_FASE_USD:
                        raise SystemExit("PARADO: gasto da fase passou do teto")
        except BaseException:
            for x in fut:                     # erro ou teto: nada que ainda não começou é chamado
                x.cancel()
            raise
    print(f"fim. gasto da fase: US$ {gasto_fase():.3f}")


META = 0.01
ARQ_AVALIACAO = {"piloto": config.RESULTS / "marco9_piloto.json", "dev": config.RESULTS / "marco9_dev.json"}


def linhas(regs: list[dict], s: str, mdl) -> tuple[list[dict], dict]:
    """Uma linha por pedido no formato do Marco 4: (previsto, nota), nota = (confiança, ML concorda, p do ML)."""
    from triagem import ml
    from triagem.marco4 import NIVEL
    cache = llm.Cache(llm.MODELOS["sonnet"])
    pred_ml, prob = ml.prever(mdl, [r["texto"] for r in regs])
    classes = list(mdl.classes_)
    out, diag = [], Counter()
    uso = Counter()
    for r, pm, pr in zip(regs, pred_ml, prob):
        rec = cache.get(llm.chave_cache(corpo_requisicao(s, r["texto"]), r["id"]))
        if rec is None:
            raise SystemExit(f"falta a resposta do Sonnet para {r['id']}")
        d, erro = interpretar(rec["resposta"])
        diag[erro or "ok"] += 1
        diag["stop_" + str(rec["stop_reason"])] += 1
        uso.update(rec["uso"])
        uso["custo_usd"] += rec["custo_usd"]
        prev, conf = (d["orgao"], d["confianca"]) if d else (None, None)
        if d:
            diag["trecho_no_pedido"] += llm.trecho_esta_no_pedido(d["trecho"], r["texto"])
        p = dict(zip(classes, map(float, pr)))
        out.append({"id": r["id"], "verdadeiro": r["orgao_sigla"], "reencaminhado": bool(r["reencaminhado"]),
                    "confianca": conf, "previsto": prev, "ml": pm, "p_ml_do_previsto": p.get(prev, 0.0),
                    "sonnet": (prev, (NIVEL[conf], int(prev == pm), p.get(prev, 0.0))),
                    "ml_so": (pm, (max(p.values()),))})
    return out, {"respostas": dict(diag), "uso": {k: round(v, 4) for k, v in uso.items()}}


def em_palavras(lim: list) -> str:
    """O limiar (confiança, ML concorda, probabilidade do ML para o órgão escolhido) em português."""
    nivel, concorda, p = lim
    p_ = f"{p:.4f}".replace(".", ",")
    if nivel == 2 and concorda == 1:
        return f"confiança alta, com o modelo estatístico concordando e probabilidade >= {p_}"
    if nivel == 2:
        return f"confiança alta; se o modelo estatístico discordar, só quando ele der ao órgão escolhido probabilidade >= {p_}"
    if concorda == 1:
        return f"confiança alta; ou média com o modelo estatístico concordando e probabilidade >= {p_}"
    return (f"confiança alta; ou média com o modelo estatístico concordando; ou média com probabilidade do modelo "
            f"estatístico >= {p_} para o órgão escolhido")


def avaliar(conjunto: str) -> dict:
    """Piloto: procura bug. Dev: acurácia, confiança e o limiar da regra (maior cobertura com erro <= 1%)."""
    from triagem.marco4 import aplicar, curva, escolher_limiar
    from triagem.metricas import intervalo_wilson
    regs = ler(conjunto)
    s = sistema()
    ls, diag = linhas(regs, s, modelo_ml())
    n = len(ls)
    ac = sum(l["previsto"] == l["verdadeiro"] for l in ls)
    ac_ml = sum(l["ml"] == l["verdadeiro"] for l in ls)
    por_conf = {c: {"n": len(g), "acerto": round(sum(l["previsto"] == l["verdadeiro"] for l in g) / len(g), 4)}
                for c in llm.CONFIANCAS for g in [[l for l in ls if l["confianca"] == c]] if g}
    saida = {"conjunto": conjunto, "pedidos": n, "hash_prompt": hash_prompt(s), "diagnostico": diag,
             "acuracia_sonnet": round(ac / n, 4), "acuracia_sonnet_ic95": list(intervalo_wilson(ac, n)),
             "acuracia_ml": round(ac_ml / n, 4), "acuracia_ml_ic95": list(intervalo_wilson(ac_ml, n)),
             "por_confianca": por_conf,
             "por_orgao": {o: {"n": len(g), "sonnet": round(sum(l["previsto"] == o for l in g) / len(g), 4),
                               "ml": round(sum(l["ml"] == o for l in g) / len(g), 4)}
                           for o in SIGLAS for g in [[l for l in ls if l["verdadeiro"] == o]] if g},
             "confusoes_sonnet": dict(Counter(f"{l['verdadeiro']}->{l['previsto']}" for l in ls
                                              if l["previsto"] != l["verdadeiro"]).most_common(12)),
             "custo_por_1000_usd": round(1000 * diag["uso"]["custo_usd"] / n, 4)}
    if conjunto == "dev":
        pts = curva(ls, "sonnet")
        esc = escolher_limiar(pts, META)
        esc_ml = escolher_limiar(curva(ls, "ml_so"), META)
        saida["regra"] = {
            "criterio": "maior cobertura com erro <= 1% no dev (mesmo critério do Marco 4)",
            "limiar": esc["limiar"] if esc else None,
            "em_palavras": em_palavras(esc["limiar"]) if esc else None,
            "no_dev": aplicar(ls, "sonnet", esc["limiar"]) if esc else None,
            "curva": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()} for p in pts],
            "regra_v1_federal_no_dev_sp": aplicar(ls, "sonnet", [1, 1, 0.8035]),
            "ml_sozinho": {"limiar": esc_ml["limiar"] if esc_ml else None, "no_dev": aplicar(ls, "ml_so", esc_ml["limiar"]) if esc_ml else None},
        }
    ARQ_AVALIACAO[conjunto].write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    with open(config.RESULTS / "predicoes" / f"sp_{conjunto}.jsonl", "w", encoding="utf-8") as f:
        for l in ls:
            f.write(json.dumps({k: l[k] for k in ("id", "verdadeiro", "previsto", "confianca", "ml", "p_ml_do_previsto",
                                                  "reencaminhado")}, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in saida.items() if k != "regra"} | (
        {"regra": {k: v for k, v in saida["regra"].items() if k != "curva"}} if "regra" in saida else {}),
        ensure_ascii=False, indent=1))
    return saida


ARQ_CONGELADO = config.RESULTS / "marco9_congelado.json"


def pesos_2025() -> dict:
    """Fatia de cada órgão nos pedidos de 2025 aos 10 órgãos (base inteira, antes da limpeza)."""
    d = pedidos_2025()
    c = d[d["sigla"].isin(SIGLAS)]["sigla"].value_counts()
    return {o: round(int(c[o]) / int(c.sum()), 6) for o in SIGLAS}


def congelar() -> dict:
    """Antes de qualquer chamada no teste: hash do teste, do treino (ML) e do prompt, a requisição, o C e o limiar."""
    from datetime import datetime, timezone
    from triagem.marco7 import gasto_fase
    cache = llm.Cache(llm.MODELOS["sonnet"])
    ids = {r["id"] for r in ler_jsonl(ARQ_TESTE)}
    if any(r["id"] in ids for r in cache.dados.values()):
        raise SystemExit("já existe chamada em pedido do teste: não dá para congelar depois")
    dev = json.loads(ARQ_AVALIACAO["dev"].read_text())
    s = sistema()
    if dev["hash_prompt"] != hash_prompt(s):
        raise SystemExit("o prompt mudou depois do dev")
    corpo = corpo_requisicao(s, "")
    saida = {
        "congelado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256_teste": sha256(ARQ_TESTE), "sha256_treino": sha256(ARQ_TREINO), "sha256_dev": sha256(ARQ_DEV),
        "n_teste": len(ids), "hash_prompt": hash_prompt(s), "sha256_prompt_completo": hashlib.sha256(s.encode()).hexdigest(),
        "requisicao": {k: corpo[k] for k in ("model", "max_tokens", "output_config", "thinking")},
        "ml_c": json.loads(ARQ_ML.read_text())["c_escolhido"],
        "limiar_sonnet": dev["regra"]["limiar"], "limiar_ml_sozinho": dev["regra"]["ml_sozinho"]["limiar"],
        "regra_v1_federal_tambem_aplicada": [1, 1, 0.8035],
        "sha256_auditoria": sha256(ARQ_AUDITORIA),
        "excluidos_da_avaliacao": json.loads(ARQ_AUDITORIA.read_text())["excluir_do_teste"],
        "numero_principal": "contagem direta nos pedidos do teste (sem os excluídos), regra escolhida no dev de SP",
        "secundario_ponderado": {"descricao": "mesmo cálculo, com cada órgão pesado pela sua fatia nos pedidos de 2025 dos 10 órgãos (antes da limpeza)",
                                 "fatia_2025": pesos_2025()},
        "gasto_da_fase_no_congelamento_usd": round(gasto_fase(), 3),
        "estimativa_teste_usd": json.loads(ARQ_ESTIMATIVA.read_text())["rodadas"]["teste"]["usd_com_cache_de_prompt"],
        "regra": "uma rodada do Sonnet no teste; as regras são aplicadas às mesmas respostas, sem chamadas extras; "
                 "o número principal é a regra escolhida no dev de SP (meta de erro de 1%)",
    }
    saida["gasto_previsto_ao_fim_usd"] = round(saida["gasto_da_fase_no_congelamento_usd"] + saida["estimativa_teste_usd"], 2)
    ARQ_CONGELADO.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


def conferir_congelado() -> dict:
    reg = json.loads(ARQ_CONGELADO.read_text())
    s = sistema()
    corpo = corpo_requisicao(s, "")
    checagens = {"teste": sha256(ARQ_TESTE) == reg["sha256_teste"], "treino": sha256(ARQ_TREINO) == reg["sha256_treino"],
                 "prompt": hash_prompt(s) == reg["hash_prompt"],
                 "requisicao": {k: corpo[k] for k in ("model", "max_tokens", "output_config", "thinking")} == reg["requisicao"],
                 "ml_c": json.loads(ARQ_ML.read_text())["c_escolhido"] == reg["ml_c"],
                 "dev": sha256(ARQ_DEV) == reg["sha256_dev"], "auditoria": sha256(ARQ_AUDITORIA) == reg["sha256_auditoria"],
                 "limiar": json.loads(ARQ_AVALIACAO["dev"].read_text())["regra"]["limiar"] == reg["limiar_sonnet"],
                 "limiar_ml": json.loads(ARQ_AVALIACAO["dev"].read_text())["regra"]["ml_sozinho"]["limiar"] == reg["limiar_ml_sozinho"]}
    if not all(checagens.values()):
        raise SystemExit(f"PARADO: algo mudou depois do congelamento: {checagens}")
    return reg


ARQ_TESTE_RES = config.RESULTS / "marco9_teste.json"


def avaliar_teste() -> dict:
    """Uma vez, depois da rodada única: lê os limiares do CONGELADO (não do dev) e aplica as três regras às mesmas
    respostas. Número principal: contagem direta; secundário: ponderado pela fatia de cada órgão em 2025."""
    from triagem.marco4 import aplicar
    from triagem.metricas import intervalo_wilson
    reg = conferir_congelado()
    regs = ler("teste")
    if {r["id"] for r in ler_jsonl(ARQ_TESTE)} - {r["id"] for r in regs} != set(reg["excluidos_da_avaliacao"]):
        raise SystemExit("PARADO: exclusões diferentes das congeladas")
    s = sistema()
    ls, diag = linhas(regs, s, modelo_ml())
    n = len(ls)
    pesos = {o: reg["secundario_ponderado"]["fatia_2025"][o] / (sum(l["verdadeiro"] == o for l in ls) / n)
             for o in {l["verdadeiro"] for l in ls}}
    ac = sum(l["previsto"] == l["verdadeiro"] for l in ls)
    ac_ml = sum(l["ml"] == l["verdadeiro"] for l in ls)
    rng = np.random.default_rng(config.SEED)
    dif = np.array([l["previsto"] == l["verdadeiro"] for l in ls], float) - np.array([l["ml"] == l["verdadeiro"] for l in ls], float)
    boot = [dif[rng.integers(0, n, n)].mean() for _ in range(2000)]
    regras = {"sp_escolhida_no_dev": ("sonnet", reg["limiar_sonnet"]), "v1_federal": ("sonnet", reg["regra_v1_federal_tambem_aplicada"]),
              "ml_sozinho": ("ml_so", reg["limiar_ml_sozinho"])}
    res = {}
    for nome, (estr, lim) in regras.items():
        a = aplicar(ls, estr, lim, pesos)
        a = {k: v for k, v in a.items() if not k.startswith("reencaminhados")}   # 2025 não tem status: sairia sempre 0
        res[nome] = a | {"erros_por_1000_pedidos": round(1000 * a["erros"] / n, 1), "limiar": lim}
    saida = {
        "pedidos": n, "excluidos": reg["excluidos_da_avaliacao"], "hash_prompt": hash_prompt(s), "diagnostico": diag,
        "acuracia_sonnet": round(ac / n, 4), "acuracia_sonnet_ic95": list(intervalo_wilson(ac, n)),
        "acuracia_ml": round(ac_ml / n, 4), "acuracia_ml_ic95": list(intervalo_wilson(ac_ml, n)),
        "sonnet_menos_ml_pontos": {"diferenca": round(float(dif.mean()), 4),
                                   "ic95_bootstrap": [round(float(np.percentile(boot, 2.5)), 4), round(float(np.percentile(boot, 97.5)), 4)]},
        "regras": res,
        "nota": ("'ponderado_distribuicao_real' pesa cada órgão pela fatia em 2025 (registro congelado) e não tem IC; "
                 "não há reencaminhados no teste porque a base de 2025 não tem status"),
        "por_confianca": {c: {"n": len(g), "acerto": round(sum(l["previsto"] == l["verdadeiro"] for l in g) / len(g), 4)}
                          for c in llm.CONFIANCAS for g in [[l for l in ls if l["confianca"] == c]] if g},
        "por_orgao": {o: {"n": len(g), "sonnet": round(sum(l["previsto"] == o for l in g) / len(g), 4),
                          "ml": round(sum(l["ml"] == o for l in g) / len(g), 4)}
                      for o in SIGLAS for g in [[l for l in ls if l["verdadeiro"] == o]] if g},
        "confusoes_sonnet": dict(Counter(f"{l['verdadeiro']}->{l['previsto']}" for l in ls if l["previsto"] != l["verdadeiro"]).most_common(12)),
        "custo_usd": diag["uso"]["custo_usd"], "custo_por_1000_usd": round(1000 * diag["uso"]["custo_usd"] / n, 4),
    }
    ARQ_TESTE_RES.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n")
    with open(config.RESULTS / "predicoes" / "sp_teste.jsonl", "w", encoding="utf-8") as f:
        for l in ls:
            f.write(json.dumps({k: l[k] for k in ("id", "verdadeiro", "previsto", "confianca", "ml", "p_ml_do_previsto")},
                               ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return saida


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["baixar", "dor", "preparar", "auditar", "ml", "prompt", "estimar", "rodar", "avaliar", "congelar"])
    ap.add_argument("--conjunto", choices=sorted(CONJUNTOS) + ["teste"])
    a = ap.parse_args()
    if a.cmd in ("rodar", "avaliar") and not a.conjunto:
        ap.error("--conjunto é obrigatório")
    if a.cmd == "rodar":
        return rodar(a.conjunto)
    if a.cmd == "avaliar":
        return avaliar_teste() if a.conjunto == "teste" else avaliar(a.conjunto)
    if a.cmd == "auditar":
        return auditar()
    if a.cmd == "congelar":
        return congelar()
    {"baixar": baixar, "dor": dor, "preparar": preparar, "ml": treinar_ml, "prompt": mostrar_prompt, "estimar": estimar}[a.cmd]()


if __name__ == "__main__":
    main()
