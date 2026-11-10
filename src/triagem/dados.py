"""Download dos arquivos da CGU e leitura dos CSVs.

A CGU atualiza os arquivos todos os dias. Por isso o download só acontece se o
arquivo ainda não existir, e o SHA-256 de cada zip fica em results/manifesto_download.json.
O conjunto de teste (data/test.jsonl) é congelado e não depende de um novo download.
"""
import hashlib
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from triagem import config


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _baixar(url: str, destino_dir: Path) -> dict:
    destino_dir.mkdir(parents=True, exist_ok=True)
    zip_path = destino_dir / url.rsplit("/", 1)[1]
    if not zip_path.exists():
        print(f"baixando {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "triagem-pedidos-publicos"})
        with urllib.request.urlopen(req, timeout=600) as resp, open(zip_path, "wb") as out:
            ultima_mod = resp.headers.get("Last-Modified")
            while bloco := resp.read(1 << 20):
                out.write(bloco)
    else:
        ultima_mod = None
        print(f"já existe: {zip_path.name}")
    with zipfile.ZipFile(zip_path) as z:
        nomes = z.namelist()
        if not all((destino_dir / n).exists() for n in nomes):
            z.extractall(destino_dir)
    return {
        "url": url,
        "arquivo": zip_path.name,
        "sha256": sha256_arquivo(zip_path),
        "bytes": zip_path.stat().st_size,
        "last_modified_servidor": ultima_mod,
        "conteudo": sorted(nomes),
    }


def baixar_tudo() -> None:
    manifesto_path = config.RESULTS / "manifesto_download.json"
    anterior = json.loads(manifesto_path.read_text()) if manifesto_path.exists() else {}
    itens = [
        _baixar(config.URL_COMPLETA, config.DIR_COMPLETA),
        _baixar(config.URL_FILTRADA, config.DIR_FILTRADA),
    ]
    for item in itens:
        prev = next((p for p in anterior.get("arquivos", []) if p["arquivo"] == item["arquivo"]), None)
        if prev and prev["sha256"] != item["sha256"]:
            print(f"AVISO: {item['arquivo']} mudou desde o manifesto anterior.", file=sys.stderr)
        if prev and not item["last_modified_servidor"]:
            item["last_modified_servidor"] = prev.get("last_modified_servidor")
    manifesto = {
        "registrado_em": anterior.get("registrado_em") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "arquivos": itens,
    }
    config.RESULTS.mkdir(exist_ok=True)
    manifesto_path.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n")
    print(f"manifesto em {manifesto_path}")


def _csv_pedidos(diretorio: Path) -> Path:
    candidatos = sorted(diretorio.glob(f"*_Pedidos_csv_{config.ANO}.csv"))
    if not candidatos:
        raise FileNotFoundError(f"CSV de pedidos não encontrado em {diretorio}. Rode `make dados`.")
    return candidatos[-1]


def ler_csv(caminho: Path) -> pd.DataFrame:
    """Os CSVs da CGU são UTF-16, separados por ';', com espaços em campos vazios."""
    df = pd.read_csv(caminho, sep=";", encoding="utf-16", dtype=str, keep_default_na=False)
    return df.apply(lambda s: s.str.strip())


def ler_completa() -> pd.DataFrame:
    return ler_csv(_csv_pedidos(config.DIR_COMPLETA))


def ler_filtrada() -> pd.DataFrame:
    return ler_csv(_csv_pedidos(config.DIR_FILTRADA))


if __name__ == "__main__":
    baixar_tudo()
