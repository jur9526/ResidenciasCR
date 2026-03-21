#!/usr/bin/env python3
"""
ResidenciasCostaRica — fetch_images.py
=======================================
Usa Playwright para renderizar cada propiedad de Encuentra24,
toma un screenshot, y usa Ollama moondream para verificar que
es una foto de casa. Guarda las imágenes en assets/ y actualiza
properties-data.js automáticamente.

Uso:
  python3 fetch_images.py
"""

import asyncio
import os
import re
import base64
import json
import requests
from pathlib import Path
from playwright.async_api import async_playwright

# ── Config ────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent
ASSETS_DIR  = PROJECT_DIR / "assets"
DATA_FILE   = PROJECT_DIR / "properties-data.js"
OLLAMA_URL  = "http://localhost:11434/api/generate"
VISION_MODEL = "moondream"   # cambiá a "llava" si lo tenés

ASSETS_DIR.mkdir(exist_ok=True)

# IDs de Encuentra24
PROPERTY_IDS = [
    "31892295", "31076847", "31254567", "29377845", "30422582",
    "30856282", "31939144", "31254818", "30728594", "30885230",
    "31254758", "30856191", "31881272", "31892169", "28313598",
    "30885142", "31354896", "31881424", "31881388", "30127424",
]

# Selectores CSS para la imagen principal (en orden de prioridad)
IMG_SELECTORS = [
    "img[class*='GalleryPhoto']",
    "img[class*='gallery']",
    "img[class*='carousel']",
    "img[class*='slider']",
    "img[class*='photo']",
    "img[class*='listing']",
    ".swiper-slide img",
    ".slick-slide img",
    "div[class*='Gallery'] img",
    "div[class*='Photo'] img",
    "div[class*='Image'] img",
    "picture img",
    "article img",
    "main img",
]

def ollama_is_available():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return VISION_MODEL in models or any(VISION_MODEL in m for m in models)
    except:
        return False

