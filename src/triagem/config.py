"""Parâmetros do projeto. Tudo que muda o resultado fica aqui."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DATA = RAIZ / "data"
RAW = DATA / "raw"
RESULTS = RAIZ / "results"
CACHE = RAIZ / "cache"

SEED = 42
ANO = 2025
N_ORGAOS = 10

# Tamanhos dos conjuntos (pedidos).
N_TESTE = 500
N_DEV = 500
N_TREINO_AMOSTRA = 2000  # treino "pequeno" (regras, exemplos do prompt, referência do ML)
MIN_POR_ORGAO_TESTE = 25
N_REVISAO_MANUAL = 50

URL_BASE = "https://dadosabertos-download.cgu.gov.br/FalaBR"
# Base completa: só metadados, todos os pedidos. Usada para medir a dor.
URL_COMPLETA = f"{URL_BASE}/Arquivos_FalaBR/Pedidos_csv_{ANO}.zip"
# Base "filtrada": tem o texto do pedido, mas só parte dos pedidos. Usada para classificar.
URL_FILTRADA = f"{URL_BASE}/Arquivos_FalaBR_Filtrado/Arquivos_csv_{ANO}.zip"

DIR_COMPLETA = RAW / f"falabr_{ANO}"
DIR_FILTRADA = RAW / f"falabr_filtrado_{ANO}"

DECISAO_SEM_COMPETENCIA = "Órgão não tem competência para responder sobre o assunto"
ESPEC_PARCIAL_OUTRO_ORGAO = "Parte da informação é de competência de outro órgão/entidade"

ARQ_TESTE = DATA / "test.jsonl"
ARQ_DEV = DATA / "dev.jsonl"
ARQ_TREINO = DATA / "train.jsonl"            # todo o treino disponível (para o ML clássico)
ARQ_TREINO_AMOSTRA = DATA / "train_amostra.jsonl"
ARQ_FORA_COMPETENCIA = DATA / "fora_competencia.jsonl"
ARQ_REVISAO = DATA / "revisao_manual_50.csv"
ARQ_HASH_TESTE = DATA / "test.sha256"
