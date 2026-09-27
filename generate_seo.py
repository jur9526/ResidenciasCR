#!/usr/bin/env python3
"""
ResidenciasCostaRica — generate_seo.py
======================================
Genera, a partir de properties-data.js, el contenido que Google y los
buscadores de IA pueden leer sin ejecutar JavaScript:

  inmueble/<slug>-<id>.html   una página estática por propiedad (con JSON-LD)
  inmueble/index.html         índice con todas las propiedades
  sitemap.xml                 páginas fijas + todas las propiedades
  llms.txt                    resumen del sitio para modelos de IA

La plantilla es propiedad.html (mismo head, navbar, footer y botones de
WhatsApp con gtagSendEvent). Se corre después de cada sync.

Uso:
  python3 generate_seo.py
"""

import html
import json
import re
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
DATA_FILE   = PROJECT_DIR / "properties-data.js"
TEMPLATE    = PROJECT_DIR / "propiedad.html"
OUT_DIR     = PROJECT_DIR / "inmueble"
SITE        = "https://residenciascostarica.com"
WA_NUMBER   = "50683725603"
MAX_GALLERY = 8

# Páginas fijas del sitemap: (ruta, changefreq, priority)
STATIC_PAGES = [
    ("/",                      "daily",   "1.0"),
    ("/propiedades",           "daily",   "0.9"),
    ("/propiedades-alquiler",  "daily",   "0.9"),
    ("/inmueble/",             "daily",   "0.8"),
    ("/escazu",                "weekly",  "0.8"),
    ("/santa-ana",             "weekly",  "0.8"),
    ("/heredia",               "weekly",  "0.8"),
    ("/alajuela",              "weekly",  "0.8"),
    ("/curridabat",            "weekly",  "0.8"),
    ("/moving-to-costa-rica",  "monthly", "0.7"),
]

ZONES = [
    ("Escazú", "/escazu"), ("Santa Ana", "/santa-ana"), ("Heredia", "/heredia"),
    ("Alajuela", "/alajuela"), ("Curridabat", "/curridabat"),
]

e = lambda s: html.escape(str(s or ""), quote=True)


# ── Datos ─────────────────────────────────────────────────────
def load_properties() -> list:
    text = DATA_FILE.read_text(encoding="utf-8")
    return json.loads(text[text.index("["):text.rindex("]") + 1])


def slugify(text: str) -> str:
    text = text.lower()
    for a, b in zip("áéíóúüñ", "aeiouun"):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:80].strip("-")


def prop_slug(p: dict) -> str:
    # El e24url ya trae un slug descriptivo: .../casa-en-venta-en-heredia/33013190
    m = re.search(r"/([^/]+)/\d{7,}$", p.get("e24url", ""))
    base = m.group(1) if m else slugify(p.get("title", "propiedad"))
    return f"{slugify(base)}-{p['e24id']}"


def prop_path(p: dict) -> str:
    return f"/inmueble/{prop_slug(p)}"


def clean_price(price: str) -> str:
    # El parser a veces deja "₡ 90,000,000\n\n-7%": nos quedamos con la primera línea
    return (price or "").strip().split("\n")[0].strip() or "Consultar"


def price_offer(price: str):
    """('CRC'|'USD', número) o None."""
    currency = "CRC" if "₡" in price else "USD" if "$" in price or "USD" in price else None
    digits = re.sub(r"[^\d]", "", price)
    return (currency, int(digits)) if currency and digits else None


def as_int(v) -> int:
    try:
        return int(str(v).strip())
    except ValueError:
        return 0


def gallery(p: dict) -> list:
    # all_images incluye fotos de anuncios relacionados: solo las de esta propiedad
    pid = str(p["e24id"])
    seen, out = set(), []
    for url in p.get("all_images") or []:
        if f"/{pid}_" in url and url not in seen:
            seen.add(url)
            out.append(url.replace("/t_or_fh_l/", "/t_or_fh_m/"))
    return out[:MAX_GALLERY]


