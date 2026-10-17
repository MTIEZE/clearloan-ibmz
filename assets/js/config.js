// ClearLoan front-end configuration
// USE_MOCK = true  -> fake data in the browser (no back-end needed)
// USE_MOCK = false -> real calls to the Flask API (python -m backend)
// Mock is on when the page is opened as a file (double-click on index.html), or after visiting
// any page with ?mock=1 (front-end work with a static server). ?mock=0 turns it off again.
(function () {
  let forced = null;
  try {
    const q = new URLSearchParams(location.search).get('mock');
    if (q === '1' || q === '0') sessionStorage.setItem('cl_mock_mode', q);
    forced = sessionStorage.getItem('cl_mock_mode');
  } catch (e) { /* storage blocked */ }

  window.CL_CONFIG = {
    USE_MOCK: forced ? forced === '1' : location.protocol === 'file:',
    API_BASE: '',              // '' = same server that serves the pages
    SESSION_MINUTES: 15,       // auto sign-out after inactivity (also enforced by the server)
    APPROVAL_LIMIT: 50         // risk score above this = not approved
  };
})();
