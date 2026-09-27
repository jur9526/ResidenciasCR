#!/usr/bin/env python3
"""
ResidenciasCostaRica — indexnow.py
==================================
Avisa a Bing (y demás buscadores de IndexNow) qué URLs cambiaron, para que
las indexen sin esperar. ChatGPT busca en el índice de Bing.

Uso:
  python3 indexnow.py                      # todas las URLs del sitemap
  python3 indexnow.py archivo.html ...     # solo esas páginas (rutas del repo)
"""

import re
import sys
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).parent
SITE = "https://residenciascostarica.com"
HOST = "residenciascostarica.com"


def key() -> str:
    # El archivo <key>.txt en la raíz del sitio prueba que el dominio es nuestro
    for f in PROJECT_DIR.glob("*.txt"):
        if re.fullmatch(r"[0-9a-f]{32}", f.stem) and f.read_text().strip() == f.stem:
            return f.stem
    raise SystemExit("No se encontró el archivo de clave de IndexNow")


def url_for(path: str) -> str:
    path = path.removesuffix(".html").removesuffix("index")
    return f"{SITE}/{path}"


def main():
    if len(sys.argv) > 1:
        urls = sorted({url_for(p) for p in sys.argv[1:]})
    else:
        urls = re.findall(r"<loc>([^<]+)</loc>", (PROJECT_DIR / "sitemap.xml").read_text())
    if not urls:
        print("IndexNow: nada que avisar")
        return
    k = key()
    r = requests.post("https://api.indexnow.org/indexnow", timeout=30, json={
        "host": HOST, "key": k, "keyLocation": f"{SITE}/{k}.txt", "urlList": urls,
    })
    print(f"IndexNow: {len(urls)} URLs → HTTP {r.status_code}")
    # 200/202 = aceptado; otro código no debe romper el sync
    if r.status_code not in (200, 202):
        print(r.text[:300])


if __name__ == "__main__":
    main()
