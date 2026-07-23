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
MAX_PAGES    = 8

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

    # ── Imágenes (múltiples) ──────────────────────────────
    image_url = ""
    all_images = []

    def is_property_photo(url):
        """Solo fotos reales de propiedades (photos.encuentra24.com)."""
        return "photos.encuentra24.com" in url

    # og:image
    og_img = page.query_selector('meta[property="og:image"]')
    if og_img:
        url = og_img.get_attribute("content") or ""
        if url and is_property_photo(url):
            image_url = url
            all_images.append(url)

    # Buscar galería: src y data-src (lazy-loaded)
    seen = set(all_images)
    for img in page.query_selector_all("img"):
        for attr in ("src", "data-src", "data-lazy-src"):
            src = img.get_attribute(attr) or ""
            if src and src not in seen and is_property_photo(src):
                all_images.append(src)
                seen.add(src)
        if len(all_images) >= 15:
            break

    # También buscar en sourceset de <picture>/<source>
    for src_el in page.query_selector_all("source[srcset], img[srcset]"):
        srcset = src_el.get_attribute("srcset") or ""
        for part in srcset.split(","):
            url = part.strip().split(" ")[0]
            if url and url not in seen and is_property_photo(url):
                all_images.append(url)
                seen.add(url)
        if len(all_images) >= 15:
            break

    if not image_url and all_images:
        image_url = all_images[0]

    # ── Descripción ───────────────────────────────────────
    description = ""
    for sel in [
        '[class*="description"]', '[class*="Description"]',
        '[data-testid*="description"]', 'section p',
    ]:
        try:
            els = page.query_selector_all(sel)
            for el in els:
                text = el.inner_text().strip()
                if len(text) > 80:
                    description = text
                    break
        except Exception:
            pass
        if description:
            break

    # ── Amenidades — extraer de sección "Amenidades" en descripción ──
    amenities = []
    if description:
        lines = description.splitlines()
        in_amen = False
        for line in lines:
            stripped = line.strip()
            # Detectar encabezado de sección (línea corta que termina en : o contiene solo el título)
            if not in_amen and re.match(
                r'^(amenidades?|amenities|servicios del condominio)[^.]{0,30}$',
                stripped, re.I
            ):
                in_amen = True
                continue
            if in_amen:
                if not stripped:
                    continue
                # Nuevo encabezado de sección — detener
                if re.match(r'^(distribuci|caracter|descripci|ubicaci|precio|contáct|506|\+506|acceso)', stripped, re.I):
                    break
                item = re.sub(r'^[\s•\-–*·\(\)]+', '', stripped).strip()
                item = re.sub(r'\s+', ' ', item)
                if 2 < len(item) <= 60 and item not in amenities:
                    amenities.append(item)
            if len(amenities) >= 20:
                break

    # ── Parking ───────────────────────────────────────────
    parking = 0
    park_m = re.search(r'(\d+)\s*(?:parking|parqueo|estacionamiento|garaje)', full_text, re.I)
    if park_m:
        parking = int(park_m.group(1))

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
        "id":          f"E24-{prop_id}",
        "title":       title,
        "price":       price,
        "location":    location,
        "beds":        beds,
        "baths":       baths,
        "area":        area,
        "parking":     parking,
        "type":        prop_type,
        "badge":       badge,
        "badgeClass":  badge_class,
        "description": description,
        "amenities":   amenities,
        "image_url":   image_url,    # temporal, se reemplaza abajo
        "all_images":  all_images,   # todas las URLs de e24 (sin descargar)
        "e24id":       prop_id,
        "wa":          f"Me%20interesa%20la%20propiedad%20{prop_id}%20en%20encuentra24%20(v%C3%ADa%20residenciascostarica.com)",
    }


# ── Descargar imagen → WebP optimizado ───────────────────────
def download_image(image_url: str, prop_id: str) -> str:
    if not image_url:
        return ""
    try:
        from PIL import Image
        import io
        r = requests.get(image_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            if img.width > 800:
                h = int(img.height * 800 / img.width)
                img = img.resize((800, h), Image.LANCZOS)
            path = ASSETS_DIR / f"e24-{prop_id}.webp"
            img.save(path, "WebP", quality=78, method=6)
            return f"assets/e24-{prop_id}.webp"
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
def sync():
    print("=" * 55)
    print(f"Sincronización Encuentra24 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55 + "\n")

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

        # Página 1
        print(f"📋 Cargando perfil página 1:\n   {PROFILE_URL}\n")
        page.goto(PROFILE_URL, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(3000)

        # Aceptar cookies (solo la primera vez)
        try:
            page.evaluate("document.querySelector('.fc-button.fc-data-preferences-accept-all').click()")
            page.wait_for_timeout(2000)
            cookies_accepted = True
        except Exception:
            pass

        html = page.content()
        found_p1 = scrape_profile_page(html)
        print(f"  Página 1: {found_p1} propiedades")

        # Páginas 2..MAX_PAGES (usa ?page=N)
        for pnum in range(2, MAX_PAGES + 1):
            page_url = f"{PROFILE_URL}?page={pnum}"
            print(f"  Cargando página {pnum}: {page_url}")
            try:
                page.goto(page_url, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(2500)
                if not cookies_accepted:
                    try:
                        page.evaluate("document.querySelector('.fc-button.fc-data-preferences-accept-all').click()")
                        page.wait_for_timeout(1500)
                        cookies_accepted = True
                    except Exception:
                        pass
                html_n = page.content()
                found_n = scrape_profile_page(html_n)
                print(f"  Página {pnum}: {found_n} propiedades nuevas")
                if found_n == 0:
                    print(f"  ⚠ Página {pnum} sin propiedades nuevas, deteniendo paginación")
                    break
            except Exception as e:
                print(f"  ⚠ Error en página {pnum}: {e}")
                break

        selected = list(prop_urls_map.items())[:MAX_PROPS]
        print(f"\n  ✓ Total acumulado: {len(prop_urls_map)} propiedades")
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
                page.goto(prop_url, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(2000)
                try:
                    page.evaluate("document.querySelector('.fc-button.fc-data-preferences-accept-all').click()")
                    page.wait_for_timeout(1500)
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
