"""Abordagem 2: TF-IDF + regressão logística (scikit-learn).

Treinado no treino completo (jan-ago, 16.778 pedidos). O hiperparâmetro C é escolhido no dev.
Uma versão de referência é treinada só na amostra de 2.000, para comparar com quem vê poucos exemplos.
A explicação de uma previsão são os termos do texto que mais empurraram para o órgão escolhido
(peso do termo no modelo x TF-IDF do termo no texto).
"""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from triagem import config
from triagem.texto import STOPWORDS, normalizar


def criar(c: float) -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(preprocessor=normalizar, token_pattern=r"(?u)\b[a-z][a-z0-9_]{2,}\b",
                                  stop_words=sorted(STOPWORDS), ngram_range=(1, 2), min_df=2,
                                  sublinear_tf=True, max_features=200_000)),
        ("clf", LogisticRegression(C=c, max_iter=3000, random_state=config.SEED)),
    ])


def treinar(textos: list[str], rotulos: list[str], c: float) -> Pipeline:
    modelo = criar(c)
    modelo.fit(textos, rotulos)
    return modelo


def prever(modelo: Pipeline, textos: list[str]) -> tuple[list[str], np.ndarray]:
    """Órgão previsto e a matriz de probabilidades (linhas = pedidos, colunas = modelo.classes_)."""
    prob = modelo.predict_proba(textos)
    classes = modelo.classes_
    return [classes[i] for i in prob.argmax(axis=1)], prob


_CACHE_NOMES: dict[int, np.ndarray] = {}


def _nomes_termos(vet) -> np.ndarray:
    if id(vet) not in _CACHE_NOMES:
        _CACHE_NOMES[id(vet)] = vet.get_feature_names_out()
    return _CACHE_NOMES[id(vet)]


def explicar(modelo: Pipeline, texto: str, orgao: str, n: int = 5) -> list[str]:
    """Os n termos do texto que mais contribuíram para o órgão escolhido."""
    vet = modelo.named_steps["tfidf"]
    clf = modelo.named_steps["clf"]
    x = vet.transform([texto])
    k = list(clf.classes_).index(orgao)
    contrib = x.multiply(clf.coef_[k]).tocsr()
    idx = contrib.indices[np.argsort(-contrib.data)][:n]
    nomes = _nomes_termos(vet)
    return [nomes[i] for i in idx if contrib[0, i] > 0]
