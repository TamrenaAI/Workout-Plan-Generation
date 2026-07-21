// ── Global session state ──────────────────────────────────────────────────────
window.tamrena = {
  intake: {},           // filled by intake.js
  capturedBlob: null,   // set by CameraCapture after VALID state
  result: null,         // set after /generate-plan response
  authToken: null,      // set by processing.js's ensureAuthToken() (dev-login)
};

// ── Pages registry ────────────────────────────────────────────────────────────
const PAGES = {
  '':               renderHome,
  'home':           renderHome,
  'intake':         renderIntake,
  'intake-step2':   renderIntakeStep2,
  'intake-optional':renderIntakeOptional,
  'capture':        renderCapture,
  'processing':     renderProcessing,
  'plan':           renderPlan,
};

// ── Router ────────────────────────────────────────────────────────────────────
function navigate(hash) {
  window.location.hash = hash;
}

function mount() {
  const hash = window.location.hash.replace('#', '').split('?')[0];
  const render = PAGES[hash] || renderHome;
  const app = document.getElementById('app');
  app.innerHTML = '';
  render(app);
}

window.addEventListener('hashchange', mount);
window.addEventListener('DOMContentLoaded', mount);
