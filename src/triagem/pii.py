"""Mascaramento de dados pessoais antes de qualquer uso do texto.

Duas camadas:
1. Regex para dados com formato fixo: e-mail, CPF, telefone, CEP, RG, endereço com número.
2. NER do spaCy (modelo pt_core_news_md) para nomes de pessoas (entidade PER),
   filtrado por uma lista de prenomes do IBGE para não apagar termos do domínio.

O texto mascarado é o único que vai para os classificadores e para a API.
Limitações estão em DADOS.md.
"""
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

# A ordem importa: e-mail e documentos rotulados primeiro, depois CPF, depois telefone.
PADROES: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    # Documento pessoal rotulado: mantém o rótulo (sinal útil, ex. "PIS") e mascara só o número.
    ("DOCUMENTO", re.compile(
        r"(?i)(?P<pre>\b(?:passaporte|NIS|PIS|PASEP|NIT|CNH|CNS|cart[ãa]o (?:do )?SUS|t[íi]tulo de eleitor|"
        r"matr[íi]cula(?: SIAPE)?|SIAPE|OAB(?:/[A-Z]{2})?)\b[^\w\n]{0,4}(?:n[º°o]\.?\s*)?[:\-]?\s*)"
        r"[A-Z]{0,3}\d[\d.\-/]{5,}")),
    ("DATA_NASC", re.compile(
        r"(?i)(?P<pre>\b(?:data de nascimento|data nasc\.?|nascid[oa] em|nascimento)\s*[:\-]?\s*)"
        r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}")),
    ("CPF", re.compile(r"(?<![\d./-])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\d/-]|\.\d)")),
    ("TELEFONE", re.compile(
        r"(?i)\b(?:tel(?:efone)?|cel(?:ular)?|whats(?:app)?|fone|contato)\s*[:.]?\s*\+?[\d()][\d()\s.-]{7,18}\d")),
    ("TELEFONE", re.compile(r"(?<![\d./-])(?:\+?55\s?)?\(\d{2}\)\s?9?\d{4}[\s-]?\d{4}(?![\d])")),
    # Sem DDD, exige celular (9xxxx) ou fixo começando em 2-5 que não pareça ano ("2019-2023").
    ("TELEFONE", re.compile(
        r"(?<![\d./-])(?:\+?55\s?)?(?:\d{2}\s9?\d{4}|9\d{4}|(?!19|20)[2-5]\d{3})-\d{4}(?![\d/-]|\.\d)")),
    ("TELEFONE", re.compile(r"(?<![\d./-])\d{2}9\d{8}(?![\d/-]|\.\d)")),
    ("CEP", re.compile(r"(?i)\bCEP\s*[:.]?\s*\d{2}\.?\d{3}-?\d{3}\b")),
    ("CEP", re.compile(r"(?<![\d./-])\d{5}-\d{3}(?![\d/-]|\.\d)")),
    ("RG", re.compile(r"(?i)\b(?:RG|R\.G\.|carteira de identidade)\s*(?:n[º°o]\.?\s*)?[:\-]?\s*[\dXx][\dXx./-]{4,}")),
    ("ENDERECO", re.compile(
        r"(?i)\b(?:rua|avenida|av\.|travessa|alameda)\s+[^,\n;]{2,60},\s*(?:n[º°o]\.?\s*)?\d{1,5}")),
]



# Matrícula funcional (ex.: "matrícula SIAPE n. 4019283"). O padrão DOCUMENTO acima não cobre o "n." com ponto.
# Fica FORA de PADROES de propósito: ligar por padrão mudaria a máscara dos conjuntos já congelados (teste, holdouts
# de jan/fev e amostra do Marco 8) e o hash deles. Use mascarar(..., matricula=True) em conjuntos NOVOS.
PADRAO_MATRICULA = ("MATRICULA", re.compile(
    r"(?i)(?P<pre>\b(?:matr[íi]cula(?:\s+(?:SIAPE|funcional))?|SIAPE)\b[^\w\n]{0,4}(?:n\.?[º°o]?\.?\s*)?[:\-]?\s*)"
    r"\d(?:[.\-/]?\d){4,}"))   # 5 dígitos ou mais: não pega um ano ("SIAPE 2024")


def mascarar_regex(texto: str, contagem: Counter | None = None, matricula: bool = False) -> str:
    padroes = ([PADRAO_MATRICULA] if matricula else []) + PADROES
    for tipo, padrao in padroes:
        marcador = f"[{tipo}]"
        if "pre" in padrao.groupindex:
            texto, n = padrao.subn(lambda m, mk=marcador: m.group("pre") + mk, texto)
        else:
            texto, n = padrao.subn(marcador, texto)
        if contagem is not None and n:
            contagem[tipo] += n
    return texto


