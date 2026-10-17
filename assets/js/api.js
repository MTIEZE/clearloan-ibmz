// ClearLoan — API client. Every page talks to the back-end through this file only.
(function () {
  const cfg = window.CL_CONFIG;

  class ApiError extends Error {
    constructor(code, message, status, field) {
      super(message);
      this.code = code; this.status = status; this.field = field;
    }
  }

  async function call(method, path, body, opts = {}) {
    let res;
    try {
      res = await fetch(cfg.API_BASE + path, {
        method,
        // The custom header + JSON body is our CSRF protection (checked by the server)
        headers: Object.assign({ 'X-ClearLoan': '1' }, body ? { 'Content-Type': 'application/json' } : {}),
        body: body ? JSON.stringify(body) : undefined,
        credentials: 'same-origin'
      });
    } catch (e) {
      throw new ApiError('network', 'Server not reachable. Check your connection and try again.', 0);
    }
    let data = null;
    try { data = await res.json(); } catch (e) { /* empty body */ }
    if (res.status === 401 && !opts.quiet401) {
      window.location.href = 'index.html?expired=1';
      throw new ApiError('unauthorized', 'Please sign in again.', 401);
    }
    if (!res.ok) {
      throw new ApiError((data && data.error) || 'server', (data && data.message) || `Server error ${res.status}. Please try again.`, res.status, data && data.field);
    }
    return data;
  }

  const m = (name) => (...args) => CL_MOCK[name](...args);
  const real = {
    login: (body) => call('POST', '/api/login', body),
    register: (body) => call('POST', '/api/register', body),
    logout: () => call('POST', '/api/logout', {}, { quiet401: true }),
    // Returns null when nobody is signed in
    me: () => call('GET', '/api/me').then((d) => (d && d.ok ? d : null)),
    apply: (body) => call('POST', '/api/apply', body),
    applications: () => call('GET', '/api/applications').then((d) => d.items),
    application: (id) => call('GET', '/api/applications/' + encodeURIComponent(id)),
    privacy: (id) => call('GET', '/api/privacy/' + encodeURIComponent(id)),
    appeal: (id, text) => call('POST', '/api/appeal/' + encodeURIComponent(id), { text }),
    reviews: () => call('GET', '/api/reviews').then((d) => d.items),
    resolveReview: (ticket, outcome, note) => call('POST', '/api/reviews/' + encodeURIComponent(ticket), { outcome, note }),
    fairness: () => call('GET', '/api/fairness')
  };

  window.ApiError = ApiError;
  window.API = cfg.USE_MOCK
    ? Object.fromEntries(Object.keys(real).map((k) => [k, m(k)]))
    : real;
})();
