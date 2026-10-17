// ClearLoan — mock back-end (fake data, used only when index.html is opened as a file)
// It follows the same JSON contract as the real API (see README.md). The real logic lives in backend/.
(function () {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const randHex = (n) => Array.from({ length: n }, () => '0123456789ABCDEF'[Math.floor(Math.random() * 16)]).join('');
  const fmt = (n) => Number(n).toLocaleString('en-US');
  const LIMIT = () => window.CL_CONFIG.APPROVAL_LIMIT;

  const db = {
    load() { try { return JSON.parse(sessionStorage.getItem('cl_mock') || '{"apps":{}}'); } catch (e) { return { apps: {} }; } },
    save(s) { try { sessionStorage.setItem('cl_mock', JSON.stringify(s)); } catch (e) { /* ignore */ } }
  };
  const sess = () => { try { return JSON.parse(sessionStorage.getItem('cl_session') || 'null'); } catch (e) { return null; } };

  function maskIdentity(id) {
    const parts = (id.name || '').trim().split(/\s+/);
    return {
      first_name: parts[0] || 'Applicant',
      name: parts[0] + (parts[1] ? ' ' + parts[1][0] + '•••' : ''),
      id_number: (id.id_number || '').slice(0, 4) + '••••-•••••••-•',
      phone: (id.phone || '').slice(0, 4) + ' •• ••• ••••',
      email: (id.email || '').slice(0, 1) + '••••@•••••.com'
    };
  }

  function score(f) {
    const ratio = f.avg_bill > 0 ? f.avg_payment / f.avg_bill : 1;
    let risk = 100 - ratio * 140;
    if (f.loan_amount > 40000) risk += 10;
    if (!f.credit_history) risk += 8;
    if (f.credit_history && f.pay_history.some((p) => p > 0)) risk += 12;
    risk = Math.max(3, Math.min(97, Math.round(risk)));
    const reasons = [
      { feature: 'payment_ratio', value: Number(ratio.toFixed(2)), impact: ratio < 0.3 ? 'high' : 'low', direction: ratio < 0.35 ? 'raises' : 'lowers',
        label: `Your monthly payments cover ${Math.round(ratio * 100)}% of your monthly bills`, weight: ratio < 0.3 ? 0.9 : 0.3 },
      { feature: 'loan_amount', value: f.loan_amount, impact: f.loan_amount > 40000 ? 'medium' : 'low', direction: f.loan_amount > 40000 ? 'raises' : 'lowers',
        label: `AED ${fmt(f.loan_amount)} requested compared with your bill level`, weight: f.loan_amount > 40000 ? 0.58 : 0.2 },
      { feature: 'credit_history', value: f.credit_history ? 'yes' : 'none', impact: f.credit_history ? 'low' : 'medium', direction: f.credit_history ? 'lowers' : 'raises',
        label: f.credit_history ? 'Your repayment record over 6 months' : 'No credit history yet, so the model is less sure', weight: f.credit_history ? 0.25 : 0.42 }
    ].sort((a, b) => b.weight - a.weight);
    return { decision: risk <= LIMIT() ? 'approved' : 'not_approved', risk_score: risk, top_reasons: reasons, version: 'mock', limit: LIMIT() };
  }

  function explain(lang, approved, f, name) {
    const amount = fmt(f.loan_amount);
    const T = {
      en: approved
        ? `Hello ${name}, good news: your loan of AED ${amount} is approved. Your monthly payments and your bills are in a healthy balance. Please keep paying on time.`
        : `Hello ${name}, thank you for applying. For now, we can't approve a loan of AED ${amount}. The main reason is that your monthly payments cover only a small part of your monthly bills. This is not a final answer: you can improve your chances, or ask a person to review your application.`,
      ar: approved
        ? `مرحباً ${name}، خبر سار: تمت الموافقة على قرضك بقيمة ${amount} درهم. دفعاتك الشهرية متوازنة مع فواتيرك.`
        : `مرحباً ${name}، شكراً لتقديم طلبك. لا يمكننا حالياً الموافقة على قرض بقيمة ${amount} درهم. هذا ليس قراراً نهائياً: يمكنك تحسين فرصك، أو طلب مراجعة من قِبل موظف.`,
      fr: approved
        ? `Bonjour ${name}, bonne nouvelle : votre prêt de ${amount} AED est accepté. Continuez à payer à temps.`
        : `Bonjour ${name}, merci pour votre demande. Pour l'instant, nous ne pouvons pas accepter un prêt de ${amount} AED. Ce n'est pas une réponse définitive : vous pouvez améliorer vos chances ou demander une révision par une personne.`
    };
    return T[lang] || T.en;
  }

  const result = (a) => Object.assign({}, a.result, { final_decision: a.final_decision, appeal: a.appeal || null });

  window.CL_MOCK = {
    async login(body) {
      await sleep(350);
      const lockUntil = Number(localStorage.getItem('cl_lock_until') || 0);
      if (Date.now() < lockUntil) return { ok: false, error: 'locked', minutes_left: Math.ceil((lockUntil - Date.now()) / 60000) };
      const okPassword = (body.password || '').length >= 8;
      const okCode = body.role !== 'staff' || /^\d{6}$/.test(body.code || '');
      if (!body.email || !okPassword || !okCode) {
        const fails = Number(localStorage.getItem('cl_fails') || 0) + 1;
        localStorage.setItem('cl_fails', String(fails));
        if (fails >= 5) { localStorage.setItem('cl_lock_until', String(Date.now() + 10 * 60000)); localStorage.setItem('cl_fails', '0'); return { ok: false, error: 'locked', minutes_left: 10 }; }
        return { ok: false, error: 'invalid', attempts_left: 5 - fails };
      }
      localStorage.setItem('cl_fails', '0');
      return { ok: true, role: body.role, display_name: body.role === 'staff' ? 'Auditor' : (body.email.split('@')[0] || 'Applicant') };
    },
    async register(body) { await sleep(350); return { ok: true, role: 'applicant', display_name: body.display_name }; },
    async logout() { return { ok: true }; },
    async me() { const s = sess(); return s ? { ok: true, role: s.role, display_name: s.display_name } : null; },

    async apply(body) {
      const t0 = performance.now();
      await sleep(600);
      const suffix = randHex(6);
      const token = 'Applicant_' + suffix, id = 'CL-' + suffix;
      const masked = maskIdentity(body.identity);
      const f = body.financial;
      const model = score(f);
      const approved = model.decision === 'approved';
      const lang = body.language || 'en';
      const t = new Date();
      const prompt = `SYSTEM  You explain loan decisions in simple, kind words. Never invent facts.\nUSER    ${token} was ${approved ? 'approved' : 'not approved'} (risk ${model.risk_score}/100, limit ${LIMIT()}).\n        Top reasons: ${model.top_reasons.map((r) => `${r.feature} = ${r.value} (${r.impact})`).join('; ')}.\n        Write a short explanation in ${lang} and 3 steps to improve.`;
      const r = {
        application_id: id, token, created_at: t.toISOString(), latency_ms: Math.round(performance.now() - t0),
        model_used: f.credit_history ? 'full_history' : 'first_time_borrower', display_name: masked.first_name,
        request: { loan_amount: f.loan_amount, language: lang }, model,
        llm: {
          explanation: explain(lang, approved, f, masked.first_name),
          explanation_en: lang === 'en' ? null : explain('en', approved, f, masked.first_name),
          steps: approved
            ? ['Keep paying your bills on time.', 'Set up an automatic monthly payment.', 'Contact us if your income changes.']
            : ['Ask for a smaller amount. Around AED 30,000 fits your current bills better.', 'Pay more of your monthly bills. Paying more than 35% of them makes a big difference.',
               f.credit_history ? 'Avoid late payments for the next 3 months.' : 'Come back after 3 months of on-time payments. We can then use the full model.'],
          appeal_draft: `Dear ClearLoan team,\nI would like a person to review my application ${id}.\n[Add your reason here, for example a new job or a higher salary.]\nI can share documents to support this.\nThank you,\n${masked.first_name}`,
          language: lang, engine: 'Sample data (mock)'
        }
      };
      const at = (ms) => new Date(t.getTime() + ms).toISOString();
      const s = db.load();
      s.apps[id] = {
        result: r, final_decision: model.decision, appeal: null, masked, sex: body.audit.sex, financial: f, prompt,
        log: [
          { ts: at(0), step: 'Application received', component: 'Web app', details: 'Form submitted over HTTPS' },
          { ts: at(6), step: 'Identity hidden', component: 'Privacy gateway', details: `4 fields encrypted → ${token}` },
          { ts: at(61), step: 'Risk scored', component: `Mock model · ${r.model_used.replace(/_/g, ' ')}`, details: `${model.risk_score}/100 · ${approved ? 'approved' : 'not approved'}` },
          { ts: at(315), step: 'Explanation written', component: 'Sample data (mock)', details: 'Prompt scan: 0 personal fields' },
          { ts: at(331), step: 'Name restored', component: 'Privacy gateway', details: 'First name shown to the applicant only' }
        ]
      };
      db.save(s);
      return result(s.apps[id]);
    },

    async applications() {
      await sleep(150);
      return Object.values(db.load().apps).reverse().map((a) => ({
        application_id: a.result.application_id, token: a.result.token, created_at: a.result.created_at, loan_amount: a.financial.loan_amount,
        risk_score: a.result.model.risk_score, decision: a.result.model.decision, final_decision: a.final_decision,
        model_used: a.result.model_used, appeal_status: a.appeal ? a.appeal.status : null
      }));
    },
    async application(id) {
      await sleep(200);
      const a = db.load().apps[id];
      if (!a) throw new ApiError('not_found', 'No application found with this ID.', 404);
      return result(a);
    },

    async privacy(id) {
      await sleep(250);
      const a = db.load().apps[id];
      if (!a) return null;
      const f = a.financial;
      const staff = (sess() || {}).role === 'staff';
      return {
        application_id: id, token: a.result.token,
        identity_masked: staff ? { name: null, id_number: a.masked.id_number, phone: null, email: null } : a.masked,
        audit_only: { sex: a.sex },
        model_input: { applicant: a.result.token, loan_amount: f.loan_amount, age: f.age, education: f.education, marriage: f.marriage,
          avg_bill: f.avg_bill, avg_payment: f.avg_payment, credit_history: f.credit_history, pay_history: f.credit_history ? f.pay_history : null },
        prompt: a.prompt, pii_scan: { personal_fields_found: 0 }, engine: 'Sample data (mock)', audit_log: a.log
      };
    },

    async appeal(id, text) {
      await sleep(350);
      const s = db.load();
      const ticket = 'RV-' + randHex(5);
      s.apps[id].appeal = { ticket, status: 'open', created_at: new Date().toISOString(), text, reviewer_note: null, resolved_at: null };
      s.apps[id].log.push({ ts: new Date().toISOString(), step: 'Human review requested', component: 'Applicant', details: `Ticket ${ticket}` });
      db.save(s);
      return { ok: true, ticket, reviewer: 'Credit officer', eta_hours: 48, status: 'open' };
    },

    async reviews() {
      await sleep(200);
      return Object.values(db.load().apps).filter((a) => a.appeal).map((a) => Object.assign({}, a.appeal, {
        text: a.appeal.text.split(a.masked.first_name).join('[name]'),
        application_id: a.result.application_id, token: a.result.token, model: a.result.model, final_decision: a.final_decision,
        model_used: a.result.model_used, financial: a.financial
      }));
    },
    async resolveReview(ticket, outcome, note) {
      await sleep(300);
      const s = db.load();
      const a = Object.values(s.apps).find((x) => x.appeal && x.appeal.ticket === ticket);
      Object.assign(a.appeal, { status: outcome, reviewer_note: note, resolved_at: new Date().toISOString() });
      if (outcome === 'overturned') a.final_decision = 'approved';
      db.save(s);
      return { ok: true, ticket, status: outcome };
    },

    async fairness() {
      await sleep(300);
      const apps = Object.values(db.load().apps);
      const approved = apps.filter((a) => a.result.model.decision === 'approved').length;
      return {
        model: 'full_history',
        metrics: { gap_sex_before: 9, gap_sex_after: 2, ratio_age_before: 0.74, ratio_age_after: 0.90, ratio_target: 0.80, auc_before: 0.78, auc_after: 0.77, latency_ms: 38, latency_samples: 1000 },
        groups: {
          sex: [{ label: 'Men', before: 64, after: 66 }, { label: 'Women', before: 73, after: 68 }],
          age: [{ label: '21 to 25', before: 52, after: 61 }, { label: '26 to 35', before: 70, after: 68 }, { label: '36 to 50', before: 69, after: 67 }, { label: '51 and over', before: 58, after: 63 }]
        },
        models: [
          { name: 'A · Full history', note: 'people with a credit record', auc: 0.77, approval_rate: 67, gap_sex: 2 },
          { name: 'B · First-time borrower', note: 'no history needed', auc: 0.66, approval_rate: 59, gap_sex: 3 }
        ],
        method: { tool: 'AI Fairness 360 (IBM, open source)', mitigation: 'Reweighing the training data', groups: 'Sex, age bands' },
        dataset: 'UCI “Default of Credit Card Clients”, 30,000 records',
        live: {
          applications: apps.length, approval_rate: apps.length ? Math.round(100 * approved / apps.length) : null, gap_sex: null, ratio_age: null,
          avg_latency_ms: null, first_time_share: null, groups: { sex: [], age: [] },
          appeals: { open: apps.filter((a) => a.appeal && a.appeal.status === 'open').length, upheld: 0, overturned: 0 }, small_sample: true
        }
      };
    }
  };
})();
