"""Procura dados pessoais nos arquivos que vão para o repositório público.

Roda antes de cada commit (`make varredura`). Verifica os arquivos que o git versionaria
(rastreados + novos não ignorados) e lista:
1. CPF, e-mail, telefone, CEP e documentos (mesmas regex da máscara) cujo número APARECE no texto
   bruto da CGU, ou seja, dado real copiado da base. Valores que não estão no bruto são fictícios (fixtures);
2. sequências com cara de nome (prenome do IBGE + sobrenome) que aparecem no texto bruto da CGU;
4. (para revisão) palavras com inicial maiúscula, fora das palavras comuns, que aparecem só 1 a 3 vezes no
   bruto: um sobrenome raro copiado de um pedido real para um teste ou doc aparece aqui;
3. trechos de texto de pedido: qualquer sequência de N_PALAVRAS palavras seguidas (sem acento, minúsculas) que
   também aparece no texto bruto (sem máscara) de algum pedido da CGU. Pega texto de pedido copiado para
   README, report.html, results/ ou exemplos de erro. Só conta a sequência que aparece em no máximo
   MAX_PEDIDOS_COM_A_SEQUENCIA pedidos: frase comum a muitos pedidos (nome de órgão, citação da lei) não é
   texto de um pedido.

Achados do tipo 2 precisam de revisão humana: podem ser autoridade pública, instituição ou lugar.
Sai com código 1 se houver achado do tipo 1 ou 3.
"""
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from triagem import config, dados, pii

# Pessoas públicas citadas em papel público e nomes de lugar/instituição usados como exemplo.
PUBLICOS = {
    "Fernando Haddad", "Gabriel Galípolo", "Nilo Peçanha", "Oswaldo Cruz", "Frederico Westphalen",
    "Gabriel da Cachoeira", "Maria da Penha", "Carolina Bori", "Paulo Guerra", "Costa do Sol",
}
N_PALAVRAS = 8
MAX_PEDIDOS_COM_A_SEQUENCIA = 2
# Frases que não são conteúdo de pedido e que algum cidadão também escreveu: o cabeçalho padrão de HTML (alguém
# colou HTML num pedido), textos oficiais da CGU, a URL pública dos dados e a citação da lei.
FRASES_PERMITIDAS = [
    "meta name viewport content width device width initial scale 1 title",
    "orgao nao tem competencia para responder sobre o assunto",
    "casos em que parte da informacao e de competencia de outro orgao",  # opção oficial de decisão da CGU
    "https dadosabertos download cgu gov br falabr arquivos falabr",  # URL pública da CGU
    "lei n 12 527 2011 e no decreto 7 724 2012",                     # citação da LAI e do decreto
]
_NOME = re.compile(r"\b([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ý][a-zà-ÿ]+){1,3})\b")


def arquivos_versionados() -> list[Path]:
    saida = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                           cwd=config.RAIZ, capture_output=True, text=True, check=True).stdout
    return [config.RAIZ / linha for linha in saida.splitlines()
            if linha and not linha.startswith("data/ref/")]  # listas de palavras, sem frases


def _palavras(texto: str) -> list[str]:
    t = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", t)


def _sequencias(palavras: list[str]) -> set[tuple]:
    return {tuple(palavras[i:i + N_PALAVRAS]) for i in range(len(palavras) - N_PALAVRAS + 1)}


def trechos_de_pedido(arquivos: list[Path], textos_brutos) -> dict[str, set[str]]:
    """Sequências de N_PALAVRAS palavras dos arquivos versionados que também estão em algum pedido bruto."""
    por_seq: dict[tuple, set[str]] = {}
    for arq in arquivos:
        try:
            texto = arq.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for seq in _sequencias(_palavras(texto)):
            por_seq.setdefault(seq, set()).add(str(arq.relative_to(config.RAIZ)))
    contagem: dict[tuple, int] = {}
    for t in textos_brutos:
        for seq in _sequencias(_palavras(t)) & por_seq.keys():
            contagem[seq] = contagem.get(seq, 0) + 1
    return {" ".join(seq): por_seq[seq] for seq, n in contagem.items()
            if n <= MAX_PEDIDOS_COM_A_SEQUENCIA and not any(" ".join(seq) in f for f in FRASES_PERMITIDAS)}


