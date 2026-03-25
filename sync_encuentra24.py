#!/usr/bin/env python3
"""
ResidenciasCostaRica — sync_encuentra24.py
==========================================
Usa Playwright para renderizar encuentra24.com (SPA),
extrae las últimas 6 propiedades del perfil y actualiza
properties-data.js con imágenes descargadas.

Uso:
  python3 sync_encuentra24.py
"""

import re
import json
import sys
import socket
import requests
from pathlib import Path
from datetime import datetime

# Playwright se instala con: pip3 install playwright && python3 -m playwright install chromium
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("ERROR: Playwright no está instalado.")
    print("Instalar con: pip3 install playwright && python3 -m playwright install chromium")
    sys.exit(1)

# ── Configuración ─────────────────────────────────────────────
PROJECT_DIR  = Path(__file__).parent
ASSETS_DIR   = PROJECT_DIR / "assets"
DATA_FILE    = PROJECT_DIR / "properties-data.js"
PROFILE_URL  = "https://www.encuentra24.com/costa-rica-es/user/profile/id/13021117"
MAX_PROPS    = 50

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

ASSETS_DIR.mkdir(exist_ok=True)


# ── Extraer datos del DOM renderizado ─────────────────────────
def parse_property_page(page, prop_id: str) -> dict:
    """Extrae datos de una página de propiedad ya cargada en Playwright."""

    # og:title tiene el formato:
    # "Título | N Recamaras por PRECIO en ZONA"
    og_title_el = page.query_selector('meta[property="og:title"]')
    og_title = og_title_el.get_attribute("content").strip() if og_title_el else ""

    # ── Título ────────────────────────────────────────────
    title = og_title.split("|")[0].strip() if og_title else f"Propiedad {prop_id}"

    # ── Precio ────────────────────────────────────────────
    price = "Consultar"
    price_el = page.query_selector('[class*="price"], [class*="Price"], [itemprop="price"]')
    if price_el:
        t = price_el.inner_text().strip()
        if t and any(c.isdigit() for c in t):
            price = t
    if price == "Consultar" and og_title:
        pm = re.search(r'por\s+([\d,\.]+)', og_title, re.I)
        if pm:
            try:
                price_num = float(pm.group(1).replace(",", ""))
                price = f"${int(price_num):,}" if price_num < 2_000_000 else f"₡{int(price_num):,}"
            except Exception:
                pass

    # ── Ubicación ─────────────────────────────────────────
    # h2 suele ser "Casas en ZONA | Título"
    location = "Costa Rica"
    h2_el = page.query_selector("h2")
    if h2_el:
        h2_text = h2_el.inner_text().strip()
        loc_m = re.match(r'[^|]+en\s+([^|]+)', h2_text, re.I)
        if loc_m:
            location = loc_m.group(1).strip()
    if location == "Costa Rica" and og_title:
        loc_m2 = re.search(r'en\s+([^|]+)$', og_title, re.I)
        if loc_m2:
            location = loc_m2.group(1).strip()

    # ── Habitaciones y baños ──────────────────────────────
    beds, baths, area = 0, 0, ""
    full_text = page.content()

    rec_m = re.search(r'(\d+)\s*Recamara', og_title, re.I) if og_title else None
    if rec_m:
        beds = int(rec_m.group(1))
    else:
        bed_m = re.search(r'(\d+)\s*(?:hab(?:itaci[oó]n(?:es)?)?|cuarto|dormitorio|recamara)', full_text, re.I)
        if bed_m:
            beds = int(bed_m.group(1))

    bath_m = re.search(r'(\d+)\s*(?:ba[ñn]o|bath)', full_text, re.I)
    if bath_m:
        baths = int(bath_m.group(1))

    area_m = re.search(r'(\d[\d\.,]*)\s*m[²2]', full_text)
    if area_m:
        area = f"{area_m.group(1)} m²"

    # ── Imagen ────────────────────────────────────────────
    image_url = ""
    og_img = page.query_selector('meta[property="og:image"]')
    if og_img:
        image_url = og_img.get_attribute("content") or ""

    if not image_url:
        for img in page.query_selector_all("img"):
            src = img.get_attribute("src") or ""
            if src and any(ext in src for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                if "encuentra24" in src or "e24img" in src:
                    image_url = src
                    break

    # Tipo
    title_low = title.lower()
    if "penthouse" in title_low:
        prop_type = "Penthouse"
    elif "apartamento" in title_low or " apto" in title_low:
        prop_type = "Apartamento"
    elif "terreno" in title_low or "lote" in title_low:
        prop_type = "Terreno"
    elif "finca" in title_low:
        prop_type = "Finca"
    elif "local" in title_low or "comercial" in title_low:
        prop_type = "Local"
    else:
        prop_type = "Casa"

    # Badge
    if "alquiler" in title_low:
        badge, badge_class = "Venta / Alquiler", "badge-special"
    elif "oportunidad" in title_low or "remate" in title_low:
        badge, badge_class = "Oportunidad", "badge-opp"
    else:
        badge, badge_class = "En Venta", ""

    return {
        "id":         f"E24-{prop_id}",
        "title":      title,
        "price":      price,
        "location":   location,
        "beds":       beds,
        "baths":      baths,
        "area":       area,
        "type":       prop_type,
        "badge":      badge,
        "badgeClass": badge_class,
        "image_url":  image_url,   # temporal, se reemplaza abajo
        "e24id":      prop_id,
        "wa":         f"Me%20interesa%20la%20propiedad%20{prop_id}%20en%20encuentra24",
    }


# ── Descargar imagen ──────────────────────────────────────────
def download_image(image_url: str, prop_id: str) -> str:
    if not image_url:
        return ""
    try:
        r = requests.get(image_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            path = ASSETS_DIR / f"e24-{prop_id}.jpg"
            path.write_bytes(r.content)
            return f"assets/e24-{prop_id}.jpg"
    except Exception as e:
        print(f"    ⚠  Imagen {prop_id}: {str(e)[:40]}")
    return ""

FALLBACK_IMG = "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=800&q=80"


# ── Guardar properties-data.js ────────────────────────────────
def update_data_file(properties: list):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    js = f"// Auto-generado por sync_encuentra24.py — {now}\n"
    js += "window.DEFAULT_PROPERTIES = "
    js += json.dumps(properties, ensure_ascii=False, indent=2)
    js += ";"
    DATA_FILE.write_text(js, encoding="utf-8")
    print(f"\n✓ properties-data.js actualizado con {len(properties)} propiedades")


# ── Sync principal ────────────────────────────────────────────
def check_internet() -> bool:
    try:
        socket.setdefaulttimeout(5)
        socket.create_connection(("8.8.8.8", 53))
        return True
    except OSError:
        return False


def sync():
    print("=" * 55)
    print(f"Sincronización Encuentra24 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55 + "\n")

    if not check_internet():
        print("✗ Sin conexión a internet. Abortando.")
        sys.exit(0)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="es-CR",
        )
        page = ctx.new_page()

        # ── Paso 1: Perfil — raspar TODAS las páginas ─────────
        prop_urls_map = {}  # id -> url_completa (preserva orden de aparición)
        cookies_accepted = False

        def scrape_profile_page(html_content):
            """Extrae URLs de propiedades del HTML de una página de perfil."""
            hrefs = re.findall(
                r'href="(/costa-rica-es/bienes-raices[^"]+?/(\d{7,}))"',
                html_content
            )
            added = 0
            for href, pid in hrefs:
                if pid != "13021117" and pid not in prop_urls_map:
                    prop_urls_map[pid] = "https://www.encuentra24.com" + href
                    added += 1
            return added

        def get_total_pages(html_content):
            """Detecta el número total de páginas en el perfil."""
            nums = re.findall(
                r'/user/profile/id/13021117/page/(\d+)', html_content
            )
            return max((int(n) for n in nums), default=1)

        # Página 1
        print(f"📋 Cargando perfil página 1:\n   {PROFILE_URL}\n")
        page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)

        # Aceptar cookies (solo la primera vez)
        try:
            page.evaluate("document.querySelector('.fc-button.fc-data-preferences-accept-all').click()")
            page.wait_for_timeout(800)
            cookies_accepted = True
        except Exception:
            pass

        html = page.content()
        found_p1 = scrape_profile_page(html)
        total_pages = get_total_pages(html)
        print(f"  Página 1: {found_p1} propiedades · Total de páginas detectadas: {total_pages}")

        # Páginas 2..N
        for pnum in range(2, total_pages + 1):
            page_url = f"{PROFILE_URL}/page/{pnum}"
            print(f"  Cargando página {pnum}: {page_url}")
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(1000)
                if not cookies_accepted:
                    try:
                        page.evaluate("document.querySelector('.fc-button.fc-data-preferences-accept-all').click()")
                        page.wait_for_timeout(500)
                        cookies_accepted = True
                    except Exception:
                        pass
                html_n = page.content()
                found_n = scrape_profile_page(html_n)
                print(f"  Página {pnum}: {found_n} propiedades nuevas")
                # Si una página no agrega nada nueva, probablemente no existe
                if found_n == 0:
                    print(f"  Sin propiedades nuevas en página {pnum}, deteniendo.")
                    break
            except Exception as e:
                print(f"  ⚠ Error en página {pnum}: {e}")
                break

        selected = list(prop_urls_map.items())[:MAX_PROPS]
        print(f"\n  ✓ Total acumulado: {len(prop_urls_map)} propiedades en {total_pages} página(s)")
        print(f"  ✓ Se descargarán las primeras {len(selected)}")

        if not selected:
            print("  ✗ No se encontraron propiedades. Abortando.")
            browser.close()
            return False

        # ── Paso 2: Datos de cada propiedad ───────────────────
        print(f"\n🏠 Descargando {len(selected)} propiedades...\n")
        properties = []

        for prop_id, prop_url in selected:
            if not prop_url:
                print(f"  ⚠  {prop_id} — URL desconocida, saltando")
                continue
            try:
                page.goto(prop_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(800)
                try:
                    page.evaluate("document.querySelector('.fc-button.fc-data-preferences-accept-all').click()")
                    page.wait_for_timeout(500)
                except Exception:
                    pass

                data = parse_property_page(page, prop_id)
                image_url = data.pop("image_url", "")
                local_img = download_image(image_url, prop_id)
                data["image"] = local_img or FALLBACK_IMG
                data["e24url"] = prop_url

                print(f"  ✓ {prop_id} — {data['title'][:55]}")
                properties.append(data)

            except PWTimeout:
                print(f"  ⚠  {prop_id} — Timeout")
            except Exception as e:
                print(f"  ✗ {prop_id} — {e}")

        browser.close()

    if not properties:
        print("\n✗ No se obtuvieron propiedades.")
        return False

    update_data_file(properties)
    print(f"\n✅ Sync completado: {len(properties)}/{len(selected)} propiedades\n")
    return True


if __name__ == "__main__":
    sync()
