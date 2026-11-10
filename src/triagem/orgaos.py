"""Seleção dos órgãos do recorte e nomes curtos."""
import re

import pandas as pd

from triagem import config


def sigla(nome: str) -> str:
    """'MS – Ministério da Saúde' -> 'MS'. Os nomes da CGU usam '–' ou '-' como separador."""
    return re.split(r"\s+[–-]\s+", nome, maxsplit=1)[0].strip()


def rotulo_confiavel(df: pd.DataFrame) -> pd.Series:
    """Pedido cujo órgão destinatário é um rótulo confiável.

    Fica de fora quem respondeu "não tem competência": o órgão registrado é o que recusou,
    e o órgão certo não aparece na base.
    """
    return df["Decisao"] != config.DECISAO_SEM_COMPETENCIA


def top_orgaos(filtrada: pd.DataFrame, n: int = config.N_ORGAOS) -> list[str]:
    """Os n órgãos com mais pedidos na base com texto, contando só rótulos confiáveis.
    Empate é resolvido pelo nome, para o resultado não depender da ordem do arquivo."""
    base = filtrada[(filtrada["Esfera"] == "Federal") & rotulo_confiavel(filtrada)]
    cont = base["OrgaoDestinatario"].value_counts()
    ordem = sorted(cont.items(), key=lambda kv: (-kv[1], kv[0]))
    return [nome for nome, _ in ordem[:n]]
