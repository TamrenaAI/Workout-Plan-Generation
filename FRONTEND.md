# Tamrena AI — Frontend Implementation Guide

Vanilla JS + CSS. No framework, no build step. Drop into `frontend/` and open `index.html`.

---

## File Structure

```
frontend/
├── index.html              ← single-page app shell, loads all scripts/styles
├── src/
│   ├── theme.css           ← CSS custom properties (design tokens only)
│   ├── base.css            ← resets, typography, shared component classes
│   ├── main.js             ← router — maps hash to page, mounts/unmounts
│   │
│   ├── pages/
│   │   ├── home.js         ← landing
│   │   ├── intake.js       ← Hunter Profile form
│   │   ├── capture.js      ← camera + PDF upload + validation
│   │   ├── processing.js   ← loading state with step tracker
│   │   └── plan.js         ← formatted Training Protocol
│   │
│   └── components/
│       ├── CameraCapture.js      ← camera feed, canvas overlay, state machine
│       ├── ValidationFeedback.js ← status badge below the camera frame
│       ├── PillSelector.js       ← multi-option pill button group (reused on intake)
│       ├── StatTile.js           ← single stat box (value + label)
│       └── PlanDay.js            ← one training day card
```

---

## index.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Tamrena AI</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Rajdhani:wght@700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="src/theme.css" />
  <link rel="stylesheet" href="src/base.css" />
</head>
<body>
  <div id="app"></div>

  <script src="src/components/CameraCapture.js"></script>
  <script src="src/components/ValidationFeedback.js"></script>
  <script src="src/components/PillSelector.js"></script>
  <script src="src/components/StatTile.js"></script>
  <script src="src/components/PlanDay.js"></script>
  <script src="src/pages/home.js"></script>
  <script src="src/pages/intake.js"></script>
  <script src="src/pages/capture.js"></script>
  <script src="src/pages/processing.js"></script>
  <script src="src/pages/plan.js"></script>
  <script src="src/main.js"></script>
</body>
</html>
```

---

## src/theme.css

```css
:root {
  --bg-primary:     #0F0F14;
  --bg-card:        #1A1628;
  --bg-card-alt:    #1E1A2E;
  --bg-input:       #13101F;
  --bg-overlay:     #0A0812;

  --purple-deep:    #26215C;
  --purple-mid:     #534AB7;
  --purple-primary: #7F77DD;
  --purple-light:   #AFA9EC;
  --purple-pale:    #EEEDFE;

  --text-primary:   #F0EEFF;
  --text-secondary: #AFA9EC;
  --text-muted:     #7070A0;
  --text-disabled:  #3D3A5C;

  --border-subtle:  #1E1A2E;
  --border-default: #2A2A3A;
  --border-accent:  #7F77DD;

  --success:        #1D9E75;
  --warning:        #EF9F27;
  --danger:         #E24B4A;
  --streak-fire:    #FF6B35;

  --xp-start:       #5C3DB5;
  --xp-end:         #AFA9EC;

  --radius-card:    16px;
  --radius-badge:   20px;
  --radius-button:  12px;
  --radius-tile:    10px;

  --screen-pad:     20px;
  --card-pad:       18px;
  --gap-cards:      12px;
  --gap-inner:      8px;
}
```

---

## src/base.css

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Inter', sans-serif;
  font-size: 15px;
  line-height: 1.5;
  min-height: 100vh;
}

/* ── Layout ── */
.t-screen {
  max-width: 520px;
  margin: 0 auto;
  padding: 32px var(--screen-pad) 48px;
}

.t-section-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

/* ── Card ── */
.t-card {
  background: var(--bg-card);
  border: 0.5px solid var(--border-default);
  border-radius: var(--radius-card);
  padding: var(--card-pad);
}

/* ── Buttons ── */
.t-btn-primary {
  display: block;
  width: 100%;
  height: 52px;
  background: var(--purple-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-button);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.t-btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.t-btn-ghost {
  display: block;
  width: 100%;
  height: 48px;
  background: var(--bg-card-alt);
  color: var(--purple-light);
  border: 1px solid var(--purple-mid);
  border-radius: var(--radius-button);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

/* ── Badge ── */
.t-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: var(--radius-badge);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  background: var(--bg-card-alt);
  border: 1px solid var(--purple-mid);
  color: var(--purple-light);
}
.t-badge.success { border-color: var(--success); color: var(--success); }
.t-badge.danger  { border-color: var(--danger);  color: var(--danger);  }
.t-badge.warning { border-color: var(--warning); color: var(--warning); }

/* ── Stat tile ── */
.t-stat-tile {
  background: var(--bg-card-alt);
  border: 0.5px solid var(--border-subtle);
  border-radius: var(--radius-tile);
  padding: 12px 8px;
  text-align: center;
}
.t-stat-tile .value {
  display: block;
  font-family: 'Rajdhani', sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--purple-light);
}
.t-stat-tile .label {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* ── Pill selector ── */
.pill-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.pill {
  padding: 8px 16px;
  border-radius: var(--radius-badge);
  border: 1px solid var(--border-default);
  background: var(--bg-input);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.pill.active {
  border-color: var(--purple-primary);
  background: var(--purple-deep);
  color: var(--text-primary);
}

/* ── Form label ── */
.t-label {
  display: block;
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

/* ── Divider ── */
.t-divider {
  height: 0.5px;
  background: var(--border-default);
  margin: 20px 0;
}

/* ── Step tracker (used on processing page) ── */
.step-list { display: flex; flex-direction: column; gap: 16px; }
.step-item {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-muted);
  font-size: 14px;
}
.step-item.done    { color: var(--success); }
.step-item.active  { color: var(--text-primary); font-weight: 600; }
.step-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1.5px solid currentColor;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}
.step-item.done .step-icon  { background: var(--success); border-color: var(--success); color: #fff; }
.step-item.active .step-icon { border-color: var(--purple-primary); color: var(--purple-primary); }

/* ── Spinner ── */
@keyframes spin { to { transform: rotate(360deg); } }
.t-spinner {
  width: 48px;
  height: 48px;
  border: 3px solid var(--border-default);
  border-top-color: var(--purple-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 24px;
}

/* ── Exercise table ── */
.exercise-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.exercise-table th {
  text-align: left;
  color: var(--text-muted);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  padding: 8px 0;
  border-bottom: 0.5px solid var(--border-default);
}
.exercise-table td {
  padding: 10px 0;
  color: var(--text-primary);
  border-bottom: 0.5px solid var(--border-subtle);
  vertical-align: top;
}
.exercise-table td:first-child { font-weight: 500; }
```