def ask_ollama_vision(image_path: Path) -> str:
    """Usa Ollama vision para verificar si la imagen es una propiedad."""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    payload = {
        "model": VISION_MODEL,
        "prompt": "Is this a photo of a house, apartment, land, or real estate property? Answer only: YES or NO.",
        "images": [img_b64],
        "stream": False,
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response = r.json().get("response", "").strip().upper()
        return "YES" in response
    except Exception as e:
        print(f"    Ollama error: {e}")
        return True  # si falla, asumimos que es válida

async def fetch_property_image(page, prop_id: str):
    output_path = ASSETS_DIR / f"e24-{prop_id}.jpg"

    if output_path.exists():
        print(f"  ✓ {prop_id} — ya descargado")
        return str(output_path.relative_to(PROJECT_DIR))

    url = f"https://www.encuentra24.com/costa-rica-es/bienes-raices/{prop_id}"
    print(f"  → {prop_id} — {url}")

    try:
        await page.goto(url, wait_until="networkidle", timeout=35000)
        await page.wait_for_timeout(4000)  # esperar JS y renders
        # Verificar que no estamos en la homepage
        current_url = page.url
        if "profile" in current_url or current_url.endswith("encuentra24.com/") or "search" in current_url:
            print(f"    Redirigido a: {current_url} — reintentando...")
            await page.wait_for_timeout(2000)
            await page.goto(url, wait_until="networkidle", timeout=35000)
            await page.wait_for_timeout(4000)
    except Exception as e:
        print(f"    Error cargando página: {e}")
        return None

    # Intentar extraer URL de imagen del DOM renderizado
    img_src = None
    for selector in IMG_SELECTORS:
        try:
            el = await page.query_selector(selector)
            if el:
                src = await el.get_attribute("src") or await el.get_attribute("data-src")
                if src and len(src) > 10 and not src.endswith(".svg"):
                    img_src = src
                    print(f"    Imagen encontrada: {selector}")
                    break
        except:
            continue

    if img_src:
        # Descargar la imagen directamente
        try:
            if img_src.startswith("//"):
                img_src = "https:" + img_src
            elif img_src.startswith("/"):
                img_src = "https://www.encuentra24.com" + img_src

            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            r = requests.get(img_src, headers=headers, timeout=15)
            if r.status_code == 200:
                output_path.write_bytes(r.content)
                print(f"    Imagen descargada: {img_src[:60]}...")
                return str(output_path.relative_to(PROJECT_DIR))
        except Exception as e:
            print(f"    Error descargando imagen: {e}")

    # Fallback: screenshot de la zona de la imagen
    print(f"    Usando screenshot como fallback...")
    try:
        # Intentar screenshot del primer elemento grande de imagen
        for selector in IMG_SELECTORS:
            try:
                el = await page.query_selector(selector)
                if el:
                    box = await el.bounding_box()
                    if box and box["width"] > 200 and box["height"] > 150:
                        await el.screenshot(path=str(output_path))
                        print(f"    Screenshot de elemento: {selector}")
                        return str(output_path.relative_to(PROJECT_DIR))
            except:
                continue

        # Screenshot del viewport superior (donde suele estar la galería)
        await page.screenshot(
            path=str(output_path),
            clip={"x": 0, "y": 60, "width": 900, "height": 500}
        )
        print(f"    Screenshot de página completa (recortado)")
        return str(output_path.relative_to(PROJECT_DIR))

    except Exception as e:
        print(f"    Error en screenshot: {e}")
        return None

def update_properties_data(image_map: dict):
    """Actualiza el campo 'image' en properties-data.js."""
    if not DATA_FILE.exists():
        print("  ✗ No se encontró properties-data.js")
        return

    content = DATA_FILE.read_text(encoding="utf-8")

    updated = 0
    for prop_id, img_path in image_map.items():
        # Buscar el bloque con este e24id y reemplazar su image
        pattern = rf'(e24id:\s*"{prop_id}"[^}}]*?image:\s*)"([^"]*)"'
        # Buscar primero la posición del e24id en el objeto
        e24_match = re.search(rf'e24id:\s*"{prop_id}"', content)
        if not e24_match:
            continue

        # Encontrar el inicio del objeto que contiene este e24id
        obj_start = content.rfind("{", 0, e24_match.start())
        obj_end   = content.find("}", e24_match.end()) + 1

        if obj_start < 0 or obj_end <= obj_start:
            continue

        obj_str     = content[obj_start:obj_end]
        new_obj_str = re.sub(r'(image:\s*)"([^"]*)"', f'\\1"{img_path}"', obj_str, count=1)

        if new_obj_str != obj_str:
            content = content[:obj_start] + new_obj_str + content[obj_end:]
            updated += 1

    DATA_FILE.write_text(content, encoding="utf-8")
    print(f"\n  ✓ properties-data.js actualizado ({updated} propiedades)")

async def main():
    use_ollama = ollama_is_available()
    if use_ollama:
        print(f"✓ Ollama disponible con {VISION_MODEL} — verificación de imágenes activada\n")
    else:
        print(f"⚠  Ollama/{VISION_MODEL} no disponible — solo descarga de imágenes\n")
        print("  Para activar verificación visual:")
        print(f"  ollama pull {VISION_MODEL}\n")

    image_map = {}
    rejected  = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,   # visible para evitar detección
            slow_mo=80,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--start-maximized",
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            java_script_enabled=True,
            locale="es-CR",
            timezone_id="America/Costa_Rica",
        )
        # Eliminar señales de automatización
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
        """)
        page = await context.new_page()

        print(f"Procesando {len(PROPERTY_IDS)} propiedades...\n")

        for prop_id in PROPERTY_IDS:
            rel_path = await fetch_property_image(page, prop_id)

            if rel_path:
                abs_path = PROJECT_DIR / rel_path
                if use_ollama and abs_path.exists():
                    is_valid = ask_ollama_vision(abs_path)
                    if is_valid:
                        print(f"    Ollama: ✓ imagen válida")
                        image_map[prop_id] = rel_path
                    else:
                        print(f"    Ollama: ✗ imagen rechazada (no parece propiedad)")
                        rejected.append(prop_id)
                        abs_path.unlink(missing_ok=True)
                else:
                    image_map[prop_id] = rel_path
            else:
                print(f"    Sin imagen para {prop_id}")

        await browser.close()

    print(f"\n{'='*50}")
    print(f"✓ Descargadas: {len(image_map)} imágenes")
    if rejected:
        print(f"✗ Rechazadas por Ollama: {len(rejected)} → {rejected}")

    if image_map:
        print("\nActualizando properties-data.js...")
        update_properties_data(image_map)

    print("\nListo. Las imágenes están en:")
    print(f"  {ASSETS_DIR}")
    print("\nAbrí el sitio para ver los cambios.")

if __name__ == "__main__":
    asyncio.run(main())
