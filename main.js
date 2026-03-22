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
let currentPage = 0;
let properties  = [];

// Estado de filtros
let activeFilters = { tipo: 'todos', beds: 'todos', zona: '' };
let showAll = false; // true cuando el usuario pide ver todo

function loadProperties() {
  try {
    const stored = localStorage.getItem('rcr_properties');
    properties = stored ? JSON.parse(stored) : (window.DEFAULT_PROPERTIES || []);
  } catch {
    properties = window.DEFAULT_PROPERTIES || [];
  }
}

// ── Filtrado ─────────────────────────────────────────────────
function filtersActive() {
  return activeFilters.tipo !== 'todos' || activeFilters.beds !== 'todos' || activeFilters.zona !== '';
}

function getFiltered() {
  return properties.filter(p => {
    const tipoOk = activeFilters.tipo === 'todos' ||
      (p.type || '').toLowerCase() === activeFilters.tipo.toLowerCase();

    const bedsOk = activeFilters.beds === 'todos' ||
      p.beds >= parseInt(activeFilters.beds);

    const zonaOk = !activeFilters.zona ||
      (p.location || '').toLowerCase().includes(activeFilters.zona.toLowerCase()) ||
      (p.title   || '').toLowerCase().includes(activeFilters.zona.toLowerCase());

    return tipoOk && bedsOk && zonaOk;
  });
}

// ── Imagen con skeleton ───────────────────────────────────────
function getPropertyImage(prop) {
  if (prop.image && prop.image.trim()) return prop.image;
  if (prop.e24id) return `assets/e24-${prop.e24id}.jpg`;
  return 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=800&q=80';
}

// ── Card HTML ─────────────────────────────────────────────────
function buildPropertyCard(prop) {
  const beds  = prop.beds  > 0 ? `<span><i class="fa-solid fa-bed"></i> ${prop.beds} hab.</span>` : '';
  const baths = prop.baths > 0 ? `<span><i class="fa-solid fa-bath"></i> ${prop.baths} baños</span>` : '';
  const area  = prop.area  ? `<span><i class="fa-solid fa-ruler-combined"></i> ${prop.area}</span>` : '';
  const e24Link = prop.e24id
    ? `<a href="${prop.e24url || 'https://www.encuentra24.com/costa-rica-es/bienes-raices/' + prop.e24id}"
          target="_blank" rel="noopener" class="prop-e24-link">
         <i class="fa-solid fa-external-link-alt"></i> Ver en Encuentra24
       </a>`
    : '';
  const imgSrc = getPropertyImage(prop);

  return `
    <div class="property-card reveal">
      <div class="property-img">
        <div class="prop-skeleton"></div>
        <img src="${imgSrc}" alt="${prop.title}" loading="lazy" class="prop-img-lazy" />
        <span class="property-badge ${prop.badgeClass || ''}">${prop.badge || 'En Venta'}</span>
        <div class="property-img-overlay">
          <a href="https://wa.me/50683725603?text=${prop.wa || 'Me%20interesa%20una%20propiedad'}"
             target="_blank" rel="noopener" class="prop-wa-btn">
            <i class="fa-brands fa-whatsapp"></i> Consultar
          </a>
        </div>
      </div>
      <div class="property-body">
        <div class="property-price">${prop.price}</div>
        <div class="property-title">${prop.title}</div>
        <div class="property-location"><i class="fa-solid fa-location-dot"></i> ${prop.location}</div>
        <div class="property-features">${beds}${baths}${area}</div>
        ${e24Link}
      </div>
    </div>`;
}

// ── Render ────────────────────────────────────────────────────
function renderProperties() {
  const grid        = document.getElementById('propertiesGrid');
  const loadMoreBtn = document.getElementById('loadMoreBtn');
  const noResults   = document.getElementById('propNoResults');
  if (!grid) return;

  const filtered = getFiltered();

  // Mostrar todo si: filtros activos O usuario pidió ver todo
  const displayAll = showAll || filtersActive();
  const slice = displayAll ? filtered : filtered.slice(0, PROPS_PER_PAGE);

  if (filtered.length === 0) {
    grid.innerHTML = '';
    if (noResults) noResults.style.display = 'flex';
  } else {
    if (noResults) noResults.style.display = 'none';
    grid.innerHTML = slice.map(buildPropertyCard).join('');
    grid.querySelectorAll('.prop-img-lazy').forEach(img => {
      const skeleton = img.previousElementSibling;
      img.addEventListener('load', () => { if (skeleton) skeleton.style.display = 'none'; img.classList.add('loaded'); });
      img.addEventListener('error', () => {
        if (skeleton) skeleton.style.display = 'none';
        img.src = 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=800&q=80';
        img.classList.add('loaded');
      });
    });
    grid.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));
  }

  // Botón visible solo cuando hay más que mostrar y sin filtros activos y no showAll
  if (loadMoreBtn) {
    loadMoreBtn.style.display = (!displayAll && filtered.length > PROPS_PER_PAGE) ? 'inline-flex' : 'none';
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
function resetPage() { currentPage = 0; showAll = false; }

// Chips de tipo
document.querySelectorAll('[data-filter-tipo]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('[data-filter-tipo]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilters.tipo = btn.dataset.filterTipo;
    resetPage();
    renderProperties();
  });
});

// Chips de habitaciones
document.querySelectorAll('[data-filter-beds]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('[data-filter-beds]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilters.beds = btn.dataset.filterBeds;
    resetPage();
    renderProperties();
  });
});

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
        form.reset();
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

handleForm('buyerForm', 'buyerSuccess');
handleForm('sellForm',  'formSuccess');

// ── Toggle "sin costo" en buyer form ─────────────────────────
const freeNote = document.getElementById('buyer-free-note');
document.querySelectorAll('#buyerForm input[name="intencion"]').forEach(radio => {
  radio.addEventListener('change', () => {
    if (freeNote) freeNote.style.display = radio.value === 'Comprar' ? '' : 'none';
  });
});

// ── Modal Bono Vivienda ──────────────────────────────────────
const bonoModal   = document.getElementById('bonoModal');
const bonoCard    = document.getElementById('bonoCard');
const bonoClose   = document.getElementById('bonoModalClose');
const bonoCta     = document.getElementById('bonoModalCta');
if (bonoCard && bonoModal) {
  bonoCard.addEventListener('click', () => { bonoModal.style.display = 'flex'; });
  bonoModal.addEventListener('click', e => { if (e.target === bonoModal) bonoModal.style.display = 'none'; });
  if (bonoClose) bonoClose.addEventListener('click', () => { bonoModal.style.display = 'none'; });
  if (bonoCta)   bonoCta.addEventListener('click',   () => { bonoModal.style.display = 'none'; });
}

// ── Cámara de Comercio tooltip ───────────────────────────────
const camaraTip = document.getElementById('camara-tooltip');
if (camaraTip) {
  document.querySelectorAll('.camara-contact-pill, .camara-sello-wrap').forEach(el => {
    el.addEventListener('mouseenter', () => { camaraTip.style.opacity = '1'; });
    el.addEventListener('mouseleave', () => { camaraTip.style.opacity = '0'; });
    el.addEventListener('mousemove', e => {
      camaraTip.style.left = e.clientX + 'px';
      camaraTip.style.top  = (e.clientY - 44) + 'px';
    });
  });
}