---

## src/main.js

```javascript
// ── Global session state ──────────────────────────────────────────────────────
window.tamrena = {
  intake: {},           // filled by intake.js
  capturedBlob: null,   // set by CameraCapture after VALID state
  result: null,         // set after /generate-plan response
};

// ── Pages registry ────────────────────────────────────────────────────────────
const PAGES = {
  '':           renderHome,
  'home':       renderHome,
  'intake':     renderIntake,
  'capture':    renderCapture,
  'processing': renderProcessing,
  'plan':       renderPlan,
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
```

---

## src/pages/home.js

```javascript
function renderHome(container) {
  container.innerHTML = `
    <div class="t-screen" style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;text-align:center;">
      <div style="margin-bottom:48px;">
        <div style="font-family:'Rajdhani',sans-serif;font-size:42px;font-weight:700;color:var(--purple-primary);letter-spacing:2px;">TAMRENA</div>
        <div style="font-size:13px;color:var(--purple-light);letter-spacing:6px;text-transform:uppercase;margin-top:4px;">AI Training System</div>
      </div>

      <p style="color:var(--text-secondary);font-size:16px;max-width:300px;line-height:1.6;margin-bottom:48px;">
        Your body. Your data. Your protocol.
      </p>

      <div style="width:100%;max-width:320px;">
        <button class="t-btn-primary" onclick="navigate('intake')">Begin Assessment</button>
      </div>

      <div class="t-badge" style="margin-top:32px;">Hunter Rank System</div>
    </div>
  `;
}
```

---

## src/pages/intake.js