def encontrar_pii_regex(texto: str, matricula: bool = False) -> list[tuple[str, str]]:
    """Dados pessoais estruturados que sobraram no texto (usado nos testes e na varredura dos arquivos versionados).
    matricula=True também procura matrícula funcional (a varredura usa; os conjuntos congelados, não)."""
    achados = []
    for tipo, padrao in ([PADRAO_MATRICULA] if matricula else []) + PADROES:
        for m in padrao.finditer(texto):
            achados.append((tipo, m.group(0)))
    return achados


# ---------------------------------------------------------------- nomes de pessoas

REF = Path(__file__).resolve().parents[2] / "data" / "ref"
ARQ_PRENOMES = REF / "prenomes_ibge.txt"
ARQ_COMUNS = REF / "palavras_comuns.txt"
URL_PRENOMES = "https://data.brasil.io/dataset/genero-nomes/nomes.csv.gz"
FREQ_MIN_PRENOME = 200
FREQ_MIN_COMUM = 10
RAZAO_MIN_COMUM = 0.5
# Prenomes do IBGE que também são palavras com peso na triagem (MEI, LEI, BRASIL...).
PRENOMES_EXCLUIDOS = {
    "MEI", "LEI", "BRASIL", "SAO", "SANTA", "SANTO", "JUNHO", "DAS", "DOS", "DA", "DE", "DO",
    "SOCORRO", "LUZ", "SANTOS", "CRUZ", "ESPERANCA", "AURORA", "PAZ", "VITORIA", "GLORIA",
    "CARMO", "JESUS", "ROSARIO", "REAL", "BOLSA", "PORTO", "CAIXA", "BANCO",
}
# Siglas e nomes de instituição que nunca são absorvidos como parte de um nome.
NUNCA_NOME = {
    "MS", "PETROBRAS", "ANVISA", "BACEN", "BCB", "INSS", "MF", "MGI", "MEC", "ANEEL", "PF", "SUS",
    "CPF", "CNPJ", "RG", "LAI", "STF", "STJ", "TCU", "CGU", "AGU", "MPF", "OAB", "ENEM", "INEP",
    "CNH", "PIX", "IBAMA", "FUNAI", "DNIT", "MTE", "CEF", "BNDES", "SIAPE", "SEI", "NUP", "UF",
    "NOME", "EMAIL", "TELEFONE", "CEP", "DOCUMENTO", "ENDERECO", "DATA_NASC", "LTDA", "ME", "SA",
    # palavras institucionais e de tratamento, quase sempre escritas com maiúscula
    "MINISTERIO", "SECRETARIA", "AGENCIA", "INSTITUTO", "UNIVERSIDADE", "FUNDACAO", "DEPARTAMENTO",
    "COORDENACAO", "DIRETORIA", "GERENCIA", "SUPERINTENDENCIA", "PRESIDENCIA", "POLICIA", "RECEITA",
    "TESOURO", "CONSELHO", "COMISSAO", "PROGRAMA", "SERVICO", "SISTEMA", "EMPRESA", "COMPANHIA",
    "GOVERNO", "FEDERAL", "NACIONAL", "BRASILEIRO", "BRASILEIRA", "PREZADOS", "PREZADO", "PREZADA",
    "SENHOR", "SENHORA", "SENHORES", "SR", "SRA", "DR", "DRA", "ILMO", "ILMA", "EXMO", "EXMA",
    "ANALISTA", "DIRETOR", "DIRETORA", "COORDENADOR", "COORDENADORA", "ASSESSOR", "ASSESSORA",
    "HOSPITAL", "CLINICA", "ESCOLA", "COLEGIO", "FACULDADE", "CENTRO", "ASSOCIACAO", "CASA",
    # começo de nomes de lugar
    "SAO", "SANTA", "SANTO", "RIO", "PORTO", "BELO", "NOVA", "NOVO", "MATO", "GROSSO", "MINAS",
    "GERAIS", "ESPIRITO", "DISTRITO",
}
CONECTORES = {"da", "de", "do", "das", "dos", "e"}
TRATAMENTOS = {"SR", "SRA", "SRTA", "DR", "DRA", "PROF", "PROFA", "SENHOR", "SENHORA", "DONA", "DOM",
               "PREZADO", "PREZADA", "CARO", "CARA"}
SUFIXOS_NOME = {"FILHO", "FILHA", "JUNIOR", "JR", "NETO", "NETA", "SOBRINHO"}


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()


