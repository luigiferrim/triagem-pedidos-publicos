"""Procura dados pessoais nos arquivos que vão para o repositório público.

Roda antes de cada commit (`make varredura`). Verifica os arquivos que o git versionaria
(rastreados + novos não ignorados) e lista:
1. CPF, e-mail, telefone, CEP e documentos (mesmas regex da máscara) cujo número APARECE no texto
   bruto da CGU, ou seja, dado real copiado da base. Valores que não estão no bruto são fictícios (fixtures);
2. sequências com cara de nome (prenome do IBGE + sobrenome) que aparecem no texto bruto da CGU.

Achados do tipo 2 precisam de revisão humana: podem ser autoridade pública, instituição ou lugar.
Sai com código 1 se houver achado do tipo 1.
"""
import re
import subprocess
import sys
from pathlib import Path

from triagem import config, dados, pii

# Pessoas públicas citadas em papel público e nomes de lugar/instituição usados como exemplo.
PUBLICOS = {
    "Fernando Haddad", "Gabriel Galípolo", "Nilo Peçanha", "Oswaldo Cruz", "Frederico Westphalen",
    "Gabriel da Cachoeira", "Maria da Penha", "Carolina Bori", "Paulo Guerra", "Costa do Sol",
}
_NOME = re.compile(r"\b([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ý][a-zà-ÿ]+){1,3})\b")


def arquivos_versionados() -> list[Path]:
    saida = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                           cwd=config.RAIZ, capture_output=True, text=True, check=True).stdout
    return [config.RAIZ / linha for linha in saida.splitlines()
            if linha and not linha.startswith("data/ref/")]  # listas de palavras, sem frases


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

    print(f"{len(arquivos)} arquivos versionados verificados")
    print(f"dados estruturados: {len(estruturados)} no total, {len(reais)} encontrados no texto bruto (REAIS)")
    for a, t, v in reais:
        print(f"  REAL {a}: {t} {v!r}")
    print(f"nomes que também aparecem no texto bruto da CGU: {len(no_bruto)} (revisar à mão)")
    for n, a in sorted(no_bruto.items()):
        print(f"  {n!r} em {sorted(a)}")
    return 1 if reais else 0


if __name__ == "__main__":
    sys.exit(main())
