// ClearLoan — shared helpers: escaping, icons, session guard, header, stepper, toasts
(function () {
  const cfg = window.CL_CONFIG;

  // Always escape data before putting it in HTML (protects against XSS)
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const store = {
    get(k) { try { return JSON.parse(sessionStorage.getItem(k) || 'null'); } catch (e) { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* ignore */ } },
    del(k) { try { sessionStorage.removeItem(k); } catch (e) { /* ignore */ } }
  };

  // ---------- Icons (Lucide-style strokes, one family everywhere)
  const P = {
    shield: '<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    chart: '<path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/>',
    scale: '<path d="M12 3v18"/><path d="M5 7h14"/><path d="M5 7l-3 7a3 3 0 0 0 6 0z"/><path d="M19 7l-3 7a3 3 0 0 0 6 0z"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18z"/>',
    check: '<path d="M5 12l5 5L20 7"/>',
    alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6"/><path d="M12 16.5v.5"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/><path d="M12 7.5v.5"/>',
    arrow: '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    chip: '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 1v4M15 1v4M9 19v4M15 19v4M1 9h4M1 15h4M19 9h4M19 15h4"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    users: '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M16 4a4 4 0 0 1 0 8M22 21a7 7 0 0 0-4-6.3"/>',
    file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>',
    eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    eyeOff: '<path d="M3 3l18 18"/><path d="M10.6 5.1A10.9 10.9 0 0 1 12 5c6.5 0 10 7 10 7a17.7 17.7 0 0 1-3.2 4.2"/><path d="M6.6 6.6A17.4 17.4 0 0 0 2 12s3.5 7 10 7a10.7 10.7 0 0 0 5.4-1.4"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
    inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.1L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1z"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    printer: '<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
    up: '<path d="M22 7l-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    down: '<path d="M22 17l-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
    sparkle: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 16l.7 1.8 1.8.7-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z"/>',
    key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="M10.7 12.3L21 2M17 6l3 3M14 9l2 2"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    db: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    x: '<path d="M18 6L6 18M6 6l12 12"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    gauge: '<path d="M12 14l4-4"/><path d="M3.3 19a10 10 0 1 1 17.4 0"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    wallet: '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3"/><path d="M21 9h-6a3 3 0 0 0 0 6h6z"/>',
    history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>'
  };
  const icon = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${P[name] || ''}</svg>`;
  const ico = (name) => `<i data-icon="${name}">${icon(name)}</i>`;
  function hydrateIcons(root) {
    (root || document).querySelectorAll('i[data-icon]:empty').forEach((el) => { el.innerHTML = icon(el.dataset.icon); });
  }

  // ---------- Formatting
  const fmt = (n) => Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
  const money = (n) => 'AED ' + fmt(n);
  const toDate = (ts) => new Date(ts);
  const date = (ts) => toDate(ts).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const dateTime = (ts) => `${date(ts)}, ${toDate(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`;
  const clock = (ts) => { const d = toDate(ts); return d.toTimeString().slice(0, 8) + '.' + String(d.getMilliseconds()).padStart(3, '0'); };
  const params = new URLSearchParams(window.location.search);

  // ---------- Toasts (aria-live, never steal focus)
  function toast(message, kind) {
    let box = document.getElementById('toasts');
    if (!box) {
      box = document.createElement('div');
      box.id = 'toasts'; box.className = 'toasts'; box.setAttribute('aria-live', 'polite'); box.setAttribute('role', 'status');
      document.body.appendChild(box);
    }
    const t = document.createElement('div');
    t.className = 'toast' + (kind === 'warn' ? ' warn' : '');
    t.innerHTML = ico(kind === 'warn' ? 'alert' : 'check') + `<span>${esc(message)}</span>`;
    box.appendChild(t);
    setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 200); }, 4200);
  }

  function busy(btn, on) {
    btn.disabled = on;
    btn.classList.toggle('is-loading', on);
    btn.setAttribute('aria-busy', String(on));
  }

  // ---------- Session (the server is the source of truth; this copy only drives the header)
  const NAV = {
    applicant: [['apply.html', 'Apply', 'plus'], ['decision.html', 'My decision', 'gauge'], ['privacy.html', 'Privacy proof', 'eye']],
    staff: [['fairness.html', 'Fairness', 'scale'], ['reviews.html', 'Reviews', 'inbox'], ['privacy.html', 'Audit log', 'list']]
  };
  const home = (role) => NAV[role][0][0];

  function saveSession(s) { store.set('cl_session', { role: s.role, display_name: s.display_name, last: Date.now() }); }
  function localSession() {
    const s = store.get('cl_session');
    if (!s) return null;
    if (Date.now() - s.last > cfg.SESSION_MINUTES * 60000) { store.del('cl_session'); return null; }
    return s;
  }
  function touch() { const s = store.get('cl_session'); if (s) { s.last = Date.now(); store.set('cl_session', s); } }

  async function signOut(reason) {
    try { await API.logout(); } catch (e) { /* already signed out */ }
    store.del('cl_session'); store.del('cl_last_result');
    window.location.href = 'index.html' + (reason ? '?' + reason + '=1' : '');
  }

  function renderHeader(active, session) {
    const header = document.getElementById('site-header');
    if (!header) return;
    const links = session ? NAV[session.role] || [] : [];
    const dark = window.CL_THEME && CL_THEME.current() === 'dark';
    header.className = 'site-header';
    header.innerHTML = `
      <div class="inner">
        <a class="brand" href="${session ? esc(home(session.role)) : 'index.html'}"><span class="brand-mark">${ico('shield')}</span><span>ClearLoan</span></a>
        <nav class="main-nav" aria-label="Main">
          ${links.map(([href, label, ic]) => `<a href="${esc(href)}"${href === active ? ' aria-current="page"' : ''}>${ico(ic)}<span>${esc(label)}</span>${href === 'reviews.html' ? '<span class="nav-badge hidden" id="nav-reviews"></span>' : ''}</a>`).join('')}
        </nav>
        <div class="header-right">
          ${cfg.USE_MOCK ? '<span class="chip chip-mock">Sample data</span>' : ''}
          <span class="badge-linuxone" title="Runs on IBM LinuxONE">${ico('chip')}<span>Runs on IBM LinuxONE</span></span>
          <button class="icon-btn" type="button" id="theme-btn" aria-label="Switch to ${dark ? 'light' : 'dark'} theme" title="Switch theme">${ico(dark ? 'sun' : 'moon')}</button>
          ${session ? `<span class="user-chip"><span class="avatar" aria-hidden="true">${esc((session.display_name || '?').slice(0, 1).toUpperCase())}</span><span class="uname">${esc(session.display_name)} · ${esc(session.role)}</span></span>
            <button class="btn-signout" type="button" id="signout" aria-label="Sign out" title="Sign out">${ico('logout')}<span>Sign out</span></button>` : ''}
        </div>
      </div>`;
    document.getElementById('theme-btn').addEventListener('click', () => { CL_THEME.toggle(); renderHeader(active, session); });
    const out = document.getElementById('signout');
    if (out) out.addEventListener('click', () => signOut());

    if (!document.querySelector('.skip-link')) {
      const skip = document.createElement('a');
      skip.className = 'skip-link'; skip.href = '#main'; skip.textContent = 'Skip to content';
      document.body.prepend(skip);
    }
    const main = document.querySelector('main');
    if (main && !main.id) main.id = 'main';
    renderFooter();
  }

  function renderFooter() {
    if (document.querySelector('footer.site-footer')) return;
    const f = document.createElement('footer');
    f.className = 'site-footer';
    f.innerHTML = '<span>ClearLoan · Team Made To Rise · IBM Z Datathon 2026</span><span>Private · Fair · Explainable</span>';
    document.body.appendChild(f);
  }

  // Applicant journey: 1 Apply → 2 Decision → 3 Privacy proof
  function stepper(current, appId) {
    const el = document.getElementById('stepper');
    if (!el) return;
    const q = appId ? '?id=' + encodeURIComponent(appId) : '';
    const steps = [['apply.html', 'Apply', 'Fill in the form'], ['decision.html' + q, 'Decision', 'Reasons and next steps'], ['privacy.html' + q, 'Privacy proof', 'What the AI saw']];
    el.className = 'stepper';
    el.setAttribute('aria-label', 'Your progress');
    el.innerHTML = steps.map(([href, label, long], i) => {
      const n = i + 1;
      const attrs = n === current ? ' aria-current="step"' : '';
      const cls = n < current ? ' class="done"' : '';
      const disabled = n > 1 && !appId && n !== current ? ' aria-disabled="true" tabindex="-1"' : '';
      return `<li${cls}><a href="${esc(href)}"${attrs}${disabled}><span class="n">${n < current ? icon('check') : n}</span><span>${esc(label)}<span class="lbl-long xsmall muted" style="display:block;font-weight:400">${esc(long)}</span></span></a></li>`;
    }).join('');
  }

  // Call at the top of each protected page. Resolves with the session, or redirects.
  async function guard(active, roles) {
    let s = localSession();
    if (!cfg.USE_MOCK) {
      try {
        const me = await API.me();
        if (!me) { store.del('cl_session'); window.location.replace('index.html' + (s ? '?expired=1' : '')); return null; }
        s = { role: me.role, display_name: me.display_name };
        saveSession(s);
      } catch (e) {
        renderHeader(active, s);
        hydrateIcons();
        toast(e.message, 'warn');
        return null;
      }
    }
    if (!s) { window.location.replace('index.html'); return null; }
    if (roles && !roles.includes(s.role)) { window.location.replace(home(s.role)); return null; }
    renderHeader(active, s);
    hydrateIcons();
    ['click', 'keydown'].forEach((ev) => document.addEventListener(ev, touch, { passive: true }));
    setInterval(() => { if (!localSession()) signOut('expired'); }, 30000);
    if (s.role === 'staff' && API.reviews) {
      API.reviews().then((items) => {
        const open = items.filter((x) => x.status === 'open').length;
        const b = document.getElementById('nav-reviews');
        if (b && open) { b.textContent = open; b.classList.remove('hidden'); b.setAttribute('aria-label', open + ' open'); }
      }).catch(() => {});
    }
    return s;
  }

  // Inline form errors: message under the field, linked with aria-describedby
  function fieldError(input, message) {
    clearFieldError(input);
    input.setAttribute('aria-invalid', 'true');
    const p = document.createElement('p');
    p.className = 'field-error'; p.id = input.id + '-error';
    p.innerHTML = ico('alert') + `<span>${esc(message)}</span>`;
    (input.closest('.input-affix') || input).insertAdjacentElement('afterend', p);
    input.setAttribute('aria-describedby', p.id);
  }
  function clearFieldError(input) {
    input.removeAttribute('aria-invalid');
    const old = document.getElementById(input.id + '-error');
    if (old) old.remove();
    if (input.getAttribute('aria-describedby') === input.id + '-error') input.removeAttribute('aria-describedby');
  }

  window.CL = { esc, store, icon, ico, hydrateIcons, fmt, money, date, dateTime, clock, params, toast, busy,
    NAV, home, saveSession, localSession, signOut, renderHeader, stepper, guard, fieldError, clearFieldError };
})();
