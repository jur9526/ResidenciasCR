// ============================================================
//  ResidenciasCostaRica — main.js
// ============================================================

// ── Mobile nav ──────────────────────────────────────────────
const navToggle = document.getElementById('navToggle');
const navLinks  = document.getElementById('navLinks');
if (navToggle && navLinks) {
  navToggle.addEventListener('click', () => navLinks.classList.toggle('open'));
  navLinks.querySelectorAll('a').forEach(l => l.addEventListener('click', () => navLinks.classList.remove('open')));
}

// ── Scroll reveal ────────────────────────────────────────────
const revealObserver = new IntersectionObserver(entries => {
  entries.forEach((entry, i) => {
    if (entry.isIntersecting) {
      setTimeout(() => entry.target.classList.add('visible'), i * 80);
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.07 });
document.querySelectorAll('.reveal, .fade-in').forEach(el => revealObserver.observe(el));

// ── Smooth scroll ────────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', e => {
    const target = document.querySelector(anchor.getAttribute('href'));
    if (target) {
      e.preventDefault();
      window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - 80, behavior: 'smooth' });
    }
  });
});

// ── Properties ───────────────────────────────────────────────
const PROPS_PER_PAGE = 6;
const PROPS_PER_PROP_PAGE = 9;
let currentPage = 0;
let propCurrentPage = 1;
let properties  = [];

// Estado de filtros
let activeFilters = { tipo: 'todos', beds: 'todos', zona: '', provincia: 'todas', operacion: 'todas' };
let showAll = false;

const PROVINCE_CANTONS = {
  'San José':    ['San José','Escazú','Desamparados','Puriscal','Aserrí','Mora','Goicoechea','Santa Ana','Alajuelita','Coronado','Tibás','Moravia','Montes de Oca','Curridabat','Pérez Zeledón','Hatillo','Zapote','San Pedro','La Uruca','Sabanilla','Guadalupe','Tres Ríos','San Sebastián','San Francisco','Ciudad Colón','Paso Ancho'],
  'Alajuela':   ['Alajuela','San Ramón','Grecia','Atenas','Naranjo','Palmares','Poás','Orotina','San Carlos','Ciudad Quesada','Zarcero','Upala','Los Chiles','La Guácima','Guácima','El Coyol','Coyol','San Rafael de Alajuela'],
  'Cartago':    ['Cartago','La Unión','Tres Ríos','Paraíso','Turrialba','El Guarco','Oreamuno','Cot','Tobosi','Dulce Nombre','El Tejar','Quebradilla','Tejar','San Diego'],
  'Heredia':    ['Heredia','Barva','Santo Domingo','Santa Bárbara','San Rafael','Belén','Flores','San Pablo','Ulloa','Sarapiquí','San Joaquín','San Isidro','Lagunilla','Bambú','Calles Blanco','San Antonio'],
  'Guanacaste': ['Liberia','Nicoya','Santa Cruz','Tamarindo','Flamingo','Bagaces','Carrillo','Cañas','Nosara','Sámara','Tilarán','La Cruz','Tenorio','Guanacaste'],
  'Puntarenas': ['Puntarenas','Esparza','Quepos','Manuel Antonio','Golfito','Jacó','Parrita','Dominical','Uvita','Coto Brus','Garabito','Osa'],
  'Limón':      ['Limón','Pococí','Siquirres','Talamanca','Matina','Guácimo','Cahuita','Puerto Viejo','Guápiles','Batán'],
};

function loadProperties() {
  try {
    // Siempre usar datos frescos del archivo data
    properties = window.DEFAULT_PROPERTIES || [];
    // Actualizar localStorage con la versión actual
    localStorage.setItem('rcr_properties', JSON.stringify(properties));
  } catch {
    properties = window.DEFAULT_PROPERTIES || [];
  }
}

// ── Filtrado ─────────────────────────────────────────────────
function filtersActive() {
  return activeFilters.tipo !== 'todos' || activeFilters.beds !== 'todos' ||
         activeFilters.zona !== '' || activeFilters.provincia !== 'todas' ||
         activeFilters.operacion !== 'todas';
}

