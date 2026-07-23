// ── Global session state ──────────────────────────────────────────────────────
// intake is restored from sessionStorage so a hard refresh mid-flow doesn't
// silently drop it — this is a hash-based router (see mount() below), so a
// real page reload keeps whatever step's hash you were on and re-renders it
// directly, skipping the earlier steps that would otherwise populate intake.
// capturedBlob/result/authToken intentionally do NOT persist: a Blob can't
// be serialized to sessionStorage, and losing the auth token / plan result
// on a real reload is fine — those are cheap to redo (dev-login) or are
// meant to be regenerated anyway.
function loadStoredIntake() {
  try {
    return JSON.parse(sessionStorage.getItem('tamrena_intake') || '{}');
  } catch {
    return {};
  }
}

window.tamrena = {
  intake: loadStoredIntake(),  // filled by intake.js
  capturedBlob: null,   // set by CameraCapture after VALID state
  result: null,         // set after /generate-plan response
  authToken: null,      // set by processing.js's ensureAuthToken() (dev-login)
};

// intake.js calls this instead of assigning window.tamrena.intake directly,
// so every update is also persisted.
function saveIntake(patch) {
  window.tamrena.intake = { ...window.tamrena.intake, ...patch };
  sessionStorage.setItem('tamrena_intake', JSON.stringify(window.tamrena.intake));
}

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
  'workout-test':   renderWorkoutTest,
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
