// ClearLoan — decision page
(async function () {
  const session = await CL.guard('decision.html', ['applicant']);
  if (!session) return;

  const $ = (id) => document.getElementById(id);
  const esc = CL.esc;
  const LANG_NAMES = { en: 'English', ar: 'العربية', ur: 'اردو', hi: 'हिन्दी', fr: 'Français' };
  const RTL = ['ar', 'ur'];

  function empty(title, text) {
    $('loading').classList.add('hidden');
    if (title) $('empty-title').textContent = title;
    if (text) $('empty-text').textContent = text;
    $('empty').classList.remove('hidden');
    CL.stepper(2, null);
  }

  // Which application? ?id=… or the most recent one
  let r;
  try {
    let id = CL.params.get('id');
    if (!id) {
      const items = await API.applications();
      if (!items.length) return empty();
      id = items[0].application_id;
      history.replaceState(null, '', 'decision.html?id=' + encodeURIComponent(id));
    }
    r = await API.application(id);
  } catch (e) {
    return empty(e.status === 404 ? 'Application not found' : 'Could not load your decision', e.message);
  }
  if (!r) return empty();

  CL.stepper(2, r.application_id);
  $('loading').classList.add('hidden');
  $('content').classList.remove('hidden');
  $('print-btn').classList.remove('hidden');
  $('print-btn').addEventListener('click', () => window.print());

  const modelApproved = r.model.decision === 'approved';
  const approved = (r.final_decision || r.model.decision) === 'approved';
  const byHuman = approved && !modelApproved;
  const risk = Number(r.model.risk_score);
  const limit = r.model.limit || CL_CONFIG.APPROVAL_LIMIT;
  const amount = CL.money(r.request.loan_amount);

  $('meta').textContent = `Application ${r.application_id} · ${CL.dateTime(r.created_at)} · decided in ${(r.latency_ms / 1000).toFixed(2)} s on LinuxONE`;

  // ---------- Decision card + gauge
  const box = $('decision');
  box.className = 'decision reveal ' + (approved ? 'approved' : 'rejected');
  const level = risk <= 35 ? 'Low risk' : risk <= limit ? 'Medium risk' : 'High risk';
  const color = modelApproved ? 'var(--brand)' : 'var(--warn)';
  const th = Math.PI * (1 - limit / 100);
  const lx1 = 100 + 66 * Math.cos(th), ly1 = 100 - 66 * Math.sin(th), lx2 = 100 + 94 * Math.cos(th), ly2 = 100 - 94 * Math.sin(th);
  const title = byHuman ? 'Approved after review' : approved ? 'Approved' : 'Not approved yet';
  const text = byHuman
    ? `A credit officer reviewed your file and approved your loan of ${amount}.`
    : approved
      ? `Good news: your loan of ${amount} is approved.`
      : `We can't approve ${amount} today, but this is not a final answer. See why below, how to improve, or ask a person to review it.`;
  box.innerHTML = `
    <div class="status">
      <span class="icon">${CL.ico(approved ? 'check' : 'alert')}</span>
      <div>
        <h2>${esc(title)}</h2>
        <p>${esc(text)}</p>
        <div class="chips">
          <span class="chip chip-outline">${CL.ico('chart')}Model: ${esc(r.model_used.replace(/_/g, ' '))}</span>
          <span class="chip chip-outline">${CL.ico('wallet')}${esc(amount)}</span>
          <span class="chip chip-outline">${CL.ico('globe')}${esc(LANG_NAMES[r.llm.language] || r.llm.language)}</span>
        </div>
      </div>
    </div>
    <div class="gauge-card">
      <p class="label">Risk score</p>
      <svg class="gauge" viewBox="0 0 200 118" role="img" aria-label="Risk score ${risk} out of 100. Approval limit ${limit}. ${level}.">
        <path class="track" d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke-width="16" stroke-linecap="round"/>
        <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="${color}" stroke-width="16" stroke-linecap="round" pathLength="100" stroke-dasharray="${risk} 100" class="gauge-fill"/>
        <line class="needle-limit" x1="${lx1.toFixed(1)}" y1="${ly1.toFixed(1)}" x2="${lx2.toFixed(1)}" y2="${ly2.toFixed(1)}" stroke-width="2.5" stroke-linecap="round"/>
        <text x="20" y="116" text-anchor="middle">0</text><text x="180" y="116" text-anchor="middle">100</text>
        <text class="gv" x="100" y="92" text-anchor="middle">${risk}</text>
      </svg>
      <p class="gauge-level"><strong>${esc(level)}</strong> · approval limit ${limit}</p>
    </div>`;

  // ---------- Human review banner
  const a = r.appeal;
  if (a) {
    const banner = $('review-banner');
    const states = {
      open: ['', 'clock', 'A credit officer is reviewing your application', `Ticket ${a.ticket}, sent ${CL.dateTime(a.created_at)}. We answer within 48 hours.`],
      overturned: ['', 'check', 'Decision changed after human review', a.reviewer_note || ''],
      upheld: [' warn', 'info', 'A credit officer confirmed the decision', a.reviewer_note || '']
    }[a.status];
    banner.className = 'banner' + states[0];
    banner.innerHTML = `${CL.ico(states[1])}<span><strong>${esc(states[2])}</strong>${esc(states[3])}</span>`;
  }

  // ---------- Reasons (direction in words, not only color)
  $('reasons').innerHTML = r.model.top_reasons.map((x) => {
    const raises = (x.direction || 'raises') === 'raises';
    const impact = x.impact[0].toUpperCase() + x.impact.slice(1);
    return `<li>
      <div class="reason-top"><strong>${esc(x.label)}</strong>
        <span class="chip ${raises ? 'chip-orange' : 'chip-teal'}">${CL.ico(raises ? 'up' : 'down')}${raises ? 'Raises' : 'Lowers'} risk · ${esc(impact)}</span></div>
      <div class="bar"><div style="width:${Math.round((x.weight ?? 0.5) * 100)}%;background:${raises ? 'var(--warn)' : 'var(--brand)'}"></div></div>
    </li>`;
  }).join('');

  // ---------- Explanation (escape first, then highlight the first name)
  function renderExplanation(view) {
    const lang = view === 'en' ? 'en' : r.llm.language;
    const textValue = view === 'en' ? r.llm.explanation_en : r.llm.explanation;
    const p = $('explanation');
    p.setAttribute('lang', lang);
    p.setAttribute('dir', RTL.includes(lang) ? 'rtl' : 'ltr');
    p.style.fontFamily = lang === 'hi' ? "'Noto Sans Devanagari', var(--font)" : '';
    const safe = esc(textValue);
    const name = esc(r.display_name);
    p.innerHTML = name ? safe.split(name).join(`<mark class="name">${name}</mark>`) : safe;
  }
  if (r.llm.language !== 'en' && r.llm.explanation_en) {
    $('lang-tabs').classList.remove('hidden');
    $('tab-local').textContent = LANG_NAMES[r.llm.language] || r.llm.language;
    document.querySelectorAll('[data-view]').forEach((b) => b.addEventListener('click', () => {
      document.querySelectorAll('[data-view]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      renderExplanation(b.dataset.view);
    }));
  }
  renderExplanation('local');
  $('engine-note').innerHTML = `Written by ${esc(r.llm.engine || 'IBM Granite')} on our LinuxONE server. The AI only saw the code <code>${esc(r.token)}</code>; your name was added back at the end by the privacy gateway. <a href="privacy.html?id=${encodeURIComponent(r.application_id)}" style="font-weight:600">See what the AI saw</a>`;

  // ---------- Steps
  if (approved) $('steps-title').textContent = 'Next steps';
  const stepsRtl = RTL.includes(r.llm.language);
  $('steps').setAttribute('dir', stepsRtl ? 'rtl' : 'ltr');
  $('steps').setAttribute('lang', r.llm.language);
  if (stepsRtl) $('steps').style.fontFamily = 'var(--font-ar)';
  $('steps').innerHTML = r.llm.steps.map((s) => `<li><span>${esc(s)}</span></li>`).join('');

  // ---------- Human review
  function renderAppeal(ap) {
    $('appeal-form').classList.add('hidden');
    $('appeal-status').classList.remove('hidden');
    $('appeal-ticket').textContent = ap.ticket;
    const closed = ap.status !== 'open';
    const outcome = ap.status === 'overturned' ? 'Approved by a credit officer' : 'Decision confirmed';
    $('appeal-timeline').innerHTML = `
      <li class="done"><span class="dot">${CL.icon('check')}</span><div><strong>Request sent</strong><p>${esc(CL.dateTime(ap.created_at))}</p><p class="quote">${esc(ap.text)}</p></div></li>
      <li class="${closed ? 'done' : 'current'}"><span class="dot">${CL.icon(closed ? 'check' : 'clock')}</span><div><strong>Reviewed by a credit officer</strong><p>${closed ? 'Done' : 'In progress · answer within 48 hours'}</p></div></li>
      <li class="${closed ? 'done' : ''}"><span class="dot">${CL.icon(closed ? (ap.status === 'overturned' ? 'check' : 'info') : 'file')}</span><div><strong>${closed ? esc(outcome) : 'Final answer'}</strong>
        <p>${closed ? esc(CL.dateTime(ap.resolved_at)) : 'You will see it here'}</p>${closed && ap.reviewer_note ? `<p class="quote">${esc(ap.reviewer_note)}</p>` : ''}</div></li>`;
  }

  if (a) renderAppeal(a);
  else if (approved) $('appeal-card').classList.add('hidden');
  else {
    const ta = $('appeal-text');
    ta.value = r.llm.appeal_draft;
    const count = () => { $('appeal-count').textContent = `${ta.value.length} / 4000 characters`; };
    ta.addEventListener('input', count); count();
    $('appeal-btn').addEventListener('click', async () => {
      const btn = $('appeal-btn');
      if (ta.value.trim().length < 10) { CL.fieldError(ta, 'Please write at least 10 characters.'); return ta.focus(); }
      if (ta.value.includes('[Add your reason here')) { CL.fieldError(ta, 'Replace the line in [brackets] with your reason.'); return ta.focus(); }
      CL.clearFieldError(ta);
      CL.busy(btn, true);
      try {
        const res = await API.appeal(r.application_id, ta.value);
        CL.toast(`Sent. Ticket ${res.ticket}: a ${res.reviewer.toLowerCase()} will answer within ${res.eta_hours} hours.`);
        const ap = { ticket: res.ticket, status: 'open', created_at: new Date().toISOString(), text: ta.value };
        renderAppeal(ap);
        const banner = $('review-banner');
        banner.className = 'banner';
        banner.innerHTML = `${CL.ico('clock')}<span><strong>A credit officer is reviewing your application</strong>Ticket ${esc(res.ticket)}. We answer within 48 hours.</span>`;
      } catch (e) {
        CL.toast(e.message, 'warn');
        CL.busy(btn, false);
      }
    });
  }
})();