def gerar_lista_prenomes(destino: Path = ARQ_PRENOMES) -> None:
    """Baixa a lista de prenomes do Censo 2010 (IBGE, via brasil.io) e grava os frequentes."""
    import gzip
    import io
    import urllib.request

    import pandas as pd

    req = urllib.request.Request(URL_PRENOMES, headers={"User-Agent": "triagem-pedidos-publicos"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        bruto = gzip.decompress(resp.read())
    df = pd.read_csv(io.BytesIO(bruto), usecols=["first_name", "frequency_total"])
    nomes = sorted(set(df.loc[df["frequency_total"] >= FREQ_MIN_PRENOME, "first_name"]) - PRENOMES_EXCLUIDOS)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(nomes) + "\n", encoding="utf-8")
    print(f"{len(nomes)} prenomes em {destino}")


def gerar_palavras_comuns(textos, destino: Path = ARQ_COMUNS) -> None:
    """Palavras usadas como palavra comum no corpus, e não como nome próprio.

    Critério: aparece em minúsculas pelo menos FREQ_MIN_COMUM vezes e pelo menos metade das vezes
    em que aparece com inicial maiúscula. "registro" (5.280 x 1.144) é comum; "silva" (126 x 1.854)
    não é, porque quase sempre aparece como sobrenome."""
    minus, maius = Counter(), Counter()
    for t in textos:
        # Tira e-mails etc. antes: "fulana.souza@..." não pode contar como "fulana" em minúsculas.
        for w in re.findall(r"\b[^\W\d_]{3,}\b", mascarar_regex(t)):
            if w.islower():
                minus[w] += 1
            elif w[0].isupper():
                maius[w.lower()] += 1
    comuns = sorted({_sem_acento(w) for w, n in minus.items()
                     if n >= FREQ_MIN_COMUM and n >= RAZAO_MIN_COMUM * maius[w]})
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(comuns) + "\n", encoding="utf-8")
    print(f"{len(comuns)} palavras comuns em {destino}")


@lru_cache(maxsize=1)
def _prenomes() -> frozenset[str]:
    return frozenset(ARQ_PRENOMES.read_text(encoding="utf-8").split())


@lru_cache(maxsize=1)
def _comuns() -> frozenset[str]:
    return frozenset(ARQ_COMUNS.read_text(encoding="utf-8").split())


def _eh_prenome(palavra: str) -> bool:
    k = _sem_acento(palavra)
    return k in _prenomes() and k not in _comuns() and k not in NUNCA_NOME


def _parece_parte_de_nome(palavra: str) -> bool:
    """Palavra com inicial maiúscula (ou toda maiúscula) que não é palavra comum nem sigla conhecida."""
    if not re.fullmatch(r"[^\W\d_][^\W\d_'’-]*", palavra) or not palavra[0].isupper():
        return False
    k = _sem_acento(palavra)
    if k in SUFIXOS_NOME:
        return True
    if re.fullmatch(r"[IVXLC]+", k):  # "Fator VII Recombinante"
        return False
    return len(k) >= 2 and k not in _comuns() and k not in NUNCA_NOME


def parece_nome_de_pessoa(trecho: str) -> bool:
    """Filtro sobre a entidade PER do spaCy, que tem muitos falsos positivos neste domínio
    ("Agradeço", "Bacen", "Selic", "Registro de Operações Financeiras"...). Aceita se:
    - a primeira palavra é prenome frequente do IBGE e não é palavra comum do corpus; ou
    - tem 2+ palavras com maiúscula e nenhuma é palavra comum ou sigla conhecida."""
    if any(c.isdigit() or c in "§()[]/" for c in trecho):
        return False
    palavras = re.findall(r"[^\W\d_]+", trecho)
    while palavras and _sem_acento(palavras[0]) in TRATAMENTOS:
        palavras = palavras[1:]
    if not palavras:
        return False
    if _eh_prenome(palavras[0]):
        return True
    nucleo = [p for p in palavras if p.lower() not in CONECTORES]
    return len(nucleo) >= 2 and all(_parece_parte_de_nome(p) for p in nucleo)


@lru_cache(maxsize=1)
def _nlp():
    import spacy
    return spacy.load("pt_core_news_md", disable=["parser", "lemmatizer", "morphologizer", "attribute_ruler"])


def _contar(contagem, n=1):
    if contagem is not None:
        contagem["NOME"] += n


# Nome de pessoa que batiza instituição, lugar ou programa: "Plataforma Nilo Peçanha",
# "Fundação Oswaldo Cruz", "município de Frederico Westphalen". Não é dado pessoal e é pista da triagem.
_PREFIXO_INSTITUCIONAL = re.compile(
    r"(?i)\b(?:plataforma|funda[çc][ãa]o|munic[íi]pio de|cidade de|hospital|instituto|escola|col[ée]gio|"
    r"universidade|rodovia|ponte|avenida|aeroporto|programa|pr[êe]mio|lei|usina|campus|s[ãa]o|santo|santa)"
    r"[ \t]*$")