def hero_image(p: dict) -> str:
    img = p.get("image") or ""
    if img.startswith("assets/"):
        return "/" + img
    return img or "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=1600&q=80"


def meta_description(p: dict) -> str:
    bits = [p.get("type") or "Propiedad", f"en {p['location']}" if p.get("location") else ""]
    feats = []
    if as_int(p.get("beds")):  feats.append(f"{as_int(p['beds'])} habitaciones")
    if as_int(p.get("baths")): feats.append(f"{as_int(p['baths'])} baños")
    if p.get("area"):          feats.append(p["area"])
    text = " ".join(b for b in bits if b)
    if feats:
        text += ": " + ", ".join(feats)
    text += f". {clean_price(p.get('price'))}. Asesoría gratis y trámite de bono de vivienda."
    return text[:300]


# ── JSON-LD ───────────────────────────────────────────────────
def json_ld(p: dict, url: str) -> str:
    offer = price_offer(clean_price(p.get("price")))
    kind = {"Casa": "SingleFamilyResidence", "Apartamento": "Apartment"}.get(p.get("type"), "Accommodation")
    residence = {"@type": kind, "name": p.get("title")}
    if as_int(p.get("beds")):
        residence["numberOfBedrooms"] = as_int(p["beds"])
    if as_int(p.get("baths")):
        residence["numberOfBathroomsTotal"] = as_int(p["baths"])
    m = re.search(r"([\d.,]+)\s*m", p.get("area") or "")
    if m:
        residence["floorSize"] = {"@type": "QuantitativeValue",
                                  "value": float(m.group(1).replace(",", "")), "unitCode": "MTK"}
    residence["address"] = {"@type": "PostalAddress", "addressLocality": p.get("location"),
                            "addressCountry": "CR"}
    data = {
        "@context": "https://schema.org",
        "@type": "RealEstateListing",
        "name": p.get("title"),
        "url": url,
        "description": meta_description(p),
        "image": [SITE + hero_image(p) if hero_image(p).startswith("/") else hero_image(p)] + gallery(p)[:4],
        "about": residence,
        "provider": {"@type": "RealEstateAgent", "name": "Residencias Costa Rica",
                     "url": SITE + "/", "telephone": "+506 8372-5603"},
    }
    if p.get("synced"):
        data["dateModified"] = p["synced"]
    if offer:
        data["offers"] = {"@type": "Offer", "price": offer[1], "priceCurrency": offer[0],
                          "availability": "https://schema.org/InStock",
                          "businessFunction": "http://purl.org/goodrelations/v1#LeaseOut"
                          if "alquiler" in (p.get("e24url") or "") else
                          "http://purl.org/goodrelations/v1#Sell"}
    breadcrumbs = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Propiedades", "item": SITE + "/inmueble/"},
            {"@type": "ListItem", "position": 3, "name": p.get("title"), "item": url},
        ],
    }
    dump = lambda d: json.dumps(d, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return (f'<script type="application/ld+json">\n{dump(data)}\n</script>\n'
            f'  <script type="application/ld+json">\n{dump(breadcrumbs)}\n</script>')


# ── Plantilla ─────────────────────────────────────────────────
def load_template() -> str:
    t = TEMPLATE.read_text(encoding="utf-8")
    # Rutas absolutas: las páginas viven en /inmueble/
    for attr in ("favicon.ico", "style.css", "flory.jpg"):
        t = t.replace(f'"{attr}"', f'"/{attr}"')
    # La CSP de la plantilla no permite estilos inline y bloquea su propio <style>
    assert "style-src 'self' " in t
    t = t.replace("style-src 'self' ", "style-src 'self' 'unsafe-inline' ", 1)
    # Sin render por JS: el contenido ya viene en el HTML
    t = t.replace('  <script src="properties-data.js"></script>\n', "")
    t = re.sub(r"\n    // ── Render de la propiedad ──.*?(\n  </script>)", r"\1", t, flags=re.S)
    return t


def fill_template(t: str, title: str, description: str, canonical: str,
                  image: str, extra_head: str, content: str) -> str:
    t = re.sub(r'<title id="pageTitle">.*?</title>', f"<title>{e(title)}</title>", t)
    t = re.sub(r'<meta name="description" id="pageDesc" content="[^"]*" />',
               f'<meta name="description" content="{e(description)}" />\n'
               f'  <link rel="canonical" href="{e(canonical)}" />\n'
               f'  <meta property="og:type" content="website" />\n'
               f'  <meta property="og:title" content="{e(title)}" />\n'
               f'  <meta property="og:description" content="{e(description)}" />\n'
               f'  <meta property="og:url" content="{e(canonical)}" />\n'
               f'  <meta property="og:image" content="{e(image)}" />\n'
               f'  <meta property="og:locale" content="es_CR" />\n'
               f'  {extra_head}', t)
    t = re.sub(r'<div id="propContent">.*?\n  </div>\n',
               f'<main id="propContent">\n{content}\n  </main>\n', t, count=1, flags=re.S)
    return t


def property_content(p: dict, url: str) -> str:
    price = clean_price(p.get("price"))
    wa_text = f"Hola, te escribo desde www.residenciascostarica.com. Me interesa la propiedad: {p['title']}. Link: {url}"
    wa_href = f"https://wa.me/{WA_NUMBER}?text=" + re.sub(
        r"[^A-Za-z0-9_.~-]", lambda m: "".join(f"%{b:02X}" for b in m.group().encode()), wa_text)

    feats = []
    if as_int(p.get("beds")):
        feats.append(f'<div class="prop-feat"><i class="fa-solid fa-bed"></i> {as_int(p["beds"])} habitaciones</div>')
    if as_int(p.get("baths")):
        feats.append(f'<div class="prop-feat"><i class="fa-solid fa-bath"></i> {as_int(p["baths"])} baños</div>')
    if p.get("area"):
        feats.append(f'<div class="prop-feat"><i class="fa-solid fa-ruler-combined"></i> {e(p["area"])}</div>')
    if as_int(p.get("parking")):
        feats.append(f'<div class="prop-feat"><i class="fa-solid fa-car"></i> {as_int(p["parking"])} parqueos</div>')
    feats_html = ""
    if feats:
        feats_html = (f'<div class="prop-features-bar">{"".join(feats)}'
                      f'<div class="prop-feat"><i class="fa-solid fa-location-dot"></i> {e(p.get("location"))}</div></div>')

    desc = (p.get("description") or "").strip()
    paras = [x.strip() for x in re.split(r"\n\s*\n", desc) if x.strip()] or [
        f"{p['title']}. Ubicada en {p.get('location')}."]
    desc_html = "\n".join(f'<p class="prop-description">{e(x).replace(chr(10), "<br>")}</p>' for x in paras)

    photos = gallery(p)
    gallery_html = ""
    if photos:
        imgs = "".join(
            f'<img src="{e(u)}" alt="{e(p["title"])} — foto {i + 1}" loading="lazy" '
            f'style="width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:10px;" />'
            for i, u in enumerate(photos))
        gallery_html = (f'<div class="prop-section-title">Fotos</div>'
                        f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:.6rem;margin-bottom:1.5rem;">{imgs}</div>')

    return f'''    <!-- Generado por generate_seo.py — no editar a mano -->
    <div class="prop-hero">
      <img src="{e(hero_image(p))}" alt="{e(p['title'])}" class="prop-hero-img" fetchpriority="high" />
      <div class="prop-hero-overlay">
        <div class="prop-hero-content">
          <a href="/inmueble/" class="prop-back"><i class="fa-solid fa-arrow-left"></i> Todas las propiedades</a>
          <div class="prop-hero-badge {e(p.get('badgeClass'))}">{e(p.get('badge') or 'En Venta')}</div>
          <div class="prop-hero-price">{e(price)}</div>
          <h1 class="prop-hero-title">{e(p['title'])}</h1>
          <div class="prop-hero-location"><i class="fa-solid fa-location-dot"></i> {e(p.get('location'))}</div>
        </div>
      </div>
    </div>

    <div class="prop-detail-wrap">
      <div class="prop-detail-left">
        {feats_html}
        <h2 class="prop-section-title">Sobre esta propiedad</h2>
        {desc_html}
        {gallery_html}
        <h2 class="prop-section-title">¿Por qué elegir Residencias Costa Rica?</h2>
        <div class="prop-features-bar" style="flex-direction:column;gap:.9rem;">
          <div class="prop-feat"><i class="fa-solid fa-circle-check"></i> Servicio 100% gratis para el comprador</div>
          <div class="prop-feat"><i class="fa-solid fa-circle-check"></i> Tramitología con más de 10 bancos nacionales</div>
          <div class="prop-feat"><i class="fa-solid fa-circle-check"></i> Asesoría en Bono de Vivienda</div>
          <div class="prop-feat"><i class="fa-solid fa-circle-check"></i> Más de 10 años de experiencia · 200+ cierres</div>
          <div class="prop-feat"><i class="fa-solid fa-circle-check"></i> Afiliados a la Cámara de Comercio de Costa Rica</div>
        </div>
      </div>

      <div class="prop-cta-card">
        <div class="prop-cta-header">
          <div class="prop-cta-price">{e(price)}</div>
          <p>Consultá sin compromiso</p>
        </div>
        <div class="prop-cta-body">
          <a onclick="return gtagSendEvent(this.href)" href="{e(wa_href)}" target="_blank" rel="noopener" class="prop-cta-wa">
            <i class="fa-brands fa-whatsapp"></i> Escribir por WhatsApp
          </a>
          <a href="tel:+50683725603" class="prop-cta-call"><i class="fa-solid fa-phone"></i> +506 8372-5603</a>
          <p class="prop-cta-note"><i class="fa-solid fa-bolt"></i> Respuesta en menos de 24 horas</p>
        </div>
        <div class="prop-cta-agent">
          <img src="/flory.jpg" alt="Floribeth Elizondo" />
          <div>
            <div class="prop-cta-agent-name">Floribeth Elizondo</div>
            <div class="prop-cta-agent-role">Asesora inmobiliaria</div>
          </div>
        </div>
      </div>
    </div>'''


def index_content(props: list) -> str:
    cards = []
    for p in props:
        feats = " · ".join(x for x in [
            f"{as_int(p.get('beds'))} hab" if as_int(p.get("beds")) else "",
            f"{as_int(p.get('baths'))} baños" if as_int(p.get("baths")) else "",
            p.get("area") or ""] if x)
        cards.append(f'''      <li style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
        <a href="{prop_path(p)}" style="display:block;color:inherit;text-decoration:none;">
          <img src="{e(hero_image(p))}" alt="{e(p['title'])}" loading="lazy" style="width:100%;aspect-ratio:4/3;object-fit:cover;display:block;" />
          <div style="padding:.9rem 1rem;">
            <div style="font-weight:700;">{e(clean_price(p.get('price')))}</div>
            <h2 style="font-size:1rem;margin:.25rem 0;">{e(p['title'])}</h2>
            <div style="font-size:.85rem;opacity:.75;">{e(p.get('location'))}{' · ' + e(feats) if feats else ''}</div>
          </div>
        </a>
      </li>''')
    zones = " · ".join(f'<a href="{href}">{name}</a>' for name, href in ZONES)
    return f'''    <!-- Generado por generate_seo.py — no editar a mano -->
    <div class="container" style="padding:7rem 1rem 3rem;max-width:1200px;margin:0 auto;">
      <h1 style="margin-bottom:.5rem;">Casas, apartamentos y lotes en venta y alquiler en Costa Rica</h1>
      <p style="margin-bottom:.5rem;">{len(props)} propiedades disponibles con asesoría gratuita para el comprador y trámite de bono de vivienda. Actualizado el {date.today().strftime("%d/%m/%Y")}.</p>
      <p style="margin-bottom:1.5rem;">Por zona: {zones} · <a href="/propiedades">Buscar con filtros</a></p>
      <ul style="list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1rem;">
{chr(10).join(cards)}
      </ul>
    </div>'''


# ── Sitemap y llms.txt ────────────────────────────────────────
def sitemap(props: list) -> str:
    today = date.today().isoformat()
    urls = [f"  <url>\n    <loc>{SITE}{path}</loc>\n    <lastmod>{today if freq == 'daily' else ''}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>"
            for path, freq, prio in STATIC_PAGES]
    urls = [u.replace("    <lastmod></lastmod>\n", "") for u in urls]
    for p in props:
        urls.append(f"  <url>\n    <loc>{SITE}{prop_path(p)}</loc>\n"
                    f"    <lastmod>{p.get('synced') or today}</lastmod>\n"
                    f"    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls) + "\n</urlset>\n")


def llms_txt(props: list) -> str:
    lines = [
        "# Residencias Costa Rica",
        "",
        "> Agencia inmobiliaria en Costa Rica dirigida por Floribeth Elizondo. Venta y alquiler de casas,",
        "> apartamentos y lotes en el Gran Área Metropolitana. Asesoría gratuita para el comprador,",
        "> tramitología con más de 10 bancos y trámite de bono de vivienda.",
        "",
        "Contacto: WhatsApp +506 8372-5603 · flory@residenciascostarica.com",
        "",
        "## Páginas principales",
        "",
        f"- [Todas las propiedades]({SITE}/inmueble/): listado completo con precio y zona",
        f"- [Buscar con filtros]({SITE}/propiedades)",
        f"- [Propiedades en alquiler]({SITE}/propiedades-alquiler)",
        f"- [Moving to Costa Rica]({SITE}/moving-to-costa-rica): guía en inglés para extranjeros",
        "",
        "## Zonas",
        "",
    ]
    lines += [f"- [{name}]({SITE}{href})" for name, href in ZONES]
    lines += ["", f"## Propiedades disponibles ({len(props)})", ""]
    for p in props:
        extra = ", ".join(x for x in [
            f"{as_int(p.get('beds'))} hab" if as_int(p.get("beds")) else "",
            p.get("area") or ""] if x)
        lines.append(f"- [{p['title']}]({SITE}{prop_path(p)}): {clean_price(p.get('price'))}, "
                     f"{p.get('location')}{', ' + extra if extra else ''}")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────
def main():
    props = [p for p in load_properties() if p.get("e24id")]
    template = load_template()
    OUT_DIR.mkdir(exist_ok=True)

    written = set()
    for p in props:
        url = SITE + prop_path(p)
        title = f"{p['title']} — {clean_price(p.get('price'))} | Residencias Costa Rica"
        img = hero_image(p)
        page = fill_template(template, title, meta_description(p), url,
                             SITE + img if img.startswith("/") else img,
                             json_ld(p, url), property_content(p, url))
        name = prop_slug(p) + ".html"
        (OUT_DIR / name).write_text(page, encoding="utf-8")
        written.add(name)

    index = fill_template(
        template, "Propiedades en venta y alquiler en Costa Rica | Residencias Costa Rica",
        f"{len(props)} casas, apartamentos y lotes en venta y alquiler en Costa Rica. "
        "Asesoría gratis para el comprador y trámite de bono de vivienda.",
        SITE + "/inmueble/", SITE + "/logo-social.svg", "", index_content(props))
    (OUT_DIR / "index.html").write_text(index, encoding="utf-8")
    written.add("index.html")

    # Propiedades que ya no están: se borran sus páginas
    removed = [f for f in OUT_DIR.glob("*.html") if f.name not in written]
    for f in removed:
        f.unlink()

    (PROJECT_DIR / "sitemap.xml").write_text(sitemap(props), encoding="utf-8")
    (PROJECT_DIR / "llms.txt").write_text(llms_txt(props), encoding="utf-8")
    print(f"✓ SEO: {len(props)} páginas en /inmueble/, {len(removed)} eliminadas, "
          f"sitemap con {len(STATIC_PAGES) + len(props)} URLs, llms.txt")


if __name__ == "__main__":
    main()