```javascript
function renderIntake(container) {
  // State held in the DOM — read values on submit
  container.innerHTML = `
    <div class="t-screen">
      <div style="margin-bottom:32px;">
        <div style="font-size:12px;color:var(--purple-light);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Step 1 of 2</div>
        <h1 style="font-size:28px;font-weight:700;">Hunter Profile</h1>
      </div>

      <!-- Goal -->
      <div style="margin-bottom:24px;">
        <span class="t-label">Training Goal</span>
        <div class="pill-group" id="goal-pills">
          <button class="pill active" data-value="hypertrophy">Hypertrophy</button>
          <button class="pill" data-value="strength">Strength</button>
          <button class="pill" data-value="fat_loss">Fat Loss</button>
          <button class="pill" data-value="general_fitness">General Fitness</button>
        </div>
      </div>

      <!-- Days per week -->
      <div style="margin-bottom:24px;">
        <span class="t-label">Days per Week</span>
        <div class="pill-group" id="days-pills">
          ${[2,3,4,5,6].map((d,i) => `
            <button class="pill ${i===2?'active':''}" data-value="${d}">${d} days</button>
          `).join('')}
        </div>
      </div>

      <!-- Experience -->
      <div style="margin-bottom:24px;">
        <span class="t-label">Experience Level</span>
        <div class="pill-group" id="exp-pills">
          <button class="pill active" data-value="beginner">Novice</button>
          <button class="pill" data-value="intermediate">Intermediate</button>
          <button class="pill" data-value="advanced">Advanced</button>
        </div>
      </div>

      <!-- Session duration -->
      <div style="margin-bottom:32px;">
        <span class="t-label">Session Duration</span>
        <div class="pill-group" id="dur-pills">
          <button class="pill active" data-value="45min">45 min</button>
          <button class="pill" data-value="60min">60 min</button>
          <button class="pill" data-value="90min">90 min</button>
        </div>
      </div>

      <!-- Optional section -->
      <div style="margin-bottom:32px;">
        <button class="t-btn-ghost" onclick="toggleOptional(this)" style="margin-bottom:12px;">
          + Optional Details
        </button>
        <div id="optional-fields" style="display:none;">
          <div style="display:flex;flex-direction:column;gap:12px;">
            ${optionalField('injuries', 'Injuries / Limitations', 'e.g. left knee, lower back')}
            ${optionalField('priority', 'Priority Muscle Group', 'e.g. back, legs')}
            ${optionalField('age', 'Age', '', 'number')}
            ${selectField('sleep_quality', 'Sleep Quality', ['Good (7-9h)', 'Average (5-7h)', 'Poor (<5h)'])}
            ${selectField('job_type', 'Job Type', ['Desk job', 'Active job', 'Standing job'])}
          </div>
        </div>
      </div>

      <button class="t-btn-primary" onclick="submitIntake()">Continue to Scan</button>
    </div>
  `;

  // Wire up pill groups
  ['goal','days','exp','dur'].forEach(id => {
    document.getElementById(`${id}-pills`).addEventListener('click', e => {
      const pill = e.target.closest('.pill');
      if (!pill) return;
      document.querySelectorAll(`#${id}-pills .pill`).forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
    });
  });
}

function optionalField(id, label, placeholder, type = 'text') {
  return `
    <div>
      <span class="t-label">${label}</span>
      <input id="field-${id}" type="${type}" placeholder="${placeholder}"
        style="width:100%;height:44px;background:var(--bg-input);border:1px solid var(--border-default);
               border-radius:10px;padding:0 14px;color:var(--text-primary);font-size:14px;outline:none;" />
    </div>
  `;
}

function selectField(id, label, options) {
  return `
    <div>
      <span class="t-label">${label}</span>
      <select id="field-${id}"
        style="width:100%;height:44px;background:var(--bg-input);border:1px solid var(--border-default);
               border-radius:10px;padding:0 14px;color:var(--text-primary);font-size:14px;outline:none;appearance:none;">
        <option value="">— optional —</option>
        ${options.map(o => `<option value="${o.toLowerCase().replace(/\s+/g,'_')}">${o}</option>`).join('')}
      </select>
    </div>
  `;
}

function toggleOptional(btn) {
  const el = document.getElementById('optional-fields');
  const hidden = el.style.display === 'none';
  el.style.display = hidden ? 'block' : 'none';
  btn.textContent = hidden ? '− Optional Details' : '+ Optional Details';
}

