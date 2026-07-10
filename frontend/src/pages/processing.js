// First 3 steps are still a quick cosmetic animation — image validation
// already happened on the capture page, and extraction/flag computation
// really are fast (a couple seconds), so there's nothing real to stream for
// them. The 4th step ("agents") is now REAL: it's driven by a Server-Sent
// Events connection to the backend (see api/routes/plan.py's
// /generate-plan/stream/{session_id}, fed by agents/streaming.py translating
// deepagents' astream_events() output), showing exactly which agent is
// running and what it's doing, live, until the pipeline actually finishes.
const STEPS = [
  { id: 'validate', label: 'Image validated' },
  { id: 'extract', label: 'Analysing body composition' },
  { id: 'flags', label: 'Computing training flags' },
  { id: 'agents', label: 'Starting agent pipeline...' },
];
const FAKE_DELAYS = [0, 2500, 5000]; // one per step EXCEPT 'agents', which is driven by real SSE events

let _eventSource = null;

function renderProcessing(container) {
  container.innerHTML = `
    <div class="t-screen" style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;text-align:center;">
      <div class="t-spinner"></div>
      <h2 style="font-size:20px;font-weight:600;margin-bottom:8px;">Building your protocol...</h2>
      <p style="color:var(--text-muted);font-size:13px;margin-bottom:40px;">This can take several minutes — six agent dispatches run one after another, each doing real reasoning.</p>

      <div class="step-list" style="text-align:left;width:100%;max-width:320px;" id="steps">
        ${STEPS.map((s, i) => `
          <div class="step-item ${i === 0 ? 'active' : ''}" id="step-${s.id}">
            <div class="step-icon">${i === 0 ? '⟳' : ''}</div>
            <span ${s.id === 'agents' ? 'id="agent-label"' : ''}>${s.label}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  animateFakeSteps();
  runGeneration();
}

function markDone(id) {
  const el = document.getElementById(`step-${id}`);
  if (!el) return;
  el.className = 'step-item done';
  el.querySelector('.step-icon').textContent = '✓';
}

function markActive(id) {
  const el = document.getElementById(`step-${id}`);
  if (!el) return;
  el.className = 'step-item active';
  el.querySelector('.step-icon').textContent = '⟳';
}

function animateFakeSteps() {
  FAKE_DELAYS.forEach((delay, i) => {
    setTimeout(() => {
      markDone(STEPS[i].id);
      markActive(STEPS[i + 1].id); // hands off to 'agents' after the last fake delay
    }, delay);
  });
}

function setAgentLabel(text) {
  const el = document.getElementById('agent-label');
  if (el) el.textContent = text;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function closeStream() {
  if (_eventSource) {
    _eventSource.close();
    _eventSource = null;
  }
}

// Kicks off generation, then opens a real-time SSE connection to watch the
// actual agent pipeline run — no guessing, no fixed timers past this point.
async function runGeneration() {
  const form = new FormData();
  form.append('inbody_file', window.tamrena.capturedBlob, 'scan.jpg');
  Object.entries(window.tamrena.intake).forEach(([k, v]) => {
    if (v !== undefined && v !== '') form.append(k, v);
  });

  let started;
  try {
    const res = await fetch('/generate-plan', { method: 'POST', body: form });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    started = await res.json();
  } catch (err) {
    window.tamrena.result = { error: err.message };
    await sleep(300);
    navigate('plan');
    return;
  }

  window.tamrena.result = { session_id: started.session_id, inbody: started.inbody };

  await streamProgress(started.session_id);
}

function streamProgress(sessionId) {
  return new Promise(resolve => {
    _eventSource = new EventSource(`/generate-plan/stream/${sessionId}`);

    _eventSource.onmessage = async (msg) => {
      let event;
      try {
        event = JSON.parse(msg.data);
      } catch {
        return;
      }

      if (event.type === 'progress') {
        setAgentLabel(`${event.agent}: ${event.label}`);
        return;
      }

      if (event.type === 'done') {
        closeStream();

        if (event.error) {
          window.tamrena.result = { ...window.tamrena.result, error: event.error };
        } else {
          window.tamrena.result = {
            ...window.tamrena.result,
            plan: event.plan,
            generated_at: event.generated_at,
          };
          markDone('agents');
          setAgentLabel('Training protocol generated');
          await sleep(500); // let the user actually see the final checkmark before navigating away
        }

        navigate('plan');
        resolve();
      }
    };

    _eventSource.onerror = async () => {
      closeStream();
      if (!window.tamrena.result?.plan) {
        window.tamrena.result = { ...window.tamrena.result, error: 'Lost connection to the server while generating your plan.' };
        navigate('plan');
      }
      resolve();
    };
  });
}
