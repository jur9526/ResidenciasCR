#!/usr/bin/env python3
"""
ResidenciasCostaRica — sync_encuentra24.py
==========================================
Sincroniza las propiedades del perfil de encuentra24.com a
properties-data.js (incremental: solo descarga las nuevas y refresca
REFRESH_PER_RUN existentes por corrida).

Uso:
  SCRAPERAPI_KEY=... python3 sync_encuentra24.py   # en CI (Cloudflare bloquea GitHub)
  python3 sync_encuentra24.py                      # local, Playwright directo
  FULL_SCAN=1 ...                                  # recorrer todas las páginas del perfil
"""

import re
import json
import os
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
REFRESH_PER_RUN = int(os.environ.get("REFRESH_PER_RUN", "1"))  # existentes a re-descargar por corrida
FULL_SCAN    = os.environ.get("FULL_SCAN") == "1"

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
    path = ASSETS_DIR / f"e24-{prop_id}.webp"
    if path.exists():
        return f"assets/e24-{prop_id}.webp"
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


# ── Descarga de HTML ──────────────────────────────────────────
# Cloudflare bloquea las IPs de GitHub Actions, así que en CI las páginas se
# piden a ScraperAPI (render=true). Sin SCRAPERAPI_KEY se usa Playwright
# directo, que funciona desde una conexión residencial.
SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")
CF_TITLES = ("Cloudflare", "Un momento", "Just a moment")


def is_blocked(html: str) -> bool:
    m = re.search(r"<title>([^<]*)", html)
    return bool(m) and any(t in m.group(1) for t in CF_TITLES)


def fetch_via_scraperapi(url: str) -> str:
    last = ""
    for attempt in range(3):
        try:
            r = requests.get(
                "https://api.scraperapi.com/",
                params={"api_key": SCRAPERAPI_KEY, "url": url, "render": "true"},
                timeout=120,
            )
            if r.status_code == 200 and not is_blocked(r.text):
                return r.text
            last = f"HTTP {r.status_code}: {r.text[:100]}"
        except requests.RequestException as e:
            last = str(e)[:100]
    raise RuntimeError(f"ScraperAPI falló ({last}) en {url}")


def fetch_via_playwright(browser, url: str) -> str:
    # Contexto nuevo por navegación: Cloudflare bloquea (403) a partir de la
    # segunda página dentro de la misma sesión.
    ctx = browser.new_context(user_agent=HEADERS["User-Agent"], locale="es-CR")
    try:
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            pass
        html = page.content()
    finally:
        ctx.close()
    if is_blocked(html):
        raise RuntimeError(f"Bloqueado por Cloudflare en {url}")
    return html


# ── Datos existentes ──────────────────────────────────────────
def load_existing() -> list:
    try:
        text = DATA_FILE.read_text(encoding="utf-8")
        return json.loads(text[text.index("["):text.rindex("]") + 1])
    except (OSError, ValueError):
        return []


