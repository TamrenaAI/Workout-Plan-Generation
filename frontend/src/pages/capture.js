let _camera = null;  // CameraCapture instance

function renderCapture(container) {
  container.innerHTML = `
    <div class="t-screen">
      <div style="margin-bottom:24px;">
        <div style="font-size:12px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Step 4 of 4</div>
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
          style="border:2px dashed var(--border-default);border-radius:var(--radius-card);
                 padding:48px 24px;text-align:center;cursor:pointer;transition:border-color 0.2s;"
          onclick="document.getElementById('file-input').click()"
          ondragover="event.preventDefault();this.style.borderColor='var(--accent-primary)'"
          ondragleave="this.style.borderColor='var(--border-default)'"
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
  event.currentTarget.style.borderColor = 'var(--border-default)';
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
// The actual /generate-plan call happens on the processing page (see
// processing.js) so it can own the real request lifecycle and only mark its
// final step done when the pipeline actually finishes.
function startGeneration() {
  if (!window.tamrena.capturedBlob) return;
  stopCamera();
  navigate('processing');
}

// ── Shared feedback renderer (used by CameraCapture too) ─────────────────────
function renderFeedback(el, state, message) {
  const colorMap = {
    IDLE:        'var(--accent-primary)',
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
