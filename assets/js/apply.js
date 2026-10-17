// ClearLoan — application form
(async function () {
  const session = await CL.guard('apply.html', ['applicant']);
  if (!session) return;
  CL.stepper(1, null);

  const $ = (id) => document.getElementById(id);
  const esc = CL.esc;
  let language = 'en';

  // 6 months of repayment status (UCI PAY_ columns: 0 = on time, 1..9 = months late)
  const MONTHS = Array.from({ length: 6 }, (_, i) => {
    const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1 - i);
    return d.toLocaleDateString('en-GB', { month: 'short' });
  });
  $('history-fields').innerHTML = MONTHS.map((m, i) => `
    <div class="field"><label for="pay${i}">${esc(m)}</label>
      <select id="pay${i}" disabled>
        <option value="0">On time</option><option value="1">1 month late</option><option value="2">2+ months late</option>
      </select></div>`).join('');

  function syncHistory() {
    const has = $('h-yes').checked;
    MONTHS.forEach((_, i) => { $('pay' + i).disabled = !has; });
    $('history-hint').textContent = has ? '' : '(skipped for first-time borrowers)';
  }
  document.querySelectorAll('input[name="history"]').forEach((r) => r.addEventListener('change', syncHistory));
  syncHistory();

  document.querySelectorAll('[data-lang]').forEach((b) => {
    b.addEventListener('click', () => {
      language = b.dataset.lang;
      document.querySelectorAll('[data-lang]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    });
  });

  // ---------- Quick check: live, local, indicative
  function quickCheck() {
    const bill = Number($('avg_bill').value), pay = Number($('avg_payment').value), loan = Number($('loan_amount').value);
    if (!$('avg_bill').value || !$('avg_payment').value || bill <= 0) { $('qc').classList.add('hidden'); $('qc-empty').classList.remove('hidden'); return; }
    $('qc').classList.remove('hidden'); $('qc-empty').classList.add('hidden');
    const pct = Math.round((pay / bill) * 100);
    $('qc-ratio').textContent = pct + '%';
    $('qc-fill').style.width = Math.min(100, pct) + '%';
    $('qc-fill').style.background = pct >= 35 ? 'var(--mint)' : '#FDBA74';
    $('qc-text').textContent = pct >= 35
      ? 'Good: your payments cover a healthy share of your bills.'
      : `Below 35%. Paying about ${CL.money(Math.ceil(bill * 0.35 / 50) * 50)} a month would help a lot.`;
    $('qc-months').textContent = loan > 0 ? `≈ ${Math.round(loan / Math.max(bill, 500))} months of bills` : '—';
  }
  ['avg_bill', 'avg_payment', 'loan_amount'].forEach((id) => $(id).addEventListener('input', quickCheck));

  // ---------- Previous applications
  API.applications().then((items) => {
    if (!items || !items.length) return;
    $('history-card').classList.remove('hidden');
    $('history-list').innerHTML = items.slice(0, 5).map((a) => {
      const ok = a.final_decision === 'approved';
      return `<li><a href="decision.html?id=${encodeURIComponent(a.application_id)}">
        <span><strong>${esc(CL.money(a.loan_amount))}</strong><span class="l-id">${esc(a.application_id)} · ${esc(CL.date(a.created_at))}</span></span>
        <span class="chip ${ok ? 'chip-teal' : 'chip-orange'}">${ok ? 'Approved' : a.appeal_status === 'open' ? 'In review' : 'Not approved'}</span></a></li>`;
    }).join('');
  }).catch(() => {});

  // ---------- Validation (errors under each field, focus on the first one)
  const RULES = [
    ['name', (v) => v.length >= 2 || 'Please enter your full name.'],
    ['id_number', (v) => v.length >= 5 || 'Please enter your Emirates ID or passport number.'],
    ['phone', (v) => v.replace(/\D/g, '').length >= 7 || 'Please enter a phone number with at least 7 digits.'],
    ['email', (v) => /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(v) || 'Please enter a valid email, like name@example.com.'],
    ['loan_amount', (v) => (Number(v) >= 1000 && Number(v) <= 5000000) || 'The loan must be between AED 1,000 and AED 5,000,000.'],
    ['avg_bill', (v) => (v !== '' && Number(v) >= 0) || 'Please enter your average monthly bills (0 if none).'],
    ['avg_payment', (v) => (v !== '' && Number(v) >= 0) || 'Please enter your average monthly payments (0 if none).'],
    ['age', (v) => (Number(v) >= 18 && Number(v) <= 100) || 'You must be 18 or older.']
  ];
  RULES.forEach(([id]) => $(id).addEventListener('blur', () => { if ($(id).getAttribute('aria-invalid')) validateOne(id); }));
  function validateOne(id) {
    const rule = RULES.find((r) => r[0] === id)[1];
    const ok = rule($(id).value.trim());
    if (ok === true) { CL.clearFieldError($(id)); return true; }
    CL.fieldError($(id), ok);
    return false;
  }

  function collect() {
    $('form-error').classList.add('hidden');
    const bad = RULES.map(([id]) => id).filter((id) => !validateOne(id));
    if (!$('consent').checked) {
      $('form-error').innerHTML = CL.ico('alert') + '<span>Please accept how we use your data.</span>';
      $('form-error').classList.remove('hidden');
      if (!bad.length) { $('consent').focus(); return null; }
    }
    if (bad.length) { $(bad[0]).focus(); return null; }
    if (!$('consent').checked) return null;
    const num = (id) => Number($(id).value);
    const has = $('h-yes').checked;
    return {
      identity: { name: $('name').value.trim(), id_number: $('id_number').value.trim(), phone: $('phone').value.trim(), email: $('email').value.trim() },
      financial: {
        loan_amount: num('loan_amount'), avg_bill: num('avg_bill'), avg_payment: num('avg_payment'), age: num('age'),
        education: $('education').value, marriage: $('marriage').value,
        credit_history: has, pay_history: has ? MONTHS.map((_, i) => Number($('pay' + i).value)) : []
      },
      audit: { sex: $('sex').value },
      language
    };
  }

  $('apply-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = collect();
    if (!body) return;
    const btn = $('submit-btn');
    CL.busy(btn, true);
    try {
      const result = await API.apply(body);
      window.location.href = 'decision.html?id=' + encodeURIComponent(result.application_id);
    } catch (err) {
      if (err.field && $(err.field)) { CL.fieldError($(err.field), err.message); $(err.field).focus(); }
      else { $('form-error').innerHTML = CL.ico('alert') + `<span>${esc(err.message || 'Something went wrong. Please try again.')}</span>`; $('form-error').classList.remove('hidden'); }
      CL.busy(btn, false);
    }
  });
})();
