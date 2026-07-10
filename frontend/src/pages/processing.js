// First 3 steps are a quick cosmetic animation (validation already happened
// on the capture page; extraction + flag computation are genuinely fast).
// The 4th step ("agents") is NOT timer-based — it stays active, cycling
// through what the backend agents are actually doing, until the real
// /generate-plan request resolves. This is the part that actually takes
// 30-90 seconds, so it's the one step that must reflect real completion,
// not a guessed delay — otherwise it either finishes "done" while the
// server is still working, or sits there with no explanation for a long
// stretch and looks like the site froze.
const STEPS = [
  { id: 'validate', label: 'Image validated' },
  { id: 'extract', label: 'Analysing body composition' },
  { id: 'flags', label: 'Computing training flags' },
  { id: 'agents', label: 'Starting agent pipeline...' },
];
const FAKE_DELAYS = [0, 2500, 5000]; // one per step EXCEPT 'agents', which waits for the real fetch

// Rough narration of the real pipeline (Supervisor -> Exercise Recommender
// per muscle group -> Plan Assembler) so the user sees continuous, plausible
// progress instead of a static spinner for the ~30-90s this stage can take.
const AGENT_MESSAGES = [
  'Supervisor: classifying your goal...',
  'Supervisor: reading InBody analysis...',
  'Supervisor: building your weekly split...',
  'Exercise Recommender: chest...',
  'Exercise Recommender: back...',
  'Exercise Recommender: shoulders...',
  'Exercise Recommender: arms...',
  'Exercise Recommender: legs...',
  'Plan Assembler: scheduling sessions...',
  'Plan Assembler: checking recovery rules...',
];

let _agentTickerId = null;

function renderProcessing(container) {
  container.innerHTML = `
    <div class="t-screen" style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;text-align:center;">
      <div class="t-spinner"></div>
      <h2 style="font-size:20px;font-weight:600;margin-bottom:8px;">Building your protocol...</h2>
      <p style="color:var(--text-muted);font-size:13px;margin-bottom:40px;">This can take up to a minute or two — the agents are doing real work.</p>

      <div class="step-list" style="text-align:left;width:100%;max-width:280px;" id="steps">
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
  startAgentTicker();
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

// Cycles the 'agents' step's label through AGENT_MESSAGES on a fixed
// interval. Purely cosmetic — there's no real progress channel from the
// backend (the whole pipeline runs inside one synchronous request) — but it
// keeps the screen visibly alive instead of a silent spinner for a minute+.
function startAgentTicker() {
  let i = 0;
  _agentTickerId = setInterval(() => {
    i = (i + 1) % AGENT_MESSAGES.length;
    const el = document.getElementById('agent-label');
    if (el) el.textContent = AGENT_MESSAGES[i];
  }, 2200);
}

function stopAgentTicker() {
  if (_agentTickerId) {
    clearInterval(_agentTickerId);
    _agentTickerId = null;
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runGeneration() {
  const form = new FormData();
  form.append('inbody_file', window.tamrena.capturedBlob, 'scan.jpg');
  Object.entries(window.tamrena.intake).forEach(([k, v]) => {
    if (v !== undefined && v !== '') form.append(k, v);
  });

  try {
    const res = await fetch('/generate-plan', { method: 'POST', body: form });
    const data = await res.json();
    window.tamrena.result = data;
  } catch (err) {
    window.tamrena.result = { error: err.message };
  } finally {
    stopAgentTicker();
    markDone('agents');
    const label = document.getElementById('agent-label');
    if (label) label.textContent = 'Training protocol generated';
    await sleep(500); // let the user actually see the final checkmark before navigating away
    navigate('plan');
  }
}