function submitIntake() {
  const getActive = id => document.querySelector(`#${id}-pills .pill.active`)?.dataset.value;
  const getField  = id => document.getElementById(`field-${id}`)?.value || undefined;

  window.tamrena.intake = {
    goal:             getActive('goal'),
    days_per_week:    parseInt(getActive('days')),
    experience:       getActive('exp'),
    session_duration: getActive('dur'),
    injuries:         getField('injuries'),
    priority:         getField('priority'),
    age:              getField('age') ? parseInt(getField('age')) : undefined,
    sleep_quality:    getField('sleep_quality'),
    job_type:         getField('job_type'),
  };

  navigate('capture');
}
```

---

## src/pages/capture.js

```javascript
let _camera = null;  // CameraCapture instance

function renderCapture(container) {
  container.innerHTML = `
    <div class="t-screen">
      <div style="margin-bottom:24px;">
        <div style="font-size:12px;color:var(--purple-light);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Step 2 of 2</div>
        <h1 style="font-size:28px;font-weight:700;">Scan InBody</h1>
        <p style="color:var(--text-muted);font-size:14px;margin-top:6px;">Position the InBody result sheet inside the frame.</p>
      </div>

      <!-- Mode toggle -->
      <div style="display:flex;gap:8px;margin-bottom:20px;">
        <button id="tab-camera" class="pill active" onclick="switchMode('camera')">📷 Camera</button>
        <button id="tab-pdf"    class="pill"        onclick="switchMode('pdf')">📄 Upload PDF</button>
      </div>

      <!-- Camera mode -->
      <div id="mode-camera">
        <div id="camera-container" style="position:relative;width:100%;border-radius:var(--radius-card);overflow:hidden;background:#000;aspect-ratio:4/3;">
          <video id="camera-video" autoplay playsinline muted
            style="width:100%;height:100%;object-fit:cover;display:block;"></video>
          <canvas id="camera-canvas"
            style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;"></canvas>
        </div>

        <div id="validation-feedback" style="margin:16px 0;min-height:40px;"></div>

        <button class="t-btn-primary" id="capture-btn" onclick="doCapture()">Capture</button>
      </div>

      <!-- PDF upload mode -->
      <div id="mode-pdf" style="display:none;">
        <div id="drop-zone"
          style="border:2px dashed var(--purple-mid);border-radius:var(--radius-card);
                 padding:48px 24px;text-align:center;cursor:pointer;transition:border-color 0.2s;"
          onclick="document.getElementById('file-input').click()"
          ondragover="event.preventDefault();this.style.borderColor='var(--purple-primary)'"
          ondragleave="this.style.borderColor='var(--purple-mid)'"
          ondrop="handleDrop(event)">
          <div style="font-size:32px;margin-bottom:12px;">📄</div>
          <div style="color:var(--text-primary);font-weight:600;">Drop your InBody PDF or image here</div>
          <div style="color:var(--text-muted);font-size:13px;margin-top:4px;">JPEG, PNG, PDF accepted</div>
        </div>
        <input id="file-input" type="file" accept="image/jpeg,image/png,application/pdf"
          style="display:none;" onchange="handleFileSelect(event)" />
        <div id="file-name" style="color:var(--text-muted);font-size:13px;margin-top:12px;min-height:20px;"></div>
        <div id="pdf-feedback" style="margin:12px 0;min-height:40px;"></div>
      </div>

      <div style="margin-top:24px;">
        <button class="t-btn-primary" id="generate-btn" onclick="startGeneration()" disabled>
          Generate Training Protocol
        </button>
      </div>
    </div>
  `;

  // Start camera by default
  startCamera();
}

// ── Camera ────────────────────────────────────────────────────────────────────
async function startCamera() {
  const video  = document.getElementById('camera-video');
  const canvas = document.getElementById('camera-canvas');
  const feedback = document.getElementById('validation-feedback');

  if (!video) return;

  _camera = new CameraCapture(video, canvas, feedback);
  await _camera.start();
}

function stopCamera() {
  if (_camera) { _camera.stop(); _camera = null; }
}

async function doCapture() {
  if (!_camera) return;
  const result = await _camera.capture();
  if (result && result.valid) {
    window.tamrena.capturedBlob = result.blob;
    document.getElementById('generate-btn').disabled = false;
  }
}

// ── PDF / file upload ─────────────────────────────────────────────────────────
function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file) processFile(file);
}

function handleDrop(event) {
  event.preventDefault();
  event.currentTarget.style.borderColor = 'var(--purple-mid)';
  const file = event.dataTransfer.files[0];
  if (file) processFile(file);
}

