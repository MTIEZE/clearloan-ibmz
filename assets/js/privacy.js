// ClearLoan — privacy proof (applicant) / audit log (staff)
(async function () {
  const session = await CL.guard('privacy.html', ['applicant', 'staff']);
  if (!session) return;

  const $ = (id) => document.getElementById(id);
  const esc = CL.esc;
  const isStaff = session.role === 'staff';

  const SENT = `<span class="chip chip-blue">${CL.ico('arrow')}Sent</span>`;
  const HIDDEN = `<span class="chip chip-teal">${CL.ico('lock')}Hidden</span>`;
  const AUDIT_ONLY = `<span class="chip chip-orange">${CL.ico('scale')}Fairness audit only</span>`;
  const show = (id, on) => $(id).classList.toggle('hidden', !on);

  function render(d) {
    show('loading', false); show('empty', false); show('content', true);
    $('flow-app').textContent = d.application_id;
    $('flow-token').textContent = d.token;

    const m = d.model_input;
    const id = d.identity_masked;
    const dash = '— not shown to staff';
    const rows = [
      ['Full name', id.name ?? dash, HIDDEN, true],
      ['Emirates ID', id.id_number, HIDDEN, true],
      ['Phone', id.phone ?? dash, HIDDEN, true],
      ['Email', id.email ?? dash, HIDDEN, true],
      ['Sex', d.audit_only.sex, AUDIT_ONLY, false],
      ['Loan amount', CL.money(m.loan_amount), SENT, false],
      ['Monthly bills / payments', `${CL.money(m.avg_bill)} / ${CL.fmt(m.avg_payment)}`, SENT, false],
      ['Age, education, status', `${m.age}, ${m.education.replace(/_/g, ' ')}, ${m.marriage}`, SENT, false],
      ['Credit history', m.credit_history ? 'Yes (6 months)' : 'None (first loan)', SENT, false]
    ];
    $('fields-table').innerHTML = rows.map(([f, v, chip, mono]) =>
      `<tr><td>${esc(f)}</td><td class="${mono ? 'mono' : ''}">${esc(v)}</td><td>${chip}</td></tr>`).join('');

    $('model-input').textContent = JSON.stringify(m, null, 2);
    const n = d.pii_scan.personal_fields_found;
    $('scan').className = n ? 'error-text' : 'success';
    $('scan').innerHTML = `${CL.ico(n ? 'alert' : 'check')}<span><strong>Automatic scan:</strong> ${esc(n)} personal fields found in the prompt${n ? ' — the LLM call was blocked.' : ' before sending.'}</span>`;
    $('prompt-chip').innerHTML = `${CL.ico('shield')}${esc(n)} personal fields`;
    // Escape first, then highlight the token
    $('prompt').innerHTML = esc(d.prompt).split(esc(d.token)).join(`<span class="tok">${esc(d.token)}</span>`);
    $('prompt-note').innerHTML = `Engine: <strong>${esc(d.engine || 'IBM Granite')}</strong>. Answer received → the gateway replaces <code>${esc(d.token)}</code> with the applicant's first name, then shows it to the applicant only.`;
    $('audit').innerHTML = d.audit_log.map((x) =>
      `<tr><td class="mono">${esc(x.ts ? CL.clock(x.ts) : x.time)}</td><td><strong style="font-weight:600">${esc(x.step)}</strong></td><td>${esc(x.component)}</td><td class="muted">${esc(x.details)}</td></tr>`).join('');
  }

  async function load(appId) {
    if (!appId) { $('empty-text').textContent = isStaff ? 'Enter an application ID or pick one from the list.' : 'Submit an application first.'; show('empty', true); show('content', false); return; }
    show('loading', true); show('empty', false); show('content', false);
    try {
      const d = await API.privacy(appId);
      if (!d) throw new ApiError('not_found', `No application found for ${appId}.`, 404);
      render(d);
      if (!isStaff) CL.stepper(3, appId);
      history.replaceState(null, '', 'privacy.html?id=' + encodeURIComponent(appId));
    } catch (e) {
      show('loading', false);
      $('empty-text').textContent = e.status === 404 ? `No application found for ${appId}.` : e.message;
      show('empty', true); show('content', false);
    }
  }

  const fromUrl = CL.params.get('id');
  if (isStaff) {
    $('eyebrow').textContent = 'Bank staff · Audit log';
    $('lead').textContent = 'Check what each component received for one application. No names or contact details are shown.';
    show('staff-tools', true);
    $('stepper').remove();
    $('lookup').addEventListener('submit', (e) => { e.preventDefault(); load($('app-id').value.trim().toUpperCase()); });
    API.applications().then((items) => {
      $('recent-count').textContent = `${items.length} shown`;
      $('recent').innerHTML = items.map((a) => `
        <tr class="row-link" tabindex="0" data-id="${esc(a.application_id)}">
          <td class="mono">${esc(a.application_id)}</td><td class="mono">${esc(a.token)}</td><td>${esc(CL.date(a.created_at))}</td>
          <td class="num">${esc(a.risk_score)}</td>
          <td><span class="chip ${a.final_decision === 'approved' ? 'chip-teal' : 'chip-orange'}">${a.final_decision === 'approved' ? 'Approved' : 'Not approved'}</span></td></tr>`).join('')
        || '<tr><td colspan="5" class="muted">No applications yet.</td></tr>';
      $('recent').querySelectorAll('tr[data-id]').forEach((tr) => {
        const go = () => { $('app-id').value = tr.dataset.id; load(tr.dataset.id); $('content').scrollIntoView({ behavior: 'smooth', block: 'start' }); };
        tr.addEventListener('click', go);
        tr.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
      });
    }).catch((e) => CL.toast(e.message, 'warn'));
    if (fromUrl) { $('app-id').value = fromUrl; load(fromUrl); } else load(null);
  } else {
    CL.stepper(3, fromUrl);
    if (fromUrl) load(fromUrl);
    else {
      try {
        const items = await API.applications();
        load(items.length ? items[0].application_id : null);
      } catch (e) { $('empty-text').textContent = e.message; show('empty', true); }
    }
  }
})();
