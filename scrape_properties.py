import re
import json

# Read the HTML files
with open('profile.html', 'r', encoding='utf-8') as f:
    html1 = f.read()

with open('profile2.html', 'r', encoding='utf-8') as f:
    html2 = f.read()

html = html1 + html2

# Extract property blocks
# Find all data-adid and corresponding data-price, href, etc.

adid_pattern = re.compile(r'data-adid="(\d+)"')
price_pattern = re.compile(r'data-price="([^"]*)"')
href_pattern = re.compile(r'href="/costa-rica-es/bienes-raices[^"]*"')

# Find all matches
adids = adid_pattern.findall(html)
prices = price_pattern.findall(html)
hrefs = href_pattern.findall(html)

# Since they are in order, assume they match
properties = []

for i, adid in enumerate(adids):
    if i >= len(prices) or i >= len(hrefs):
        continue
    price = prices[i]
    href = hrefs[i]
    
    # Extract title from href
    slug = href.split('/')[-2]  # the slug before id
    title = slug.replace('-', ' ').title()
    
    # Price format
    if '.' in price:
        price = f"${price}"
    else:
        price = f"₡{price}"
    
    # Location from ga4addata if available
    loc_match = re.search(rf'ga4addata\[{adid}\].*?"location":"([^"]*)"', html)
    location = loc_match.group(1).replace('costa-rica-es-', '').replace('-provincia', '').replace('-', ' ').title() if loc_match else ""
    
    # Type from subcategory
    type_match = re.search(rf'ga4addata\[{adid}\].*?"subcategory":"([^"]*)"', html)
    subcategory = type_match.group(1) if type_match else ""
    if 'apartamentos' in subcategory:
        prop_type = 'Apartamento'
    elif 'lotes-y-terrenos' in subcategory:
        prop_type = 'Terreno'
    elif 'finca' in title.lower():
        prop_type = 'Finca'
    elif 'penthouse' in title.lower():
        prop_type = 'Penthouse'
    else:
        prop_type = 'Casa'
    
    # Badge
    badge = 'En Venta'
    if 'oportunidad' in title.lower() or 'remate' in title.lower():
        badge = 'Oportunidad'
    elif 'inversión' in title.lower():
        badge = 'Inversión'
    
    prop = {
        'id': f'E24-{adid}',
        'title': title,
        'price': price,
        'location': location,
        'beds': 0,  # Will set to 0, can be updated later
        'baths': 0,
        'area': '',
        'type': prop_type,
        'badge': badge,
        'badgeClass': '',
        'image': f'assets/e24-{adid}.jpg',
        'e24id': adid,
        'wa': f'Me%20interesa%20la%20propiedad%20{title.replace(" ", "%20")}'
    }
    properties.append(prop)

with open('properties-data-new.js', 'w', encoding='utf-8') as f:
    f.write('// Generated properties from Encuentra24 profile\nwindow.DEFAULT_PROPERTIES = ')
    json.dump(properties, f, indent=2, ensure_ascii=False)
    f.write(';')

print(f"Extracted {len(properties)} properties")