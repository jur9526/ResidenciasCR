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
let properties = [];

function loadProperties() {
  try {
    const stored = localStorage.getItem('rcr_properties');
    if (stored) {
      properties = JSON.parse(stored);
    } else {
      properties = window.DEFAULT_PROPERTIES || [];
    }
  } catch (e) {
    properties = window.DEFAULT_PROPERTIES || [];
  }
}

function getPropertyImage(prop) {
  if (prop.image && prop.image.trim()) return prop.image;
  if (prop.e24id) return `assets/e24-${prop.e24id}.jpg`;
  return 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=800&q=80';
}

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
  return `
    <div class="property-card reveal">
      <div class="property-img">
        <img src="${getPropertyImage(prop)}" alt="${prop.title}" loading="lazy"
             onerror="this.src='https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=800&q=80'"/>
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

function renderProperties() {
  const grid       = document.getElementById('propertiesGrid');
  const loadMoreBtn = document.getElementById('loadMoreBtn');
  if (!grid) return;

  const end   = (currentPage + 1) * PROPS_PER_PAGE;
  const slice = properties.slice(0, end);

  grid.innerHTML = slice.map(buildPropertyCard).join('');
  grid.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));

  if (loadMoreBtn) {
    loadMoreBtn.style.display = end < properties.length ? 'inline-flex' : 'none';
  }
}

const loadMoreBtn = document.getElementById('loadMoreBtn');
if (loadMoreBtn) {
  loadMoreBtn.addEventListener('click', () => {
    currentPage++;
    renderProperties();
    document.getElementById('propertiesGrid').lastElementChild
      .scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
}

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
