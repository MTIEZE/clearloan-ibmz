// ClearLoan — theme (loaded in <head> so the page never flashes the wrong colors)
(function () {
  const KEY = 'cl_theme';
  const root = document.documentElement;
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  let saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) { /* private mode */ }
  if (saved === 'light' || saved === 'dark') root.dataset.theme = saved;

  window.CL_THEME = {
    current() { return root.dataset.theme || (media && media.matches ? 'dark' : 'light'); },
    set(theme) {
      root.dataset.theme = theme;
      try { localStorage.setItem(KEY, theme); } catch (e) { /* ignore */ }
    },
    toggle() { this.set(this.current() === 'dark' ? 'light' : 'dark'); return this.current(); }
  };
})();