# ── Sync principal ────────────────────────────────────────────
def sync():
    print("=" * 55)
    print(f"Sincronización Encuentra24 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55 + "\n")

    existing = load_existing()
    existing_by_id = {p.get("e24id") or p["id"].removeprefix("E24-"): p for p in existing}
    # Escaneo completo (todas las páginas del perfil) los días 1 y 15 o si no
    # hay datos; el resto solo la página 1. Cada página cuesta ~15 créditos de
    # ScraperAPI y el plan gratis trae 1000/mes.
    full_scan = FULL_SCAN or datetime.now().day in (1, 15) or not existing
    print(f"Modo: {'completo' if full_scan else 'incremental'} · "
          f"{'ScraperAPI' if SCRAPERAPI_KEY else 'Playwright directo'} · "
          f"{len(existing)} propiedades existentes\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        def fetch(url: str) -> str:
            if SCRAPERAPI_KEY:
                return fetch_via_scraperapi(url)
            return fetch_via_playwright(browser, url)

        # Página sin red ni JS donde se carga el HTML para parsearlo
        parse_ctx = browser.new_context(java_script_enabled=False)
        parse_ctx.route("**/*", lambda route: route.abort())
        parse_page = parse_ctx.new_page()

        # ── Paso 1: Perfil ────────────────────────────────────
        seen = {}  # id -> url, en orden de aparición
        for pnum in range(1, MAX_PAGES + 1):
            page_url = PROFILE_URL if pnum == 1 else f"{PROFILE_URL}?page={pnum}"
            print(f"📋 Perfil página {pnum}")
            try:
                html = fetch(page_url)
            except Exception as e:
                if pnum == 1:
                    print(f"  ✗ {e}\n\n✗ No se pudo cargar el perfil. Abortando.")
                    browser.close()
                    return False
                print(f"  ⚠ {e}")
                full_scan = False  # escaneo incompleto: no borrar propiedades
                break
            hrefs = re.findall(r'href="(/costa-rica-es/bienes-raices[^"]+?/(\d{7,}))"', html)
            new_here = [(h, pid) for h, pid in hrefs if pid != "13021117" and pid not in seen]
            for href, pid in new_here:
                seen[pid] = "https://www.encuentra24.com" + href
            print(f"  {len(new_here)} propiedades")
            if not new_here:
                break
            # En modo incremental basta con seguir mientras aparezcan nuevas
            if not full_scan and all(pid in existing_by_id for _, pid in new_here):
                break

        if not seen:
            print("  ✗ No se encontraron propiedades. Abortando.")
            browser.close()
            return False

        # Orden final: lo visto en el perfil; en incremental, luego el resto
        order = list(seen)
        if full_scan:
            removed = [pid for pid in existing_by_id if pid not in seen]
            if len(removed) > len(existing_by_id) / 2:
                print(f"  ⚠ Desaparecerían {len(removed)} propiedades; se conservan por seguridad")
                order += removed
            elif removed:
                print(f"  − Ya no están en el perfil: {', '.join(removed)}")
        else:
            order += [pid for pid in existing_by_id if pid not in seen]
        order = order[:MAX_PROPS]

        # ── Paso 2: Qué descargar ─────────────────────────────
        new_ids = [pid for pid in order if pid not in existing_by_id]
        # Refrescar las existentes sincronizadas hace más tiempo
        stale = sorted((pid for pid in order if pid in existing_by_id),
                       key=lambda pid: existing_by_id[pid].get("synced", ""))
        to_fetch = new_ids + stale[:REFRESH_PER_RUN]
        print(f"\n🏠 {len(new_ids)} nuevas, {min(REFRESH_PER_RUN, len(stale))} a refrescar\n")

        fetched, failed = {}, []
        for pid in to_fetch:
            url = seen.get(pid) or existing_by_id[pid].get("e24url")
            try:
                parse_page.set_content(fetch(url), wait_until="domcontentloaded")
                data = parse_property_page(parse_page, pid)
                image_url = data.pop("image_url", "")
                data["image"] = download_image(image_url, pid) or FALLBACK_IMG
                data["e24url"] = url
                data["synced"] = datetime.now().strftime("%Y-%m-%d")
                fetched[pid] = data
                print(f"  ✓ {pid} — {data['title'][:55]}")
            except Exception as e:
                failed.append(pid)
                print(f"  ✗ {pid} — {e}")

        browser.close()

    # Nuevas que fallaron se reintentan en la próxima corrida;
    # existentes que fallaron conservan sus datos anteriores.
    properties = [fetched.get(pid) or existing_by_id[pid]
                  for pid in order if pid in fetched or pid in existing_by_id]

    if not properties:
        print("\n✗ No se obtuvieron propiedades.")
        return False

    update_data_file(properties)
    print(f"\n✅ Sync completado: {len(properties)} propiedades "
          f"({len(fetched)} descargadas, {len(failed)} fallidas)\n")
    return not failed


if __name__ == "__main__":
    sys.exit(0 if sync() else 1)