def _depois_de_prefixo_institucional(texto: str, inicio: int) -> bool:
    return bool(_PREFIXO_INSTITUCIONAL.search(texto[max(0, inicio - 30):inicio]))


def _mascarar_ner(doc, contagem: Counter | None) -> str:
    texto = doc.text
    # Substitui de trás para frente para não invalidar os índices.
    for ent in sorted((e for e in doc.ents if e.label_ == "PER"), key=lambda e: e.start_char, reverse=True):
        if _depois_de_prefixo_institucional(texto, ent.start_char):
            continue
        if parece_nome_de_pessoa(ent.text):
            # "Ricardo Alves Hospital Santa Casa": o nome acaba antes da palavra institucional.
            fim = ent.end_char
            for w in re.finditer(r"[^\W\d_]+", ent.text):
                if w.start() > 0 and _sem_acento(w.group(0)) in NUNCA_NOME:
                    fim = ent.start_char + w.start()
                    break
            sobra = texto[ent.start_char:fim].rstrip()
            fim = ent.start_char + len(sobra)
            texto = texto[: ent.start_char] + "[NOME]" + texto[fim:]
            _contar(contagem)
    return texto


# Sequências de palavras em caixa alta ou com inicial maiúscula, com conectores (de, da, dos, e).
_SEQ_MAIUSC = re.compile(r"\b[A-ZÀ-ÖØ-Ý]{2,}(?:[ \t]+(?:(?:D[AEO]S?|E)[ \t]+)?[A-ZÀ-ÖØ-Ý]{2,})+\b")
_SEQ_TITULO = re.compile(
    r"\b[A-ZÀ-ÖØ-Ý][a-zà-ÿ]+(?:[ \t]+(?:(?:d[aeo]s?|e)[ \t]+)?[A-ZÀ-ÖØ-Ý][a-zà-ÿ]+)+\b")


def _mascarar_sequencias(texto: str, contagem: Counter | None) -> str:
    """Nomes que o NER não pega: em caixa alta ("SUS JULIANA PAULA FERREIRA") ou em listas
    ("Felipe Travenzi Rodrigo Mancebo"). Dentro da sequência, mascara do primeiro prenome em diante,
    enquanto as palavras parecerem nome, se forem 2 ou mais."""
    def troca(m):
        seq = m.group(0)
        toks = list(re.finditer(r"\S+", seq))
        partes, cursor, i = [], 0, 0
        while i < len(toks):
            if not _eh_prenome(toks[i].group(0)) or _depois_de_prefixo_institucional(
                    m.string, m.start() + toks[i].start()):
                i += 1
                continue
            fim, n = i, 1
            for j in range(i + 1, len(toks)):
                w = toks[j].group(0)
                if w.lower() == "e":  # "Paulo e Santa Catarina": "e" separa, não liga nome
                    break
                if w.lower() in CONECTORES:
                    continue
                if not _parece_parte_de_nome(w):
                    break
                fim, n = j, n + 1
            if n >= 2:
                _contar(contagem)
                partes.append(seq[cursor: toks[i].start()] + "[NOME]")
                cursor = toks[fim].end()
            i = fim + 1
        partes.append(seq[cursor:])
        return "".join(partes)
    texto = _SEQ_MAIUSC.sub(troca, texto)
    return _SEQ_TITULO.sub(troca, texto)


_TOKEN = r"[^\W\d_][^\W\d_'’-]*"
# Pistas de que logo depois vem o nome de quem escreve.
_PISTA = re.compile(
    r"(?P<pre>(?i:\b(?:meu nome (?:é|e)|me chamo|eu,|nome(?: completo)?\s*:|atenciosamente|att\.?|atte\.?|"
    r"cordialmente|obrigad[oa]|grat[oa]|assinado|requerente\s*:|solicitante\s*:))(?![^\W\d_])[ \t]*[,.:;–-]?\s*)"
    rf"(?P<nome>{_TOKEN}(?:[ \t]+{_TOKEN}){{0,7}})")


