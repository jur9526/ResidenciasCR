// ── Modal de detalle de propiedad ─────────────────────────────
(function () {
  'use strict';

  const FALLBACK = 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=1200&q=80';
  let gallery = [], galIdx = 0, openedAt = 0, savedScrollY = 0, ignoreNextPopstate = false;
  let shareUrl = '', sharePropTitle = '';

  /* ── Inyectar HTML ─────────────────────────────── */
  document.body.insertAdjacentHTML('beforeend', `
<div id="propModal" class="pmodal" role="dialog" aria-modal="true">
  <div class="pmodal-overlay" id="pmodalOverlay"></div>
  <div class="pmodal-panel">
    <button class="pmodal-close" id="pmodalClose" aria-label="Cerrar">
      <i class="fa-solid fa-xmark"></i>
    </button>
    <!-- Fila principal: scroll principal + columna contacto fija -->
    <div class="pmodal-body-row">
      <div class="pmodal-scroll" id="pmodalScroll">
        <div id="pmodalBody"></div>
      </div>
      <!-- Columna contacto fuera del scroll → siempre visible -->
      <div class="pmodal-contact-col" id="pmodalContactCol" style="display:none"></div>
    </div>
    <!-- Botón WA flotante mobile (aparece después de la animación) -->
    <a id="pmodalWaFab" href="#" target="_blank" rel="noopener"
       class="pmodal-wa-fab" style="display:none">
      <i class="fa-brands fa-whatsapp"></i>
      <span>WhatsApp</span>
    </a>
  </div>
</div>

<!-- Lightbox para foto ampliada -->
<div id="pmodalLightbox" class="pmodal-lb" style="display:none" onclick="this.style.display='none'">
  <button class="pmodal-lb-close" onclick="document.getElementById('pmodalLightbox').style.display='none'">
    <i class="fa-solid fa-xmark"></i>
  </button>
  <button class="pmodal-lb-arr pmodal-lb-prev" id="pmodalLbPrev">
    <i class="fa-solid fa-chevron-left"></i>
  </button>
  <img id="pmodalLbImg" src="" alt="" onclick="event.stopPropagation()" />
  <button class="pmodal-lb-arr pmodal-lb-next" id="pmodalLbNext">
    <i class="fa-solid fa-chevron-right"></i>
  </button>
  <div class="pmodal-lb-counter" id="pmodalLbCounter"></div>
</div>`);

  const modal      = document.getElementById('propModal');
  const overlay    = document.getElementById('pmodalOverlay');
  const closeBtn   = document.getElementById('pmodalClose');
  const bodyEl     = document.getElementById('pmodalBody');
  const contactCol = document.getElementById('pmodalContactCol');
  const scroll     = document.getElementById('pmodalScroll');
  const waFab    = document.getElementById('pmodalWaFab');
  const lb       = document.getElementById('pmodalLightbox');
  const lbImg    = document.getElementById('pmodalLbImg');
  const lbPrev   = document.getElementById('pmodalLbPrev');
  const lbNext   = document.getElementById('pmodalLbNext');
  const lbCount  = document.getElementById('pmodalLbCounter');

  /* ── Helpers ──────────────────────────────────── */
  function getImg(prop) {
    if (prop.image && prop.image.trim()) return prop.image;
    if (prop.e24id) return `assets/e24-${prop.e24id}.webp`;
    return FALLBACK;
  }

  function dedupeGallery(imgs) {
    const seen = new Set(), out = [];
    for (const url of imgs) {
      const m = url.match(/-([a-f0-9]{7})$/);
      const key = m ? m[1] : url;
      if (seen.has(key)) continue;
      seen.add(key);
      // Store large version — used only in lightbox
      out.push(url.replace(/\/t_or_fh_[ms]\//, '/t_or_fh_l/'));
    }
    return out;
  }

  // Downscale URL for faster loading (l=lightbox, m=main-photo, s=thumbnail)
  function toSize(url, size) {
    return url.replace(/\/t_or_fh_[lms]\//, `/t_or_fh_${size}/`);
  }

  /* ── Carga lazy de thumbnails ────────────────── */
  function loadThumb(i) {
    const thumbs = document.querySelectorAll('.pmodal-thumb');
    if (i < 0 || i >= thumbs.length) return;
    const img = thumbs[i].querySelector('img[data-src]');
    if (img) {
      img.src = toSize(img.dataset.src, 's');
      img.removeAttribute('data-src');
    }
  }

  /* ── Galería principal ────────────────────────── */
  function goTo(idx) {
    if (!gallery.length) return;
    galIdx = ((idx % gallery.length) + gallery.length) % gallery.length;

    const mainImg = document.getElementById('pmodalMainPhoto');
    if (mainImg) {
      mainImg.style.opacity = '0';
      mainImg.src = gallery[galIdx];
      mainImg.onload  = () => { mainImg.style.opacity = '1'; };
      mainImg.onerror = () => { mainImg.src = FALLBACK; mainImg.style.opacity = '1'; };
    }

    // Marcar thumbnail activo y scrollear
    document.querySelectorAll('.pmodal-thumb').forEach((t, i) => {
      t.classList.toggle('active', i === galIdx);
      if (i === galIdx) t.scrollIntoView({ inline: 'nearest', block: 'nearest', behavior: 'smooth' });
    });

    // Actualizar contador
    const counter = document.getElementById('pmodalCounter');
    if (counter) counter.textContent = `${galIdx + 1} / ${gallery.length}`;
  }

  /* ── Lightbox ─────────────────────────────────── */
  function openLightbox(idx) {
    galIdx = idx;
    lbImg.src = gallery[galIdx];
    lbCount.textContent = `${galIdx + 1} / ${gallery.length}`;
    lb.style.display = 'flex';
  }

  function lbGoTo(idx) {
    galIdx = ((idx % gallery.length) + gallery.length) % gallery.length;
    lbImg.style.opacity = '0';
    lbImg.src = gallery[galIdx];
    lbImg.onload = () => { lbImg.style.opacity = '1'; };
    lbCount.textContent = `${galIdx + 1} / ${gallery.length}`;
  }

  lbPrev.addEventListener('click', e => { e.stopPropagation(); lbGoTo(galIdx - 1); });
  lbNext.addEventListener('click', e => { e.stopPropagation(); lbGoTo(galIdx + 1); });

  /* ── Abrir modal ──────────────────────────────── */
  function open(prop) {
    if (!prop) return;

    const e24imgs = dedupeGallery(prop.all_images || []);
    gallery  = e24imgs.length > 0 ? e24imgs : [getImg(prop)];
    galIdx   = 0;

    // Usar el link real de encuentra24; fallback al inicio del sitio
    const propLink = prop.e24url || 'https://www.residenciascostarica.com';
    const waMsg  = encodeURIComponent(
      `Hola Floribeth, te escribo desde www.residenciascostarica.com. Me interesa la propiedad: ${prop.title}. Link: ${propLink}`
    );
    const waHref = `https://wa.me/50683725603?text=${waMsg}`;

    const badge  = prop.badge || 'En Venta';
    const tagCls = (prop.badgeClass || '').includes('special') ? 'pmodal-tag-green' : 'pmodal-tag-red';
    const beds    = prop.beds   > 0 ? `<div class="pmodal-stat"><span class="pmodal-stat-val">${prop.beds}</span><span class="pmodal-stat-lbl">Recámaras</span></div>` : '';
    const baths   = prop.baths  > 0 ? `<div class="pmodal-stat"><span class="pmodal-stat-val">${prop.baths}</span><span class="pmodal-stat-lbl">Baños</span></div>` : '';
    const area    = prop.area   ? `<div class="pmodal-stat"><span class="pmodal-stat-val">${prop.area}</span><span class="pmodal-stat-lbl">Área</span></div>` : '';
    const parking = prop.parking > 0 ? `<div class="pmodal-stat"><span class="pmodal-stat-val">${prop.parking}</span><span class="pmodal-stat-lbl">Parking</span></div>` : '';

    // Thumbnails — todos cargan al abrir (t_or_fh_s son ~5-10KB, total mínimo)
    const thumbsHTML = gallery.map((src, i) => {
      const thumbSrc = toSize(src, 's');
      return `<button class="pmodal-thumb${i === 0 ? ' active' : ''}"
        onclick="window._pGoTo(${i})" type="button">
        <img src="${thumbSrc}" loading="lazy" onerror="this.parentElement.style.display='none'" />
      </button>`;
    }).join('');

    const amens    = prop.amenities || [];
    const amenHTML = amens.length > 0 ? `
      <div class="pmodal-section">
        <div class="pmodal-section-title">Amenidades y servicios</div>
        <div class="pmodal-amenities">
          ${amens.map(a => `<div class="pmodal-amen"><i class="fa-solid fa-check"></i>${a}</div>`).join('')}
        </div>
      </div>` : '';

    const descHTML = prop.description ? `
      <div class="pmodal-section">
        <div class="pmodal-section-title">Descripción</div>
        <div class="pmodal-desc">${prop.description.replace(/\n/g, '<br>')}</div>
      </div>` : '';

    const hasMany = gallery.length > 1;

    bodyEl.innerHTML = `
      <div class="pmodal-layout">
        <div class="pmodal-main">

          <!-- ── Galería ── -->
          <div class="pmodal-gallery">

            <!-- Foto principal — click para zoom (con guardia anti-ghost-tap) -->
            <div class="pmodal-gallery-main" style="cursor:zoom-in"
                 onclick="if(Date.now()-window._pOpenedAt()>500)window._pOpenLb(window._pIdx())">
              <img id="pmodalMainPhoto" src="${gallery[0]}" alt="${prop.title}"
                   class="pmodal-main-photo" onerror="this.src='${FALLBACK}'"
                   fetchpriority="high" style="transition:opacity .2s" />
              <span class="${tagCls} pmodal-photo-badge">${badge}</span>
              <div class="pmodal-photo-counter" id="pmodalCounter">1 / ${gallery.length}</div>
              <div class="pmodal-zoom-hint"><i class="fa-solid fa-expand"></i></div>
            </div>

            <!-- Flechas — fuera de gallery-main para que no se recorten -->
            ${hasMany ? `
            <button class="pmodal-arrow pmodal-arrow-prev" onclick="event.stopPropagation();window._pGoTo(window._pIdx()-1)" type="button">
              <i class="fa-solid fa-chevron-left"></i>
            </button>
            <button class="pmodal-arrow pmodal-arrow-next" onclick="event.stopPropagation();window._pGoTo(window._pIdx()+1)" type="button">
              <i class="fa-solid fa-chevron-right"></i>
            </button>` : ''}

            <!-- Thumbnails -->
            ${hasMany ? `<div class="pmodal-thumbs">${thumbsHTML}</div>` : ''}
          </div>

          <!-- ── Info ── -->
          <div class="pmodal-info-block">
            <div class="pmodal-title-row">
              <h2 class="pmodal-title">${prop.title}</h2>
              <button class="pmodal-share-btn" onclick="window._pShare()" type="button" title="Compartir">
                <i class="fa-solid fa-share-nodes"></i><span>Compartir</span>
              </button>
            </div>
            <div class="pmodal-location-row"><i class="fa-solid fa-location-dot"></i> ${prop.location}</div>
            <div class="pmodal-price-row"><span class="pmodal-price">${prop.price}</span></div>
            ${(beds||baths||area||parking) ? `<div class="pmodal-stats-row">${beds}${baths}${area}${parking}</div>` : ''}

            <div class="pmodal-section">
              <div class="pmodal-section-title">Detalles adicionales</div>
              <div class="pmodal-details-grid">
                <div class="pmodal-detail-item"><span class="pmodal-detail-lbl">Tipo</span><span class="pmodal-detail-val">${prop.type||'Casa'}</span></div>
                <div class="pmodal-detail-item"><span class="pmodal-detail-lbl">Operación</span><span class="pmodal-detail-val">${badge}</span></div>
                ${prop.area ? `<div class="pmodal-detail-item"><span class="pmodal-detail-lbl">Área</span><span class="pmodal-detail-val">${prop.area}</span></div>` : ''}
                ${prop.parking>0 ? `<div class="pmodal-detail-item"><span class="pmodal-detail-lbl">Parqueos</span><span class="pmodal-detail-val">${prop.parking}</span></div>` : ''}
              </div>
            </div>
            ${amenHTML}${descHTML}
          </div>

          <!-- Contacto mobile (oculto en desktop) -->
          <div class="pmodal-mobile-contact">
            <div class="pmodal-contact-title">Consultar propiedad</div>
            <a href="tel:+50683725603" class="pmodal-cta-call">
              <i class="fa-solid fa-phone"></i> Llamar
            </a>
            <a href="${waHref}" target="_blank" rel="noopener" class="pmodal-cta-wa"
               onclick="typeof gtagSendEvent==='function'&&gtagSendEvent('${waHref}')">
              <i class="fa-brands fa-whatsapp"></i> WhatsApp
            </a>
            <div class="pmodal-form-sep"></div>
            <form class="pmodal-email-form" onsubmit="window._pSendEmail(event, this)">
              <input type="hidden" name="access_key" value="cd9e63a3-13ad-4f01-bdbe-fdda47e172a9" />
              <input type="hidden" name="to" value="flory@residenciascostarica.com" />
              <input type="hidden" name="subject" value="Consulta: ${prop.title.replace(/'/g,"\\'")} — residenciascostarica.com" />
              <input type="hidden" name="redirect" value="false" />
              <input type="hidden" name="prop_titulo" value="${prop.title.replace(/"/g,'&quot;')}" />
              <input type="hidden" name="prop_link" value="${propLink}" />
              <input class="pmodal-email-input" name="nombre" type="text" placeholder="Tu nombre" required />
              <input class="pmodal-email-input" name="email" type="email" placeholder="Tu email" required />
              <input class="pmodal-email-input" name="telefono" type="tel" placeholder="Tu teléfono" />
              <textarea class="pmodal-email-input" name="message" rows="3"
                placeholder="Hola, me interesa esta propiedad..."></textarea>
              <button class="pmodal-email-send" type="submit">
                <i class="fa-solid fa-paper-plane"></i> Enviar
              </button>
              <div class="pmodal-email-ok">
                <i class="fa-solid fa-circle-check"></i> ¡Mensaje enviado!
              </div>
            </form>
          </div>
        </div>
      </div>`;

    // ── Columna contacto (fuera del scroll) ──────────
    contactCol.style.display = '';
    contactCol.innerHTML = `
      <div class="pmodal-contact-card">
        <div class="pmodal-agent-row">
          <img src="flory.jpg" alt="Floribeth Elizondo" class="pmodal-agent-avatar" onerror="this.style.display='none'" />
          <div>
            <div class="pmodal-agent-name">Floribeth Elizondo <i class="fa-solid fa-circle-check pmodal-verified"></i></div>
            <div class="pmodal-agent-role">Profesional Inmobiliaria</div>
          </div>
        </div>
        <!-- Acciones sticky: siempre visibles al hacer scroll en la columna -->
        <div class="pmodal-contact-actions">
          <div class="pmodal-contact-title">Enviar consulta</div>
          <a href="tel:+50683725603" class="pmodal-cta-call">
            <i class="fa-solid fa-phone"></i> Llamar
          </a>
          <a href="${waHref}" target="_blank" rel="noopener" class="pmodal-cta-wa"
             onclick="typeof gtagSendEvent==='function'&&gtagSendEvent('${waHref}')">
            <i class="fa-brands fa-whatsapp"></i> WhatsApp
          </a>
        </div>
        <div class="pmodal-form-sep"></div>
        <form class="pmodal-email-form" onsubmit="window._pSendEmail(event, this)">
          <input type="hidden" name="access_key" value="cd9e63a3-13ad-4f01-bdbe-fdda47e172a9" />
          <input type="hidden" name="to" value="flory@residenciascostarica.com" />
          <input type="hidden" name="subject" value="Consulta: ${prop.title.replace(/'/g,"\\'")} — residenciascostarica.com" />
          <input type="hidden" name="redirect" value="false" />
          <input type="hidden" name="prop_titulo" value="${prop.title.replace(/"/g,'&quot;')}" />
          <input type="hidden" name="prop_link" value="${propLink}" />
          <input class="pmodal-email-input" name="nombre" type="text" placeholder="Tu nombre" required />
          <input class="pmodal-email-input" name="email" type="email" placeholder="Tu email" required />
          <input class="pmodal-email-input" name="telefono" type="tel" placeholder="Tu teléfono" />
          <textarea class="pmodal-email-input" name="message" rows="3"
            placeholder="Hola, me interesa esta propiedad..."></textarea>
          <button class="pmodal-email-send" type="submit">
            <i class="fa-solid fa-paper-plane"></i> Enviar
          </button>
          <div class="pmodal-email-ok">
            <i class="fa-solid fa-circle-check"></i> ¡Mensaje enviado!
          </div>
        </form>

        <p class="pmodal-free-note"><i class="fa-solid fa-circle-check"></i> Servicio <strong>gratis</strong> para el comprador</p>
        <div class="pmodal-trust">
          <div><i class="fa-solid fa-building-columns"></i> +10 bancos disponibles</div>
          <div><i class="fa-solid fa-medal"></i> 200+ cierres exitosos</div>
          <div><i class="fa-solid fa-award"></i> Cámara de Comercio CR</div>
        </div>
      </div>`;

    // Botón WA flotante mobile
    waFab.href = waHref;

    modal.style.display = 'flex';
    openedAt = Date.now();
    requestAnimationFrame(() => requestAnimationFrame(() => modal.classList.add('pmodal-open')));
    savedScrollY = window.scrollY;
    document.body.style.overflow = 'hidden';
    scroll.scrollTop = 0;

    // URL compartible: ?prop=XXXXX — al abrir se actualiza, al cerrar se restaura
    const _u = new URL(window.location.href);
    _u.searchParams.set('prop', prop.e24id);
    shareUrl = _u.toString();
    sharePropTitle = prop.title;
    history.pushState({ pmodal: true }, '', shareUrl);

    // Mostrar FAB mobile con delay (tras la animación del modal)
    setTimeout(() => { waFab.style.display = 'flex'; }, 450);
  }

  /* ── Enviar email via Web3Forms ───────────────── */
  window._pSendEmail = async function(e, form) {
    e.preventDefault();
    const btn    = form.querySelector('.pmodal-email-send');
    const ok     = form.querySelector('.pmodal-email-ok');
    const titulo = form.querySelector('[name="prop_titulo"]').value;
    const link   = form.querySelector('[name="prop_link"]').value;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enviando...';
    try {
      const fd  = new FormData(form);
      const msg = fd.get('message') || '';
      const tel = fd.get('telefono') || '';
      fd.set('message',
        `Propiedad: ${titulo}\nLink: ${link}${tel ? '\nTeléfono: '+tel : ''}\n\n${msg}`
      );
      const res = await fetch('https://api.web3forms.com/submit', { method:'POST', body: fd });
      if (res.ok) {
        form.reset();
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Enviar';
        ok.style.display = 'flex';
        setTimeout(() => { ok.style.display = 'none'; }, 4000);
      } else { throw new Error(); }
    } catch {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Reintentar';
    }
  };

  /* ── Cerrar modal ─────────────────────────────── */
  function closeUI() {
    if (!modal.classList.contains('pmodal-open')) return;
    modal.classList.remove('pmodal-open');
    waFab.style.display = 'none';
    contactCol.style.display = 'none';
    document.body.style.overflow = '';
    window.scrollTo(0, savedScrollY);
    setTimeout(() => { modal.style.display = 'none'; }, 180);
    gallery = []; galIdx = 0;
  }

  function close() {
    closeUI();
    // Limpiar la entrada de historial que creamos al abrir, ignorando el popstate resultante
    if (history.state && history.state.pmodal) {
      ignoreNextPopstate = true;
      history.back();
    }
  }

  // Botón Atrás del navegador cierra el modal
  window.addEventListener('popstate', () => {
    if (ignoreNextPopstate) { ignoreNextPopstate = false; return; }
    if (modal.classList.contains('pmodal-open')) closeUI();
  });

  closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', close);

  /* ── Teclado y swipe ──────────────────────────── */
  document.addEventListener('keydown', e => {
    if (lb.style.display !== 'none') {
      if (e.key === 'Escape')     { lb.style.display = 'none'; }
      if (e.key === 'ArrowLeft')  lbGoTo(galIdx - 1);
      if (e.key === 'ArrowRight') lbGoTo(galIdx + 1);
      return;
    }
    if (!modal.classList.contains('pmodal-open')) return;
    if (e.key === 'Escape')     close();
    if (e.key === 'ArrowLeft')  goTo(galIdx - 1);
    if (e.key === 'ArrowRight') goTo(galIdx + 1);
  });

  let tx = 0;
  modal.addEventListener('touchstart', e => { tx = e.touches[0].clientX; }, { passive: true });
  modal.addEventListener('touchend',   e => {
    const dx = e.changedTouches[0].clientX - tx;
    if (Math.abs(dx) > 50) goTo(galIdx + (dx < 0 ? 1 : -1));
  });

  /* ── Compartir propiedad ──────────────────────── */
  window._pShare = function () {
    const data = {
      title: `🏡 ${sharePropTitle}`,
      text:  `Mirá esta propiedad en Residencias Costa Rica`,
      url:   shareUrl,
    };
    if (navigator.share) {
      navigator.share(data).catch(() => {});
      return;
    }
    // Fallback desktop: mostrar dropdown
    let dd = document.getElementById('pmodalShareDd');
    if (dd) { dd.classList.toggle('pmodal-share-dd--open'); return; }
    dd = document.createElement('div');
    dd.id = 'pmodalShareDd';
    dd.className = 'pmodal-share-dd pmodal-share-dd--open';
    const waText = encodeURIComponent(`🏡 ${sharePropTitle}\n${shareUrl}`);
    dd.innerHTML = `
      <button class="pmodal-share-dd-item" onclick="navigator.clipboard.writeText('${shareUrl.replace(/'/g,"\\'")}').then(()=>{this.textContent='✓ ¡Link copiado!';setTimeout(()=>this.textContent='Copiar link',1800)})">
        <i class="fa-regular fa-copy"></i> Copiar link
      </button>
      <a class="pmodal-share-dd-item" href="https://wa.me/?text=${waText}" target="_blank" rel="noopener">
        <i class="fa-brands fa-whatsapp"></i> WhatsApp
      </a>`;
    const btn = document.querySelector('.pmodal-share-btn');
    btn.parentElement.style.position = 'relative';
    btn.parentElement.appendChild(dd);
    document.addEventListener('click', function hide(e) {
      if (!dd.contains(e.target) && e.target !== btn) { dd.classList.remove('pmodal-share-dd--open'); document.removeEventListener('click', hide); }
    }, { capture: true, once: false });
  };

  /* ── Auto-abrir si la URL trae ?prop= ────────── */
  function openFromUrl() {
    const pid = new URLSearchParams(window.location.search).get('prop');
    if (!pid || !window.DEFAULT_PROPERTIES) return;
    const prop = window.DEFAULT_PROPERTIES.find(p => p.e24id === pid);
    if (prop) open(prop);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(openFromUrl, 100));
  } else {
    setTimeout(openFromUrl, 100);
  }

  /* ── Exponer globals ──────────────────────────── */
  window.openPropModal = open;
  window._pGoTo     = goTo;
  window._pIdx      = () => galIdx;
  window._pOpenLb   = (i) => openLightbox(i);
  window._pOpenedAt = () => openedAt;
})();
