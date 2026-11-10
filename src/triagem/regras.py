"""Abordagem 1: regras por palavras-chave.

Duas fontes de regra, ambas legíveis por um servidor:
1. Nome e sigla de cada órgão (ALIASES), escritos à mão. É o que qualquer servidor sabe.
2. Palavras-chave por órgão, extraídas da amostra de treino (2.000 pedidos) pelo log-odds com prior
   de Dirichlet (Monroe et al., 2008), contando documentos e não ocorrências. A lista gerada fica em
   results/regras_palavras_chave.json.

Pontuação de um pedido para um órgão = PESO_ALIAS x (citações do nome/sigla) + (palavras-chave presentes).
Vence a maior pontuação. Sem nenhuma regra disparada, a regra não decide (previsão None):
num sistema real, o pedido iria para a triagem humana.

Os dois parâmetros (palavras por órgão e peso do nome/sigla) são escolhidos no dev. O teste não é olhado.
"""
import math
import re
from collections import Counter

from triagem.texto import normalizar, termos

# Nome oficial, sigla e formas curtas óbvias. Siglas curtas só valem em maiúsculas (ver _padroes).
ALIASES = {
    "MS": ["Ministério da Saúde", "MS"],
    "PETROBRAS": ["Petrobras", "Petróleo Brasileiro"],
    "ANVISA": ["Anvisa", "Agência Nacional de Vigilância Sanitária"],
    "BACEN": ["BACEN", "BCB", "Banco Central"],
    "INSS": ["INSS", "Instituto Nacional do Seguro Social"],
    "MF": ["Ministério da Fazenda", "MF", "Receita Federal"],
    "MGI": ["MGI", "Ministério da Gestão e da Inovação"],
    "MEC": ["MEC", "Ministério da Educação"],
    "ANEEL": ["ANEEL", "Agência Nacional de Energia Elétrica"],
    "PF": ["Polícia Federal", "PF"],
}
_SIGLAS_EXATAS = {"MS", "MF", "MGI", "MEC", "PF", "BCB"}


def _padroes() -> dict[str, list[tuple[re.Pattern, bool]]]:
    """Por órgão: (padrão, procura_no_original). Siglas curtas: texto original, sensível à caixa.
    Demais nomes: texto normalizado (minúsculas, sem acento)."""
    pads = {}
    for org, nomes in ALIASES.items():
        pads[org] = [
            (re.compile(rf"(?<!\w){re.escape(n)}(?!\w)"), True) if n in _SIGLAS_EXATAS
            else (re.compile(rf"(?<!\w){re.escape(normalizar(n))}(?!\w)"), False)
            for n in nomes
        ]
    return pads


_PADROES = _padroes()


def citacoes_de_nome(texto: str) -> dict[str, int]:
    """Quantas vezes o texto cita o nome ou a sigla de cada órgão."""
    norm = normalizar(texto)
    return {org: sum(len(p.findall(texto if original else norm)) for p, original in pads)
            for org, pads in _PADROES.items()}


def extrair_palavras_chave(registros: list[dict], k: int, min_docs: int = 5, alpha: float = 0.01) -> dict:
    """Log-odds com prior informativo, por documento. Devolve, por órgão, os k termos mais
    associados a ele (z-score), com o z-score e em quantos pedidos de treino o termo aparece."""
    df_org = {}
    df_total = Counter()
    n_org = Counter()
    for r in registros:
        t = termos(r["texto"])
        df_org.setdefault(r["orgao_sigla"], Counter()).update(t)
        df_total.update(t)
        n_org[r["orgao_sigla"]] += 1
    n_total = sum(n_org.values())
    # Termo presente em todos os pedidos não discrimina nada (e zeraria o denominador).
    vocab = [w for w, n in df_total.items() if min_docs <= n < sum(n_org.values())]
    a0 = alpha * len(vocab)
    saida = {}
    for org in sorted(df_org):
        y_i, n_i = df_org[org], n_org[org]
        n_j = n_total - n_i
        pontos = []
        for w in vocab:
            a_w = alpha * df_total[w] / n_total * len(vocab)  # prior proporcional à frequência geral
            yi = y_i[w]
            yj = df_total[w] - yi
            d = (math.log((yi + a_w) / (n_i + a0 - yi - a_w)) - math.log((yj + a_w) / (n_j + a0 - yj - a_w)))
            var = 1 / (yi + a_w) + 1 / (yj + a_w)
            pontos.append((d / math.sqrt(var), w, yi))
        pontos.sort(reverse=True)
        saida[org] = [{"termo": w, "z": round(z, 2), "pedidos_no_treino": yi} for z, w, yi in pontos[:k]]
    return saida


class Regras:
    def __init__(self, palavras_chave: dict, peso_alias: float):
        self.palavras_chave = {org: {p["termo"] for p in lst} for org, lst in palavras_chave.items()}
        # Força da associação (z do log-odds), para mostrar primeiro as palavras mais decisivas.
        self.forca = {org: {p["termo"]: p.get("z", 0.0) for p in lst} for org, lst in palavras_chave.items()}
        self.peso_alias = peso_alias

    def explicar(self, texto: str) -> dict[str, dict]:
        """Por órgão: citações do nome/sigla e palavras-chave encontradas."""
        t = termos(texto)
        cit = citacoes_de_nome(texto)
        return {org: {"nome_ou_sigla": cit.get(org, 0),
                      "palavras": sorted(self.palavras_chave[org] & t, key=lambda w: (-self.forca[org][w], w))}
                for org in self.palavras_chave}

    def pontuar(self, texto: str) -> dict[str, float]:
        return {org: self.peso_alias * e["nome_ou_sigla"] + len(e["palavras"])
                for org, e in self.explicar(texto).items()}

    def prever(self, texto: str) -> tuple[str | None, float, dict]:
        """(órgão ou None, margem entre 1º e 2º, explicação do vencedor)."""
        pont = self.pontuar(texto)
        ordem = sorted(pont.items(), key=lambda kv: (-kv[1], kv[0]))
        (org1, p1), (_, p2) = ordem[0], ordem[1]
        if p1 == 0:
            return None, 0.0, {}
        exp = self.explicar(texto)[org1]
        return org1, float(p1 - p2), exp