async function processFile(file) {
  document.getElementById('file-name').textContent = file.name;
  const feedback = document.getElementById('pdf-feedback');
  renderFeedback(feedback, 'CHECKING', 'Validating scan...');

  const form = new FormData();
  form.append('file', file);

  try {
    const res  = await fetch('/validate-image', { method: 'POST', body: form });
    const data = await res.json();

    if (data.valid) {
      window.tamrena.capturedBlob = file;
      renderFeedback(feedback, 'VALID', '✓ InBody scan detected');
      document.getElementById('generate-btn').disabled = false;
    } else {
      renderFeedback(feedback, 'FAIL', data.issue || 'Validation failed');
      document.getElementById('generate-btn').disabled = true;
    }
  } catch {
    renderFeedback(feedback, 'FAIL', 'Server error — try again');
  }
}

// ── Mode switch ───────────────────────────────────────────────────────────────
function switchMode(mode) {
  document.getElementById('mode-camera').style.display = mode === 'camera' ? 'block' : 'none';
  document.getElementById('mode-pdf').style.display    = mode === 'pdf'    ? 'block' : 'none';
  document.getElementById('tab-camera').classList.toggle('active', mode === 'camera');
  document.getElementById('tab-pdf').classList.toggle('active',    mode === 'pdf');

  if (mode === 'camera') {
    startCamera();
  } else {
    stopCamera();
  }

  window.tamrena.capturedBlob = null;
  document.getElementById('generate-btn').disabled = true;
}

// ── Submit ────────────────────────────────────────────────────────────────────
async function startGeneration() {
  if (!window.tamrena.capturedBlob) return;
  stopCamera();
  navigate('processing');

  const form = new FormData();
  form.append('inbody_file', window.tamrena.capturedBlob, 'scan.jpg');
  Object.entries(window.tamrena.intake).forEach(([k, v]) => {
    if (v !== undefined && v !== '') form.append(k, v);
  });

  try {
    const res  = await fetch('/generate-plan', { method: 'POST', body: form });
    const data = await res.json();
    window.tamrena.result = data;
    navigate('plan');
  } catch (err) {
    window.tamrena.result = { error: err.message };
    navigate('plan');
  }
}

// ── Shared feedback renderer (used by CameraCapture too) ─────────────────────
function renderFeedback(el, state, message) {
  const colorMap = {
    IDLE:        'var(--purple-light)',
    CHECKING:    'var(--warning)',
    VALID:       'var(--success)',
    FAIL:        'var(--danger)',
    BLUR_FAIL:   'var(--danger)',
    DARK_FAIL:   'var(--danger)',
    OVEREXPOSED: 'var(--danger)',
    NOT_INBODY:  'var(--danger)',
  };
  const badgeClass = state === 'VALID' ? 'success' : state.includes('FAIL') || state === 'NOT_INBODY' ? 'danger' : state === 'CHECKING' ? 'warning' : '';
  el.innerHTML = `<span class="t-badge ${badgeClass}" style="color:${colorMap[state]||'var(--text-muted)'};">${message}</span>`;
}
```

---

## src/components/CameraCapture.js

The camera component owns the video feed, canvas overlay, and validation state machine.

```javascript
class CameraCapture {
  // STATES: IDLE | CHECKING | BLUR_FAIL | DARK_FAIL | OVEREXPOSED | NOT_INBODY | VALID
  static MESSAGES = {
    IDLE:        'Position the InBody scan inside the frame',
    CHECKING:    'Checking image quality...',
    BLUR_FAIL:   'Hold steady — image is too blurry',
    DARK_FAIL:   'Too dark — move to better lighting',
    OVEREXPOSED: 'Too bright — avoid direct light on the scan',
    NOT_INBODY:  'Not recognised as InBody scan — reposition and retake',
    VALID:       '✓ InBody scan detected',
  };

  static COLORS = {
    IDLE:        '#7F77DD',
    CHECKING:    '#EF9F27',
    BLUR_FAIL:   '#E24B4A',
    DARK_FAIL:   '#E24B4A',
    OVEREXPOSED: '#E24B4A',
    NOT_INBODY:  '#E24B4A',
    VALID:       '#1D9E75',
  };