function getFiltered() {
  return properties.filter(p => {
    const tipoOk = activeFilters.tipo === 'todos' ||
      (p.type || '').toLowerCase() === activeFilters.tipo.toLowerCase();
    const bedsOk = activeFilters.beds === 'todos' ||
      p.beds >= parseInt(activeFilters.beds);
    const zonaOk = !activeFilters.zona ||
      (p.location || '').toLowerCase().includes(activeFilters.zona.toLowerCase()) ||
      (p.title    || '').toLowerCase().includes(activeFilters.zona.toLowerCase());
    const provOk = activeFilters.provincia === 'todas' ||
      (PROVINCE_CANTONS[activeFilters.provincia] || []).some(c => {
        const re = new RegExp('\\b' + c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i');
        return re.test(p.location || '') || re.test(p.title || '');
      });
    const isAlquiler = (p.badge   || '').toLowerCase().includes('alquiler') ||
                       (p.title   || '').toLowerCase().includes('alquiler') ||
                       (p.location|| '').toLowerCase().includes('alquiler') ||
                       (p.e24url  || '').includes('alquiler');
    const opOk = activeFilters.operacion === 'todas' ||
      (activeFilters.operacion === 'alquiler' && isAlquiler) ||
      (activeFilters.operacion === 'compra'   && !isAlquiler);
    return tipoOk && bedsOk && zonaOk && provOk && opOk;
  });
}

// ── Imagen con skeleton ───────────────────────────────────────
function getPropertyImage(prop) {
  if (prop.image && prop.image.trim()) return prop.image;
  if (prop.e24id) return `assets/e24-${prop.e24id}.webp`;
  return 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=800&q=80';
}

// ── Card HTML ─────────────────────────────────────────────────
function buildPropertyCard(prop) {
  const beds  = prop.beds  > 0 ? `<span><i class="fa-solid fa-bed"></i> ${prop.beds} hab.</span>` : '';
  const baths = prop.baths > 0 ? `<span><i class="fa-solid fa-bath"></i> ${prop.baths} baños</span>` : '';
  const area  = prop.area  ? `<span><i class="fa-solid fa-ruler-combined"></i> ${prop.area}</span>` : '';
  const imgSrc = getPropertyImage(prop);

  const eid = prop.e24id || '';
  return `
    <div class="property-card reveal prop-card-clickable"
         onclick="openPropModal(window.DEFAULT_PROPERTIES.find(p=>p.e24id==='${eid}'))">
      <div class="property-img">
        <div class="prop-skeleton"></div>
        <img src="${imgSrc}" alt="${prop.title}" loading="lazy" decoding="async"
             width="800" height="500" class="prop-img-lazy"
             onerror="this.src='https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=800&q=80'" />
        <span class="property-badge ${prop.badgeClass || ''}">${prop.badge || 'En Venta'}</span>
      </div>
      <div class="property-body">
        <div class="property-price">${prop.price}</div>
        <div class="property-title">${prop.title}</div>
        <div class="property-location"><i class="fa-solid fa-location-dot"></i> ${prop.location}</div>
        <div class="property-features">${beds}${baths}${area}</div>
      </div>
    </div>`;
}

// ── Pagination ────────────────────────────────────────────────
function getPaginationEl() {
  return document.getElementById('propPagination') || document.getElementById('indexPagination');
}

function renderPagination(totalPages, current) {
  const el = getPaginationEl();
  if (!el) return;
  if (totalPages <= 1) { el.innerHTML = ''; return; }
  let html = `<span class="prop-page-label">Página</span>`;
  if (current > 1)
    html += `<button class="prop-page-btn prop-page-prev" data-page="${current - 1}" title="Anterior"><i class="fa-solid fa-chevron-left"></i></button>`;
  for (let i = 1; i <= totalPages; i++)
    html += `<button class="prop-page-btn${i === current ? ' active' : ''}" data-page="${i}">${i}</button>`;
  if (current < totalPages)
    html += `<button class="prop-page-btn prop-page-next" data-page="${current + 1}" title="Siguiente"><i class="fa-solid fa-chevron-right"></i></button>`;
  el.innerHTML = html;
  el.querySelectorAll('[data-page]').forEach(btn => {
    btn.addEventListener('click', () => {
      propCurrentPage = parseInt(btn.dataset.page);
      renderProperties();
      const grid = document.getElementById('propertiesGrid');
      if (grid) window.scrollTo({ top: grid.getBoundingClientRect().top + window.scrollY - 100, behavior: 'smooth' });
    });
  });
}

// ── Render ────────────────────────────────────────────────────
function renderProperties() {
  const grid         = document.getElementById('propertiesGrid');
  const loadMoreBtn  = document.getElementById('loadMoreBtn');
  const noResults    = document.getElementById('propNoResults');
  const paginationEl = getPaginationEl();
  if (!grid) return;

  const filtered      = getFiltered();
  const usePagination = !!paginationEl;
  const perPage       = document.getElementById('indexPagination') ? PROPS_PER_PAGE : PROPS_PER_PROP_PAGE;
  const totalPages    = usePagination ? Math.ceil(filtered.length / perPage) : 0;
  if (usePagination && totalPages > 0 && propCurrentPage > totalPages) propCurrentPage = 1;

  let slice;
  if (usePagination) {
    const start = (propCurrentPage - 1) * perPage;
    slice = filtered.slice(start, start + perPage);
  } else {
    // Mostrar todo si: filtros activos O usuario pidió ver todo
    const displayAll = showAll || filtersActive();
    slice = displayAll ? filtered : filtered.slice(0, PROPS_PER_PAGE);
  }

  if (filtered.length === 0) {
    grid.innerHTML = '';
    if (noResults) noResults.style.display = 'flex';
    if (paginationEl) paginationEl.innerHTML = '';
  } else {
    if (noResults) noResults.style.display = 'none';
    grid.innerHTML = slice.map(buildPropertyCard).join('');
    grid.querySelectorAll('.prop-img-lazy').forEach(img => {
      const skeleton = img.closest('.property-img')?.querySelector('.prop-skeleton');
      img.addEventListener('load', () => { if (skeleton) skeleton.style.display = 'none'; img.classList.add('loaded'); });
      img.addEventListener('error', () => {
        if (skeleton) skeleton.style.display = 'none';
        img.src = 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=800&q=80';
        img.classList.add('loaded');
      });
    });
    grid.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));
    if (usePagination) renderPagination(totalPages, propCurrentPage);
  }

  // Botón loadMore (fallback)
  if (loadMoreBtn) loadMoreBtn.style.display = 'none';

  // Botón "Ver más propiedades" → /propiedades (solo index)
  if (!usePagination) {
    const verMasWrapper = document.getElementById('verMasWrapper');
    const verMasCount   = document.getElementById('verMasCount');
    if (verMasWrapper) {
      const remaining = filtered.length - slice.length;
      verMasWrapper.style.display = remaining > 0 ? 'flex' : 'none';
      if (verMasCount && remaining > 0) {
        verMasCount.textContent = `${remaining} propiedades más te están esperando`;
      }
    }
  }
}

