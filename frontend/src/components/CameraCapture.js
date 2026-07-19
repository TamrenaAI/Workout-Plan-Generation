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
    IDLE:        '#008CFF',
    CHECKING:    '#EF9F27',
    BLUR_FAIL:   '#E24B4A',
    DARK_FAIL:   '#E24B4A',
    OVEREXPOSED: '#E24B4A',
    NOT_INBODY:  '#E24B4A',
    VALID:       '#16A34A',
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
    const color = CameraCapture.COLORS[this.state] || '#008CFF';
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