def palavras_raras(arquivos: list[Path], corpus: str) -> dict[tuple[str, int], set[str]]:
    from collections import Counter
    freq = Counter(w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{4,}", corpus))
    comuns = set((config.DATA / "ref" / "palavras_comuns.txt").read_text(encoding="utf-8").split())
    achados: dict[tuple[str, int], set[str]] = {}
    for arq in arquivos:
        rel = str(arq.relative_to(config.RAIZ))
        if rel.startswith("results/predicoes") or rel.endswith((".png", ".html")):
            continue
        try:
            texto = arq.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for w in set(re.findall(r"\b[A-ZÀ-Ý][a-zà-ÿ]{3,}\b", texto)):
            n = freq.get(w.lower(), 0)
            if 1 <= n <= 3 and w.lower() not in comuns:
                achados.setdefault((w, n), set()).add(rel)
    return achados


def main() -> int:
    arquivos = arquivos_versionados()
    estruturados, candidatos = [], {}
    for arq in arquivos:
        try:
            texto = arq.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for tipo, valor in pii.encontrar_pii_regex(texto):
            estruturados.append((arq.relative_to(config.RAIZ), tipo, valor))
        for m in _NOME.finditer(texto):
            nome = m.group(1)
            if pii._eh_prenome(nome.split()[0]) and nome not in PUBLICOS:
                candidatos.setdefault(nome, set()).add(str(arq.relative_to(config.RAIZ)))

    bruto = dados.ler_filtrada()
    # Holdout de 2026: inclui o bruto de 2026 quando ele foi baixado (data/raw/filtrada_2026/).
    extra = sorted((config.RAW / "filtrada_2026").glob("*_Pedidos_csv_2026.csv"))
    if extra:
        import pandas as pd
        bruto = pd.concat([bruto, dados.ler_csv(extra[-1])], ignore_index=True)
        print("texto bruto de 2025 e de 2026 incluído")
    corpus = "\n".join(bruto["ResumoSolicitacao"] + " " + bruto["DetalhamentoSolicitacao"])
    no_bruto = {n: a for n, a in candidatos.items() if n in corpus}
    # Todo número do bruto (com 6+ dígitos), normalizado só para dígitos, e todo e-mail.
    numeros_corpus = {re.sub(r"\D", "", m) for m in re.findall(r"\d[\d./\s()-]{4,}\d", corpus)}
    emails_corpus = set(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", corpus))

    def numero_real(valor: str) -> bool:
        if "@" in valor:
            return valor in emails_corpus
        digitos = re.sub(r"\D", "", valor)
        return len(digitos) >= 6 and digitos in numeros_corpus

    reais = [(a, t, v) for a, t, v in estruturados if numero_real(v)]
    trechos = trechos_de_pedido(arquivos, bruto["ResumoSolicitacao"] + " " + bruto["DetalhamentoSolicitacao"])

    print(f"{len(arquivos)} arquivos versionados verificados")
    print(f"dados estruturados: {len(estruturados)} no total, {len(reais)} encontrados no texto bruto (REAIS)")
    for a, t, v in reais:
        print(f"  REAL {a}: {t} {v!r}")
    # Termos em minúsculas (palavras-chave, explicações) não têm maiúscula para a busca acima.
    # Aqui: todo termo em minúsculas, em results/, que é prenome do IBGE e não é palavra comum.
    minusculos = {}
    for arq in arquivos:
        if not str(arq.relative_to(config.RAIZ)).startswith("results/"):
            continue
        for w in set(re.findall(r"(?<![\w])[a-zà-ÿ]{3,}(?![\w])", arq.read_text(encoding="utf-8", errors="ignore"))):
            if pii._eh_prenome(w):
                minusculos.setdefault(w, set()).add(str(arq.relative_to(config.RAIZ)))

    print(f"nomes que também aparecem no texto bruto da CGU: {len(no_bruto)} (revisar à mão)")
    for n, a in sorted(no_bruto.items()):
        print(f"  {n!r} em {sorted(a)}")
    print(f"termos em minúsculas em results/ que são prenomes: {len(minusculos)} (revisar à mão)")
    for w, a in sorted(minusculos.items()):
        print(f"  {w!r} em {sorted(a)[:3]}{' ...' if len(a) > 3 else ''}")
    raras = palavras_raras(arquivos, corpus)
    print(f"palavras raras do bruto (1 a 3 ocorrências) em arquivos versionados: {len(raras)} (revisar à mão)")
    for (w, n), a in sorted(raras.items(), key=lambda x: (x[0][1], x[0][0])):
        print(f"  {w!r} ({n}x no bruto) em {sorted(a)[:3]}{' ...' if len(a) > 3 else ''}")
    print(f"trechos de {N_PALAVRAS} palavras seguidas iguais a texto de até {MAX_PEDIDOS_COM_A_SEQUENCIA} pedidos (bruto): {len(trechos)}")
    for t, a in sorted(trechos.items())[:30]:
        print(f"  TRECHO {t!r} em {sorted(a)}")
    return 1 if (reais or trechos) else 0


if __name__ == "__main__":
    sys.exit(main())
