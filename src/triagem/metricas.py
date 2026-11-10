"""Métricas de classificação usadas em todos os marcos.

Tudo recebe listas de rótulos verdadeiros e previstos (siglas dos órgãos).
Uma previsão pode ser None (abstenção ou resposta inválida do modelo): conta como erro
na acurácia e no F1, e é reportada à parte em `n_sem_resposta`.
"""
import math
import re
from collections import Counter

from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

SEM_RESPOSTA = "__nenhum__"


def _normalizar(pred):
    return [SEM_RESPOSTA if p is None else p for p in pred]


def intervalo_wilson(acertos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confiança de 95% para uma proporção (Wilson). Com n pequeno, fica largo."""
    if n == 0:
        return (0.0, 0.0)
    p = acertos / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(centro - meia, 4), round(centro + meia, 4))


def avaliar(verdade: list[str], pred: list, classes: list[str]) -> dict:
    """Acurácia, F1 macro (sobre as classes reais) e métricas por classe."""
    if len(verdade) != len(pred):
        raise ValueError("verdade e previsão com tamanhos diferentes")
    if not verdade:
        return {"n": 0}
    p = _normalizar(pred)
    acertos = sum(v == q for v, q in zip(verdade, p))
    prec, rec, f1, sup = precision_recall_fscore_support(
        verdade, p, labels=classes, zero_division=0)
    return {
        "n": len(verdade),
        "acertos": acertos,
        "acuracia": round(acertos / len(verdade), 4),
        "acuracia_ic95": list(intervalo_wilson(acertos, len(verdade))),
        "f1_macro": round(float(f1_score(verdade, p, labels=classes, average="macro", zero_division=0)), 4),
        "n_sem_resposta": sum(q == SEM_RESPOSTA for q in p),
        "por_classe": {
            c: {"precisao": round(float(prec[i]), 4), "revocacao": round(float(rec[i]), 4),
                "f1": round(float(f1[i]), 4), "suporte": int(sup[i])}
            for i, c in enumerate(classes)
        },
    }


def matriz_confusao(verdade: list[str], pred: list, classes: list[str]) -> list[list[int]]:
    """Linhas = órgão verdadeiro, colunas = órgão previsto (+ coluna final para sem resposta)."""
    p = _normalizar(pred)
    return confusion_matrix(verdade, p, labels=classes + [SEM_RESPOSTA]).tolist()[: len(classes)]


def confusoes_principais(verdade: list[str], pred: list, n: int = 8) -> list[dict]:
    """Os pares (verdadeiro -> previsto) de erro mais frequentes."""
    pares = Counter((v, q) for v, q in zip(verdade, _normalizar(pred)) if v != q)
    return [{"verdadeiro": v, "previsto": q, "n": k} for (v, q), k in pares.most_common(n)]


# Como cada órgão aparece escrito pelo cidadão. Siglas curtas (MS, MF, MGI, MEC, PF) só contam em
# maiúsculas, para não casar com "ms" (milissegundos) ou palavras comuns. As demais aceitam
# qualquer caixa ("Anvisa", "Petrobras").
_SIGLAS_EXATAS = {"MS", "MF", "MGI", "MEC", "PF"}


def cita_sigla(texto: str, sigla: str) -> bool:
    """O texto cita a sigla do órgão? Usado para separar os casos 'fáceis' na análise."""
    if sigla in _SIGLAS_EXATAS:
        return re.search(rf"(?<![\w]){re.escape(sigla)}(?![\w])", texto) is not None
    return re.search(rf"(?<![\w]){re.escape(sigla)}(?![\w])", texto, flags=re.IGNORECASE) is not None
