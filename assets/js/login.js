// ClearLoan — sign-in and account creation
(function () {
  const $ = (id) => document.getElementById(id);
  CL.renderHeader('index.html', null);
  CL.hydrateIcons();

  let role = 'applicant';
  let mode = 'signin';           // or 'register' (applicants only)
  const form = $('login-form');
  const btn = $('login-btn');

  if (CL.params.get('expired')) $('session-note').classList.remove('hidden');
  if (['localhost', '127.0.0.1'].includes(location.hostname) || CL_CONFIG.USE_MOCK) $('demo-hint').classList.remove('hidden');

  // Already signed in? Go straight to the right page.
  if (!CL_CONFIG.USE_MOCK && !CL.params.get('expired')) {
    API.me().then((me) => { if (me) { CL.saveSession(me); window.location.replace(CL.home(me.role)); } }).catch(() => {});
  }

  function render() {
    const staff = role === 'staff';
    const register = mode === 'register';
    $('code-field').classList.toggle('hidden', !staff);
    $('name-field').classList.toggle('hidden', !register);
    $('signin-title').textContent = register ? 'Create your account' : 'Sign in';
    $('signin-sub').textContent = register ? 'It takes less than a minute.' : 'Choose who you are.';
    $('password').autocomplete = register ? 'new-password' : 'current-password';
    btn.textContent = register ? 'Create account' : staff ? 'Sign in as staff' : 'Sign in';
    btn.className = 'btn btn-block ' + (staff ? 'btn-dark' : 'btn-primary');
    $('login-foot').innerHTML = staff
      ? 'Staff accounts are created by the admin only.'
      : register
        ? 'Already have an account? <a href="#" id="switch-mode">Sign in</a>'
        : 'New here? <a href="#" id="switch-mode">Create an account</a>';
    const sw = $('switch-mode');
    if (sw) sw.addEventListener('click', (e) => { e.preventDefault(); mode = register ? 'signin' : 'register'; hideError(); render(); (register ? $('email') : $('display_name')).focus(); });
  }

  document.querySelectorAll('[data-role]').forEach((b) => {
    b.addEventListener('click', () => {
      role = b.dataset.role;
      if (role === 'staff') mode = 'signin';
      document.querySelectorAll('[data-role]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      hideError();
      render();
    });
  });

  $('pw-toggle').addEventListener('click', () => {
    const show = $('password').type === 'password';
    $('password').type = show ? 'text' : 'password';
    $('pw-toggle').setAttribute('aria-pressed', String(show));
    $('pw-toggle').setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    $('pw-toggle').innerHTML = CL.ico(show ? 'eyeOff' : 'eye');
  });

  function showError(msg) { $('login-error').innerHTML = CL.ico('alert') + `<span>${CL.esc(msg)}</span>`; $('login-error').classList.remove('hidden'); }
  function hideError() { $('login-error').classList.add('hidden'); [$('email'), $('password'), $('display_name'), $('code')].forEach(CL.clearFieldError); }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError();
    const email = $('email').value.trim();
    const password = $('password').value;
    if (mode === 'register' && !$('display_name').value.trim()) { CL.fieldError($('display_name'), 'Please enter your first name.'); return $('display_name').focus(); }
    if (!email) { CL.fieldError($('email'), 'Please enter your email.'); return $('email').focus(); }
    if (!password) { CL.fieldError($('password'), 'Please enter your password.'); return $('password').focus(); }
    if (mode === 'register' && password.length < 8) { CL.fieldError($('password'), 'Use at least 8 characters.'); return $('password').focus(); }
    if (role === 'staff' && !/^\d{3}\s?\d{3}$/.test($('code').value.trim())) { CL.fieldError($('code'), 'Enter the 6 digits from your authenticator app.'); return $('code').focus(); }

    CL.busy(btn, true);
    try {
      const res = mode === 'register'
        ? await API.register({ email, password, display_name: $('display_name').value.trim() })
        : await API.login({ email, password, role, code: role === 'staff' ? $('code').value.replace(/\s/g, '') : undefined });
      if (!res.ok) {
        if (res.error === 'locked') return showError(`Too many wrong attempts. Try again in ${res.minutes_left} min.`);
        return showError(`Wrong email, password${role === 'staff' ? ' or code' : ''}. ${res.attempts_left ?? ''} ${res.attempts_left === 1 ? 'try' : 'tries'} left.`);
      }
      CL.saveSession(res);
      window.location.href = CL.home(res.role);
    } catch (err) {
      if (err.field && $(err.field)) { CL.fieldError($(err.field), err.message); $(err.field).focus(); }
      else showError(err.message);
    } finally {
      CL.busy(btn, false);
    }
  });

  render();
})();
