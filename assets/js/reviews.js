// ClearLoan — human review queue (staff only)
(async function () {
  const session = await CL.guard('reviews.html', ['staff']);
  if (!session) return;

  const $ = (id) => document.getElementById(id);
  const esc = CL.esc;
  let items = [];
  let filter = 'open';

  const STATUS = {
    open: ['chip-blue', 'clock', 'Open'],
    overturned: ['chip-teal', 'check', 'Overturned · approved'],
    upheld: ['chip-gray', 'info', 'Upheld']
  };

  function card(x) {
    const [cls, ic, label] = STATUS[x.status];
    const f = x.financial;
    const pct = f.avg_bill ? Math.round((f.avg_payment / f.avg_bill) * 100) : 100;
    const reasons = x.model.top_reasons.slice(0, 3).map((r) =>
      `<li class="small"><span class="chip ${r.direction === 'lowers' ? 'chip-teal' : 'chip-orange'}" style="margin-right:6px">${r.direction === 'lowers' ? '−' : '+'}</span>${esc(r.label.replace(/^Your (\w)/, (_, c) => c.toUpperCase()))}</li>`).join('');
    const open = x.status === 'open';
    return `
      <article class="card ticket reveal" data-ticket="${esc(x.ticket)}">
        <div class="ticket-head">
          <div>
            <h2 class="mono" style="font-size:17px">${esc(x.ticket)}</h2>
            <div class="ticket-meta" style="margin-top:6px">
              <span>Application <a class="mono" href="privacy.html?id=${encodeURIComponent(x.application_id)}">${esc(x.application_id)}</a></span>
              <span class="mono">${esc(x.token)}</span>
              <span>Requested ${esc(CL.dateTime(x.created_at))}</span>
            </div>
          </div>
          <span class="chip ${cls}">${CL.ico(ic)}${esc(label)}</span>
        </div>
        <div class="ticket-grid">
          <div>
            <p class="label">Applicant's message</p>
            <p class="quote" style="margin-top:0">${esc(x.text)}</p>
          </div>
          <div>
            <p class="label">Model decision</p>
            <div class="ticket-meta" style="margin-bottom:10px">
              <span>Risk <b>${esc(x.model.risk_score)}</b>/100 (limit ${esc(x.model.limit)})</span>
              <span>Loan <b>${esc(CL.money(f.loan_amount))}</b></span>
              <span>Payments cover <b>${pct}%</b> of bills</span>
              <span>${esc(x.model_used.replace(/_/g, ' '))}</span>
            </div>
            <ul class="stack-sm" style="list-style:none;margin:0;padding:0">${reasons}</ul>
          </div>
        </div>
        ${open ? `
        <div>
          <label for="note-${esc(x.ticket)}">Message to the applicant</label>
          <textarea id="note-${esc(x.ticket)}" style="min-height:90px" maxlength="1000" placeholder="Explain the outcome in plain words, e.g. which documents you checked."></textarea>
          <div class="actions" style="margin-top:12px">
            <button type="button" class="btn btn-primary btn-sm" data-outcome="overturned">${CL.ico('check')}Approve the loan</button>
            <button type="button" class="btn btn-warn btn-sm" data-outcome="upheld">${CL.ico('x')}Keep the decision</button>
            <span class="xsmall muted">The applicant sees your message on their decision page.</span>
          </div>
        </div>` : `
        <div class="note">${CL.ico(x.status === 'overturned' ? 'check' : 'info')}<span><strong style="color:var(--text)">${x.status === 'overturned' ? 'Approved by a credit officer' : 'Decision confirmed'}</strong> · ${esc(CL.dateTime(x.resolved_at))}<br>${esc(x.reviewer_note || '')}</span></div>`}
      </article>`;
  }

  function render() {
    const open = items.filter((x) => x.status === 'open');
    const closed = items.filter((x) => x.status !== 'open');
    $('n-open').textContent = open.length;
    $('n-closed').textContent = closed.length;
    const nav = document.getElementById('nav-reviews');
    if (nav) { nav.textContent = open.length; nav.classList.toggle('hidden', !open.length); }
    const shown = filter === 'open' ? open : closed;
    $('list').innerHTML = shown.length ? shown.map(card).join('') : `
      <div class="card empty-state">
        <span class="tile-icon">${CL.ico(filter === 'open' ? 'check' : 'inbox')}</span>
        <h2>${filter === 'open' ? 'No open reviews' : 'No closed reviews yet'}</h2>
        <p>${filter === 'open' ? 'Every request has an answer. Nice work.' : 'Closed reviews will appear here.'}</p>
      </div>`;
    $('list').querySelectorAll('[data-outcome]').forEach((b) => b.addEventListener('click', () => resolve(b)));
  }

  async function resolve(btn) {
    const art = btn.closest('[data-ticket]');
    const ticket = art.dataset.ticket;
    const note = art.querySelector('textarea');
    if (note.value.trim().length < 5) { CL.fieldError(note, 'Please explain the outcome to the applicant.'); return note.focus(); }
    CL.clearFieldError(note);
    art.querySelectorAll('[data-outcome]').forEach((b) => { b.disabled = true; });
    CL.busy(btn, true);
    try {
      await API.resolveReview(ticket, btn.dataset.outcome, note.value.trim());
      CL.toast(`${ticket} closed: ${btn.dataset.outcome === 'overturned' ? 'loan approved' : 'decision kept'}.`);
      items = await API.reviews();
      render();
    } catch (e) {
      CL.toast(e.message, 'warn');
      art.querySelectorAll('[data-outcome]').forEach((b) => { b.disabled = false; });
      CL.busy(btn, false);
    }
  }

  document.querySelectorAll('[data-filter]').forEach((b) => b.addEventListener('click', () => {
    filter = b.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    render();
  }));

  try {
    items = await API.reviews();
    $('loading').classList.add('hidden');
    render();
  } catch (e) {
    $('loading').classList.add('hidden');
    $('list').innerHTML = `<div class="card error-text">${CL.ico('alert')}<span>${esc(e.message)}</span></div>`;
  }
})();
