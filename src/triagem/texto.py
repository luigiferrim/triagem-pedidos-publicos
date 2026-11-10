"""Normalização de texto compartilhada por regras e ML."""
import re
import unicodedata

# Palavras muito comuns em pedidos LAI, que não ajudam a escolher o órgão.
STOPWORDS = set("""
a ao aos as com como da das de do dos e em entre era essa esse esta este eu foi ha isso isto ja la mais mas
me mesmo meu minha na nas nao nem no nos o os ou para pela pelas pelo pelos por qual quais quando que se sem
ser seu sua suas seus so sobre tambem tem ter um uma umas uns voce vos sao foram sido estao esta estou sendo
solicito solicitar solicitacao informacao informacoes acesso dados lei pedido favor gostaria saber obrigado
obrigada desde agradeco att atenciosamente prezados prezado prezada bom dia tarde noite cordialmente forma
nome cpf email telefone cep documento endereco data_nasc rg ano anos
""".split())


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, marcadores de PII viram palavras ('[NOME]' -> 'nome')."""
    t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t)


def tokens(texto: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9_]{2,}", normalizar(texto)) if w not in STOPWORDS]


def termos(texto: str) -> set[str]:
    """Unigramas e bigramas (sem stopwords) de um texto, como conjunto."""
    tk = tokens(texto)
    return set(tk) | {f"{a} {b}" for a, b in zip(tk, tk[1:])}