// ── Load more — muestra TODAS ─────────────────────────────────
const loadMoreBtn = document.getElementById('loadMoreBtn');
if (loadMoreBtn) {
  loadMoreBtn.addEventListener('click', () => {
    showAll = true;
    renderProperties();
  });
}

// ── Filtros ───────────────────────────────────────────────────
function resetPage() { currentPage = 0; showAll = false; propCurrentPage = 1; }

function makeChip(selector, key, dataKey) {
  document.querySelectorAll(selector).forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll(selector).forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilters[key] = btn.dataset[dataKey];
      resetPage();
      renderProperties();
    });
  });
}

makeChip('[data-filter-tipo]',  'tipo',      'filterTipo');
makeChip('[data-filter-beds]',  'beds',      'filterBeds');
makeChip('[data-filter-op]',    'operacion', 'filterOp');
makeChip('[data-filter-prov]',  'provincia', 'filterProv');

// Búsqueda por zona
const zonaInput = document.getElementById('filterZona');
if (zonaInput) {
  let debounce;
  zonaInput.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      activeFilters.zona = zonaInput.value.trim();
      resetPage();
      renderProperties();
    }, 300);
  });
}

// ── Init ──────────────────────────────────────────────────────
loadProperties();
renderProperties();

// ── Form handler ─────────────────────────────────────────────
function handleForm(formId, successId) {
  const form    = document.getElementById(formId);
  const success = document.getElementById(successId);
  if (!form) return;
  const btn = form.querySelector('.btn-submit');

  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (btn) { btn.disabled = true; btn.textContent = 'Enviando...'; }

    try {
      const res = await fetch('https://api.web3forms.com/submit', {
        method: 'POST', body: new FormData(form)
      });
      if (res.ok) {
        const emailVal = form.querySelector('[name="email"]')?.value || '';
        const phoneVal = form.querySelector('[name="telefono"]')?.value || '';
        form.reset();
        if (typeof gtag === 'function') {
          gtag('set', 'user_data', { email: emailVal, phone_number: phoneVal });
          gtag('event', 'conversion', {
            'send_to': 'AW-18034283160/H3bDCNae-9EcEJiltZdD',
            'value': 15000,
            'currency': 'CRC'
          });
        }
        if (success) {
          success.style.display = 'flex';
          setTimeout(() => { success.style.display = 'none'; }, 5000);
        }
      } else {
        alert('Hubo un error. Por favor escribinos directamente por WhatsApp.');
      }
    } catch {
      alert('Error de conexión. Escribinos por WhatsApp.');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Enviar';
      }
    }
  });
}

// Forms con fotos son manejados en el inline script de index.html

// ── Toggle "sin costo" en buyer form ─────────────────────────
const freeNote = document.getElementById('buyer-free-note');
document.querySelectorAll('#buyerForm input[name="intencion"]').forEach(radio => {
  radio.addEventListener('change', () => {
    if (freeNote) freeNote.style.display = radio.value === 'Comprar' ? '' : 'none';
  });
});