  constructor(videoEl, canvasEl, feedbackEl) {
    this.video    = videoEl;
    this.canvas   = canvasEl;
    this.ctx      = canvasEl.getContext('2d');
    this.feedback = feedbackEl;
    this.state    = 'IDLE';
    this.stream   = null;
    this._rafId   = null;
    this._frozen  = false;
  }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      this.video.srcObject = this.stream;
      await this.video.play();

      // Match canvas size to video element's rendered size
      const resizeObserver = new ResizeObserver(() => this._syncCanvasSize());
      resizeObserver.observe(this.video);
      this._syncCanvasSize();

      this._loop();
      this._setState('IDLE');
    } catch (err) {
      this._setState('DARK_FAIL');  // camera unavailable — show error
      if (this.feedback) this.feedback.innerHTML =
        `<span class="t-badge danger">Camera not available: ${err.message}</span>`;
    }
  }

  stop() {
    cancelAnimationFrame(this._rafId);
    this.stream?.getTracks().forEach(t => t.stop());
  }

  // ── Capture flow ─────────────────────────────────────────────────────────────
  async capture() {
    // 1. Freeze frame
    this._frozen = true;
    this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

    // 2. Client-side brightness checks (no API, instant)
    const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
    const { brightness, darkRatio } = this._analysePixels(imageData);

    if (brightness < 50) {
      this._unfreeze();
      this._setState('DARK_FAIL');
      return null;
    }
    if (darkRatio < 0.02) {
      this._unfreeze();
      this._setState('OVEREXPOSED');
      return null;
    }

    // 3. Server validation
    this._setState('CHECKING');

    const blob = await new Promise(res => this.canvas.toBlob(res, 'image/jpeg', 0.92));
    const form = new FormData();
    form.append('file', blob, 'capture.jpg');

    try {
      const res  = await fetch('/validate-image', { method: 'POST', body: form });
      const data = await res.json();

      if (data.valid) {
        this._setState('VALID');
        return { valid: true, blob };
      } else {
        const stageMap = { blur: 'BLUR_FAIL', authenticity: 'NOT_INBODY' };
        this._setState(stageMap[data.stage] || 'BLUR_FAIL');
        this._unfreeze();
        return null;
      }
    } catch {
      this._setState('BLUR_FAIL');
      this._unfreeze();
      return null;
    }
  }

  // ── Drawing ───────────────────────────────────────────────────────────────────
  _loop() {
    if (!this._frozen) {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      this._drawFrame();
    }
    this._rafId = requestAnimationFrame(() => this._loop());
  }

  _drawFrame() {
    const color = CameraCapture.COLORS[this.state] || '#7F77DD';
    const w = this.canvas.width, h = this.canvas.height;
    const x1 = w * 0.05, y1 = h * 0.05;
    const x2 = w * 0.95, y2 = h * 0.95;
    const corner = Math.min(w, h) * 0.05;  // responsive corner length

    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = 3;

    // Thin full rectangle (50% opacity)
    this.ctx.globalAlpha = 0.5;
    this.ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    this.ctx.globalAlpha = 1;

    // Bold L-shaped corner accents
    const corners = [[x1,y1,1,1],[x2,y1,-1,1],[x1,y2,1,-1],[x2,y2,-1,-1]];
    corners.forEach(([cx, cy, dx, dy]) => {
      this.ctx.beginPath();
      this.ctx.moveTo(cx, cy); this.ctx.lineTo(cx + dx * corner, cy);
      this.ctx.stroke();
      this.ctx.beginPath();
      this.ctx.moveTo(cx, cy); this.ctx.lineTo(cx, cy + dy * corner);
      this.ctx.stroke();
    });

    // State label inside frame (top-center)
    if (this.state !== 'IDLE') {
      this.ctx.fillStyle = color;
      this.ctx.font = '600 13px Inter, sans-serif';
      this.ctx.textAlign = 'center';
      this.ctx.fillText(CameraCapture.MESSAGES[this.state], w / 2, y1 + 24);
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────────
  _setState(state) {
    this.state = state;
    if (this.feedback) renderFeedback(this.feedback, state, CameraCapture.MESSAGES[state]);
  }

  _unfreeze() {
    this._frozen = false;
  }

  _syncCanvasSize() {
    const rect = this.video.getBoundingClientRect();
    this.canvas.width  = rect.width  || 640;
    this.canvas.height = rect.height || 480;
  }

  _analysePixels(imageData) {
    let sum = 0, dark = 0;
    const len = imageData.data.length / 4;
    for (let i = 0; i < imageData.data.length; i += 4) {
      const lum = 0.299 * imageData.data[i] + 0.587 * imageData.data[i+1] + 0.114 * imageData.data[i+2];
      sum += lum;
      if (lum < 80) dark++;
    }
    return { brightness: sum / len, darkRatio: dark / len };
  }
}
```

---

## src/pages/processing.js

```javascript
const STEPS = [
  { id: 'validate',  label: 'Image validated' },
  { id: 'extract',   label: 'Analysing body composition' },
  { id: 'flags',     label: 'Computing training flags' },
  { id: 'plan',      label: 'Generating Training Protocol' },
];

function renderProcessing(container) {
  container.innerHTML = `
    <div class="t-screen" style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;text-align:center;">
      <div class="t-spinner"></div>
      <h2 style="font-size:20px;font-weight:600;margin-bottom:8px;">Building your protocol...</h2>
      <p style="color:var(--text-muted);font-size:13px;margin-bottom:40px;"></p>

      <div class="step-list" style="text-align:left;width:100%;max-width:280px;" id="steps">
        ${STEPS.map((s, i) => `
          <div class="step-item ${i === 0 ? 'active' : ''}" id="step-${s.id}">
            <div class="step-icon">${i === 0 ? '⟳' : ''}</div>
            <span>${s.label}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  // Simulate step progress (real progress comes from API response timing)
  animateSteps();
}

function animateSteps() {
  const delays = [0, 4000, 8000, 14000];  // approximate timing per stage
  STEPS.forEach((step, i) => {
    setTimeout(() => {
      const el = document.getElementById(`step-${step.id}`);
      if (!el) return;
      el.className = 'step-item done';
      el.querySelector('.step-icon').textContent = '✓';

      const next = STEPS[i + 1];
      if (next) {
        const nextEl = document.getElementById(`step-${next.id}`);
        if (nextEl) {
          nextEl.className = 'step-item active';
          nextEl.querySelector('.step-icon').textContent = '⟳';
        }
      }
    }, delays[i]);
  });
}
```

---

## src/pages/plan.js

```javascript
function renderPlan(container) {
  const result = window.tamrena.result;

  if (!result || result.error) {
    container.innerHTML = `
      <div class="t-screen" style="text-align:center;padding-top:80px;">
        <div style="font-size:32px;margin-bottom:16px;">⚠️</div>
        <h2 style="color:var(--danger);margin-bottom:8px;">Generation Failed</h2>
        <p style="color:var(--text-muted);">${result?.error || 'Unknown error'}</p>
        <button class="t-btn-ghost" style="margin-top:32px;" onclick="navigate('capture')">Try Again</button>
      </div>
    `;
    return;
  }

  const inbody = result.inbody;
  const raw    = inbody?.raw || {};
  const flags  = inbody?.flags || {};

  const flagCount = Object.values(flags).filter(v => v === true).length;

  container.innerHTML = `
    <div class="t-screen">

      <!-- Header -->
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;">
        <div>
          <h1 style="font-size:28px;font-weight:700;margin-bottom:4px;">Training Protocol</h1>
          <span class="t-badge">${formatGoal(window.tamrena.intake.goal)}</span>
        </div>
        <button onclick="downloadPlan()" class="t-btn-ghost"
          style="width:auto;height:36px;padding:0 16px;font-size:13px;">Download</button>
      </div>

      <!-- InBody summary -->
      <div class="t-card" style="margin-bottom:20px;">
        <div style="font-size:13px;font-weight:600;color:var(--text-muted);text-transform:uppercase;
                    letter-spacing:0.5px;margin-bottom:14px;">Body Composition Summary</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;">
          <div class="t-stat-tile">
            <span class="value">${raw.skeletal_muscle_mass ?? '—'}</span>
            <span class="label">SMM (${raw.smm_unit || 'kg'})</span>
          </div>
          <div class="t-stat-tile">
            <span class="value">${raw.body_fat_percent ?? '—'}%</span>
            <span class="label">Body Fat</span>
          </div>
          <div class="t-stat-tile">
            <span class="value">${raw.bmr_kcal ?? '—'}</span>
            <span class="label">BMR (kcal)</span>
          </div>
          <div class="t-stat-tile ${flagCount > 0 ? 'flag-active' : ''}">
            <span class="value" style="${flagCount > 0 ? 'color:var(--warning)' : ''}">${flagCount}</span>
            <span class="label">Flags</span>
          </div>
        </div>
      </div>

      <!-- Flags (if any) -->
      ${flagCount > 0 ? renderFlags(flags) : ''}

      <!-- Plan -->
      <div style="margin-bottom:12px;">
        <div class="t-section-title">Weekly Schedule</div>
      </div>

      <div id="plan-content">
        ${renderPlanMarkdown(result.plan)}
      </div>

    </div>
  `;
}

function renderFlags(flags) {
  const active = [];
  if (flags.arm_asymmetry) active.push(`Arm asymmetry — ${flags.weaker_arm} arm weaker by ${Math.round(flags.arm_diff_grams)}g`);
  if (flags.leg_asymmetry) active.push(`Leg asymmetry — ${flags.weaker_leg} leg weaker by ${Math.round(flags.leg_diff_grams)}g`);
  if (flags.elevated_bf)   active.push('Elevated body fat percentage');
  if (flags.trunk_underdeveloped) active.push('Trunk muscle mass below ideal');

  return `
    <div class="t-card" style="border-color:var(--warning);margin-bottom:20px;">
      <div style="font-size:13px;font-weight:600;color:var(--warning);text-transform:uppercase;
                  letter-spacing:0.5px;margin-bottom:10px;">⚠ Training Flags</div>
      ${active.map(f => `<div style="color:var(--text-secondary);font-size:14px;margin-bottom:6px;">• ${f}</div>`).join('')}
    </div>
  `;
}

// Renders the plain-text/markdown plan returned by the API into styled cards
function renderPlanMarkdown(markdown) {
  if (!markdown) return `<p style="color:var(--text-muted);">No plan generated.</p>`;

  // Split into day sections (lines starting with "Day" or "## Day")
  const sections = markdown
    .split(/\n(?=#{1,2} Day|\nDay \d)/i)
    .filter(s => s.trim());

  if (sections.length <= 1) {
    // Fallback: render as pre-formatted text if structure not recognised
    return `<pre style="white-space:pre-wrap;color:var(--text-secondary);font-size:13px;line-height:1.7;">${markdown}</pre>`;
  }

  return sections.map(section => {
    const lines = section.trim().split('\n');
    const title = lines[0].replace(/^#+\s*/, '');
    const body  = lines.slice(1).join('\n').trim();
    return `
      <div class="t-card" style="margin-bottom:12px;">
        <div style="font-family:'Rajdhani',sans-serif;font-size:18px;font-weight:700;
                    color:var(--purple-light);margin-bottom:12px;">${title}</div>
        <pre style="white-space:pre-wrap;color:var(--text-secondary);font-size:13px;line-height:1.7;
                    font-family:'Inter',sans-serif;">${body}</pre>
      </div>
    `;
  }).join('');
}

function formatGoal(goal) {
  const map = {
    hypertrophy:     'Hypertrophy',
    strength:        'Strength',
    fat_loss:        'Fat Loss',
    general_fitness: 'General Fitness',
  };
  return map[goal] || goal || 'Protocol';
}

function downloadPlan() {
  const plan = window.tamrena.result?.plan || 'No plan';
  const blob = new Blob([plan], { type: 'text/markdown' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url;
  a.download = 'tamrena_protocol.md';
  a.click();
  URL.revokeObjectURL(url);
}
```

---

## Backend connection notes

The frontend expects these exact API shapes from the existing FastAPI backend:

**POST /validate-image**
```
FormData: { file: File }
Response: { valid: bool, stage: "blur"|"authenticity"|null, issue: str|null }
```

**POST /generate-plan**
```
FormData: { inbody_file: File, goal: str, days_per_week: int,
            experience: str, session_duration: str, ...optional fields }
Response: { session_id: str, inbody: InBodyResult, plan: str, generated_at: str }
```

If the backend already returns these shapes, no changes are needed there.

---

## Running locally

```bash
# Serve frontend (from project root)
python -m http.server 3000 --directory frontend

# Backend must be running on port 8000
uvicorn backend.api.main:app --reload --port 8000
```

For local dev, add a proxy in the backend to avoid CORS issues:
```python
# backend/api/main.py
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])
```

Or serve both from the same origin by mounting the frontend as a static directory:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```