def _mascarar_apos_pista(texto: str, contagem: Counter | None) -> str:
    """'Meu nome é Lisandre Bortoval', 'Atenciosamente, Ardiel Mendrano': o nome pode ter prenome raro."""
    def troca(m):
        toks = m.group("nome").split()
        usados = 0
        for i, t in enumerate(toks):
            if _parece_parte_de_nome(t):
                usados = i + 1
            elif t.lower() in CONECTORES and i + 1 < len(toks) and _parece_parte_de_nome(toks[i + 1]):
                continue
            else:
                break
        if usados == 0:
            return m.group(0)
        _contar(contagem)
        resto = m.group("nome").split(maxsplit=usados)
        cauda = (" " + resto[usados]) if len(resto) > usados else ""
        return m.group("pre") + "[NOME]" + cauda
    return _PISTA.sub(troca, texto)


_TRATAMENTO = re.compile(
    r"(?P<pre>(?i:\b(?:sr|sra|srta|dr|dra|prof|profa|senhor|senhora|dona|dom|prezad[oa]|car[oa]))\.?[ \t]+)"
    rf"(?P<nome>{_TOKEN}(?:[ \t]+{_TOKEN}){{0,7}})")


def _parte_de_nome_tolerante(palavra: str) -> bool:
    """Depois de 'Sr./Sra./Prezado', aceita sobrenome que também é palavra comum ('Torres', 'Leite')."""
    if not re.fullmatch(r"[^\W\d_][^\W\d_'’-]*", palavra) or not palavra[0].isupper():
        return False
    k = _sem_acento(palavra)
    return k not in NUNCA_NOME and not re.fullmatch(r"[IVXLC]+", k)


def _mascarar_apos_tratamento(texto: str, contagem: Counter | None) -> str:
    """'Sra. Fulana Torres da Silva', 'Prezado Ivan': prenome do IBGE depois de pronome de tratamento.
    Aqui o sobrenome pode ser palavra comum, e um prenome sozinho já é mascarado."""
    def troca(m):
        toks = m.group("nome").split()
        if not _eh_prenome(toks[0]):
            return m.group(0)
        usados = 1
        for i in range(1, len(toks)):
            t = toks[i]
            if t.lower() in CONECTORES and t.lower() != "e" and i + 1 < len(toks) \
                    and _parte_de_nome_tolerante(toks[i + 1]):
                continue
            if not _parte_de_nome_tolerante(t):
                break
            usados = i + 1
        _contar(contagem)
        resto = m.group("nome").split(maxsplit=usados)
        return m.group("pre") + "[NOME]" + ((" " + resto[usados]) if len(resto) > usados else "")
    return _TRATAMENTO.sub(troca, texto)


_VIZINHO_DIR = re.compile(rf"\[NOME\]((?:[ \t]+(?:(?:d[aeo]s?|D[AEO]S?|e)[ \t]+)?{_TOKEN})+)")
_VIZINHO_ESQ = re.compile(rf"({_TOKEN})[ \t]+\[NOME\]")


def _absorver_vizinhos(texto: str) -> str:
    """Junta ao [NOME] sobrenomes que ficaram de fora: '[NOME] DE ARRUDA', 'Jeyson [NOME]'."""
    def direita(m):
        toks = m.group(1).split()
        usados = 0
        for i, t in enumerate(toks):
            if _parece_parte_de_nome(t):
                usados = i + 1
            elif t.lower() in CONECTORES:
                continue
            else:
                break
        if usados == 0:
            return m.group(0)
        resto = m.group(1).split(maxsplit=usados)
        return "[NOME]" + ((" " + resto[usados]) if len(resto) > usados else "")

    def esquerda(m):
        return "[NOME]" if _parece_parte_de_nome(m.group(1)) else m.group(0)

    anterior = None
    while anterior != texto:
        anterior = texto
        texto = _VIZINHO_DIR.sub(direita, texto)
        texto = _VIZINHO_ESQ.sub(esquerda, texto)
        texto = re.sub(r"\[NOME\](?:[ \t]+(?:d[aeo]s?|e)?[ \t]*\[NOME\])+", "[NOME]", texto)
    return texto


def mascarar(textos: list[str], contagem: Counter | None = None, batch_size: int = 64, matricula: bool = False) -> list[str]:
    """Regex estruturada -> NER filtrado -> sequências -> tratamento ('Sra.') -> pistas ('Meu nome é') -> vizinhos.
    Devolve os textos na mesma ordem. matricula=True também mascara matrícula funcional (conjuntos novos)."""
    pre = [mascarar_regex(t, contagem, matricula) for t in textos]
    saida = []
    for doc in _nlp().pipe(pre, batch_size=batch_size):
        t = _mascarar_ner(doc, contagem)
        t = _mascarar_sequencias(t, contagem)
        t = _mascarar_apos_tratamento(t, contagem)
        t = _mascarar_apos_pista(t, contagem)
        saida.append(_absorver_vizinhos(t))
    return saida
