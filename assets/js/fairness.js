// ClearLoan — fairness dashboard (staff only)
(async function () {
  const session = await CL.guard('fairness.html', ['staff']);
  if (!session) return;

  const $ = (id) => document.getElementById(id);
  const esc = CL.esc;

  // `note` and `extra` are HTML: build them from numbers or escaped text only
  function kpi(icon, label, value, note, extra) {
    return `<div class="kpi reveal"><p class="k-label">${CL.ico(icon)}${esc(label)}</p><p class="k-value">${esc(value)}${extra || ''}</p><p class="k-note">${note}</p></div>`;
  }
  function delta(before, after, lowerIsBetter, unit) {
    const d = after - before;
    const good = lowerIsBetter ? d <= 0 : d >= 0;
    const txt = (d > 0 ? '+' : '') + (Number.isInteger(d) ? d : d.toFixed(2)) + (unit || '');
    return `<span class="delta ${good ? 'good' : 'bad'}">${CL.icon(d >= 0 ? 'up' : 'down').replace('<svg', '<svg width="12" height="12"')}${esc(txt)}</span>`;
  }

  function renderGroups(d, group) {
    const m = d.metrics;
    document.querySelectorAll('[data-group]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.group === group)));
    $('group-title').textContent = group === 'sex' ? 'Approval rate by sex' : 'Approval rate by age band';
    $('group-note').textContent = group === 'sex'
      ? `Gap between men and women: ${m.gap_sex_before} points before, ${m.gap_sex_after} points after.`
      : `Reference fairness ratio (lowest group / highest group): ${m.ratio_age_before.toFixed(2)} before, ${m.ratio_age_after.toFixed(2)} after.`;
    $('groups').innerHTML = d.groups[group].map((g) => `
      <div class="group-row">
        <div style="font-weight:600">${esc(g.label)}</div>
        <div class="bars" role="img" aria-label="${esc(g.label)}: ${esc(g.before)}% before, ${esc(g.after)}% after">
          <div class="b"><div class="t"><div style="width:${Number(g.before)}%;background:var(--before)"></div></div><span class="muted">${esc(g.before)}%</span></div>
          <div class="b"><div class="t"><div class="after-bar" style="width:${Number(g.after)}%;background:var(--after)"></div></div><span style="font-weight:600">${esc(g.after)}%</span></div>
        </div>
      </div>`).join('');
  }

  function miniBars(groups) {
    if (!groups.length) return '<p class="muted small">No decisions yet.</p>';
    return groups.map((g) => `
      <div class="mb-row${g.enough === false ? ' few' : ''}" role="img" aria-label="${esc(g.label)}: ${esc(g.rate)}% approved out of ${esc(g.n)}${g.enough === false ? ', too few to judge' : ''}">
        <span>${esc(g.label)}</span><div class="t"><div style="width:${Number(g.rate)}%"></div></div><span><strong style="color:var(--text)">${esc(g.rate)}%</strong> · n=${esc(g.n)}</span>
      </div>`).join('') + (groups.some((g) => g.enough === false) ? '<p class="xsmall muted">Faded rows have too few decisions to judge; they are left out of the gap and ratio.</p>' : '');
  }

  function renderLive(l, target) {
    const na = '—';
    const ratioOk = l.ratio_age != null && l.ratio_age >= target;
    $('live-kpis').innerHTML =
      kpi('file', 'Decisions made', CL.fmt(l.applications), `${l.first_time_share ?? 0}% scored by the first-time borrower model`) +
      kpi('check', 'Approval rate', l.approval_rate != null ? l.approval_rate + '%' : na, 'model decisions, before human review') +
      kpi('scale', 'Live fairness ratio · age', l.ratio_age != null ? l.ratio_age.toFixed(2) : na, `target ${target.toFixed(2)} or more`,
        l.ratio_age != null ? `<span class="chip ${ratioOk ? 'chip-teal' : 'chip-orange'}">${CL.ico(ratioOk ? 'check' : 'alert')}${ratioOk ? 'Passes' : 'Watch'}</span>` : '') +
      kpi('inbox', 'Human reviews', CL.fmt(l.appeals.open + l.appeals.upheld + l.appeals.overturned),
        `${l.appeals.open} open · ${l.appeals.overturned} overturned · ${l.appeals.upheld} upheld · <a href="reviews.html">Open queue</a>`);
    $('live-sex-note').textContent = l.gap_sex != null ? `Gap between men and women: ${l.gap_sex} points.` : 'Not enough data for both groups yet.';
    $('live-age-note').textContent = l.ratio_age != null ? `Lowest band ÷ highest band: ${l.ratio_age.toFixed(2)}.` : 'Not enough data yet.';
    $('live-sex').innerHTML = miniBars(l.groups.sex);
    $('live-age').innerHTML = miniBars(l.groups.age);
    $('live-warning').classList.toggle('hidden', !l.small_sample);
  }

  let d;
  try { d = await API.fairness(); } catch (e) {
    $('kpis').innerHTML = `<div class="card error-text">${CL.ico('alert')}<span>${esc(e.message)}</span></div>`;
    return;
  }
  const m = d.metrics;
  const passes = m.ratio_age_after >= m.ratio_target;
  $('kpis').innerHTML =
    kpi('users', 'Reference approval gap · men vs women', `${m.gap_sex_after} pts`, `${delta(m.gap_sex_before, m.gap_sex_after, true, ' pts')} was ${esc(m.gap_sex_before)} pts before mitigation`) +
    kpi('scale', 'Fairness ratio · age groups', m.ratio_age_after.toFixed(2), `${delta(m.ratio_age_before, m.ratio_age_after, false)} target ${esc(m.ratio_target.toFixed(2))} or more`,
      `<span class="chip ${passes ? 'chip-teal' : 'chip-orange'}">${CL.ico(passes ? 'check' : 'alert')}${passes ? 'Passes' : 'Below target'}</span>`) +
    kpi('chart', 'Reference AUC (unvalidated)', m.auc_after.toFixed(2), `${delta(m.auc_before, m.auc_after, false)} small cost for fairness`) +
    kpi('clock', 'Reference latency (unvalidated)', `${m.latency_ms} ms`, `average over ${esc(CL.fmt(m.latency_samples))} test applications`);

  let group = 'sex';
  renderGroups(d, group);
  document.querySelectorAll('[data-group]').forEach((b) => b.addEventListener('click', () => { group = b.dataset.group; renderGroups(d, group); }));

  $('models').innerHTML = d.models.map((x) => `
    <tr><td><strong>${esc(x.name)}</strong><br><span class="small muted">${esc(x.note)}</span></td>
    <td class="num">${esc(x.auc.toFixed(2))}</td><td class="num">${esc(x.approval_rate)}%</td><td class="num">${esc(x.gap_sex)} pts</td></tr>`).join('');

  $('method').innerHTML = [['Tool', d.method.tool], ['Mitigation', d.method.mitigation], ['Groups checked', d.method.groups],
    ['Fairness ratio', `Lowest approval rate ÷ highest. ${m.ratio_target.toFixed(2)} or more passes.`]]
    .map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('');
  $('dataset').textContent = `Data: ${d.dataset}. One dataset only: results need wider validation before real use.`;

  if (d.live) renderLive(d.live, m.ratio_target);
})();
