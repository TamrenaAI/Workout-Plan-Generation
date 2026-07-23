// Manual test harness for the workout-feedback and monthly-progress-review
// endpoints (POST /workouts/{id}/feedback, POST /plan/{id}/monthly-review,
// GET /progress/{id}/report) — none of which the normal intake wizard flow
// ever exercises. Reachable at #workout-test, independent of the wizard's
// window.tamrena.intake/capturedBlob state so it works against ANY session,
// including ones backdated directly in MongoDB to test review eligibility.

let _wtSessions = [];

function renderWorkoutTest(container) {
  container.innerHTML = `
    <div class="t-screen">
      <h1 style="font-size:28px;font-weight:700;margin-bottom:4px;">Workout Feature Test</h1>
      <p style="color:var(--text-muted);font-size:13px;margin-bottom:24px;">
        Manual test harness for feedback, monthly review, and progress reports.
      </p>
      <div id="wt-sessions"><p style="color:var(--text-muted);">Loading sessions…</p></div>
      <div id="wt-panel"></div>
    </div>
  `;
  loadSessions();
}

async function loadSessions() {
  const el = document.getElementById('wt-sessions');
  try {
    const token = await ensureAuthToken();
    const res = await fetch('/sessions', { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(`Failed to load sessions (${res.status})`);
    const data = await res.json();
    _wtSessions = data.sessions || [];
    renderSessionList(el);
  } catch (err) {
    el.innerHTML = `<div class="t-card" style="border-color:var(--danger);"><p style="color:var(--danger);">${escapeHtml(err.message)}</p></div>`;
  }
}

function renderSessionList(el) {
  if (_wtSessions.length === 0) {
    el.innerHTML = `<p style="color:var(--text-muted);">No sessions yet.</p>`;
    return;
  }
  el.innerHTML = _wtSessions.map(s => `
    <div class="t-card" style="margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <span style="font-weight:600;">${escapeHtml(s.goal || '—')}</span>
        <span class="t-badge">${escapeHtml(s.status)}</span>
      </div>
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px;">
        ${escapeHtml(s.session_id)} · ${formatDate(s.created_at)}
        ${s.eligible_for_review ? '<span class="t-badge success" style="margin-left:6px;">Review Eligible</span>' : ''}
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button class="t-btn-ghost" style="width:auto;padding:0 12px;" onclick="openFeedbackForm('${s.session_id}')">Submit Feedback</button>
        <button class="t-btn-ghost" style="width:auto;padding:0 12px;" ${s.eligible_for_review ? '' : 'disabled title="Not eligible: status must be ready, 30+ days old, and not already reviewed"'} onclick="openMonthlyReviewForm('${s.session_id}')">Start Monthly Review</button>
        <button class="t-btn-ghost" style="width:auto;padding:0 12px;" onclick="openProgressReport('${s.session_id}')">View Progress Report</button>
      </div>
    </div>
  `).join('');
}

// ── Feedback form ─────────────────────────────────────────────────────────────

let _wtParsedDays = [];

async function openFeedbackForm(sessionId) {
  const panel = document.getElementById('wt-panel');
  panel.innerHTML = `<div class="t-card" style="margin-top:24px;"><p style="color:var(--text-muted);">Loading plan…</p></div>`;
  try {
    const token = await ensureAuthToken();
    const res = await fetch(`/sessions/${sessionId}/plan`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(`Failed to load plan (${res.status})`);
    const data = await res.json();
    if (data.status !== 'ready' || !data.plan) {
      panel.innerHTML = `<div class="t-card" style="margin-top:24px;"><p style="color:var(--text-muted);">Plan not ready yet for this session (status: ${escapeHtml(data.status)}).</p></div>`;
      return;
    }
    panel.innerHTML = `<div class="t-section-title" style="margin-top:24px;margin-bottom:12px;">Submit Feedback</div>` + renderFeedbackDays(sessionId, data.plan);
  } catch (err) {
    panel.innerHTML = `<div class="t-card" style="border-color:var(--danger);margin-top:24px;"><p style="color:var(--danger);">${escapeHtml(err.message)}</p></div>`;
  }
}

// Reuses plan.js's existing parsePlanToHtml (the one and only markdown parser in
// this frontend) rather than writing a second one — renders it into a detached
// element and reads day titles / exercise names back out via DOM queries.
function parsePlanIntoDays(markdown) {
  const wrapper = document.createElement('div');
  wrapper.innerHTML = parsePlanToHtml(markdown);
  const days = [];
  wrapper.querySelectorAll('.plan-card').forEach(card => {
    const titleEl = card.querySelector('.plan-card-title');
    const title = titleEl ? titleEl.textContent : '';
    if (!/^day\s+\d+/i.test(title)) return; // skip non-day sections like "Weekly Volume Summary"
    const table = card.querySelector('.exercise-table');
    if (!table) return;
    const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent);
    const exerciseCol = headers.findIndex(h => /exercise/i.test(h));
    if (exerciseCol === -1) return;
    const exercises = Array.from(table.querySelectorAll('tbody tr'))
      .map(tr => {
        const cells = tr.querySelectorAll('td');
        return cells[exerciseCol] ? cells[exerciseCol].textContent : null;
      })
      .filter(Boolean);
    if (exercises.length > 0) days.push({ title, exercises });
  });
  return days;
}

function renderFeedbackDays(sessionId, planMarkdown) {
  _wtParsedDays = parsePlanIntoDays(planMarkdown);
  if (_wtParsedDays.length === 0) {
    return `<div class="t-card"><p style="color:var(--text-muted);">No day sections found in this plan.</p></div>`;
  }
  return _wtParsedDays.map((day, dayIndex) => `
    <div class="t-card" style="margin-bottom:12px;">
      <div class="plan-card-title">${escapeHtml(day.title)}</div>
      <table class="exercise-table" style="margin-bottom:12px;">
        <thead><tr><th>Exercise</th><th>Too easy</th><th>Just right</th><th>Too hard</th><th>Pain</th></tr></thead>
        <tbody>
          ${day.exercises.map((name, exIndex) => `
            <tr>
              <td>${escapeHtml(name)}</td>
              <td style="text-align:center;"><input type="radio" name="wt-diff-${dayIndex}-${exIndex}" value="too_easy"></td>
              <td style="text-align:center;"><input type="radio" name="wt-diff-${dayIndex}-${exIndex}" value="just_right" checked></td>
              <td style="text-align:center;"><input type="radio" name="wt-diff-${dayIndex}-${exIndex}" value="too_hard"></td>
              <td style="text-align:center;"><input type="checkbox" id="wt-pain-${dayIndex}-${exIndex}"></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <button class="t-btn-ghost" style="width:auto;padding:0 12px;" onclick="submitFeedbackForDay('${sessionId}', ${dayIndex})">Submit feedback for this day</button>
      <div id="wt-feedback-result-${dayIndex}" style="margin-top:10px;"></div>
    </div>
  `).join('');
}

async function submitFeedbackForDay(sessionId, dayIndex) {
  const day = _wtParsedDays[dayIndex];
  const exercises = day.exercises.map((name, exIndex) => {
    const diffInput = document.querySelector(`input[name="wt-diff-${dayIndex}-${exIndex}"]:checked`);
    const painInput = document.getElementById(`wt-pain-${dayIndex}-${exIndex}`);
    return {
      name,
      difficulty: diffInput ? diffInput.value : 'just_right',
      pain: !!(painInput && painInput.checked),
    };
  });

  const resultEl = document.getElementById(`wt-feedback-result-${dayIndex}`);
  resultEl.innerHTML = `<p style="color:var(--text-muted);">Submitting…</p>`;
  try {
    const token = await ensureAuthToken();
    const res = await fetch(`/workouts/${sessionId}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ day_label: day.title, exercises }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.detail ? String(data.detail) : `Server returned ${res.status}`);
    resultEl.innerHTML = `
      <span class="t-badge ${data.adjustment_triggered ? 'warning' : 'success'}">
        ${data.adjustment_triggered ? 'Adjustment triggered' : 'No adjustment needed'}
      </span>
      ${data.summary ? `<p style="margin-top:8px;font-size:13px;color:var(--text-secondary);">${escapeHtml(data.summary)}</p>` : ''}
    `;
  } catch (err) {
    resultEl.innerHTML = `<p style="color:var(--danger);">${escapeHtml(err.message)}</p>`;
  }
}

// ── Monthly review form ────────────────────────────────────────────────────────

let _wtSameGoal = true;
let _wtSampleInbodyFile = null;

function openMonthlyReviewForm(sessionId) {
  const panel = document.getElementById('wt-panel');
  _wtSameGoal = true;
  _wtSampleInbodyFile = null;
  panel.innerHTML = `
    <div class="t-card" style="margin-top:24px;">
      <div class="t-section-title" style="margin-bottom:16px;">Start Monthly Review</div>
      <div style="margin-bottom:16px;">
        <span class="t-label">Same goal as before?</span>
        <div class="pill-group">
          <button type="button" class="pill active" id="wt-same-goal-yes" onclick="setSameGoal(true)">Same goal</button>
          <button type="button" class="pill" id="wt-same-goal-no" onclick="setSameGoal(false)">Goal changed</button>
        </div>
      </div>
      <div id="wt-intake-fields" style="display:none;">
        ${dropdownField('wt-goal', 'Goal', GOAL_OPTIONS, { defaultValue: 'hypertrophy', otherType: 'text' })}
        ${dropdownField('wt-days', 'Days per week', DAYS_OPTIONS, { defaultValue: '4' })}
        ${dropdownField('wt-exp', 'Experience', EXPERIENCE_OPTIONS, { defaultValue: 'intermediate' })}
        ${dropdownField('wt-dur', 'Session duration', DURATION_OPTIONS, { defaultValue: '60min', otherType: 'number' })}
        ${dropdownField('wt-injuries', 'Injuries', INJURY_OPTIONS, { defaultValue: '', otherType: 'text' })}
        ${dropdownField('wt-priority', 'Priority', PRIORITY_OPTIONS, { defaultValue: '', otherType: 'text' })}
        ${dropdownField('wt-sleep', 'Sleep quality', SLEEP_OPTIONS, { defaultValue: '' })}
        ${dropdownField('wt-job', 'Job type', JOB_OPTIONS, { defaultValue: '' })}
      </div>
      <div style="margin-bottom:16px;">
        <span class="t-label">InBody scan</span>
        <input type="file" id="wt-inbody-file" accept="image/*,application/pdf" class="t-input" style="padding:8px;height:auto;" onchange="clearSampleInbody()" />
        <button type="button" class="t-btn-ghost" style="margin-top:8px;" onclick="useSampleInbody()">Use sample image</button>
        <div id="wt-inbody-status" style="font-size:12px;color:var(--text-muted);margin-top:6px;"></div>
      </div>
      <button class="t-btn-primary" id="wt-monthly-review-submit" onclick="submitMonthlyReview('${sessionId}')">Start Review</button>
      <div id="wt-monthly-review-result" style="margin-top:12px;"></div>
    </div>
  `;
}

function setSameGoal(same) {
  _wtSameGoal = same;
  document.getElementById('wt-same-goal-yes').classList.toggle('active', same);
  document.getElementById('wt-same-goal-no').classList.toggle('active', !same);
  document.getElementById('wt-intake-fields').style.display = same ? 'none' : 'block';
}

async function useSampleInbody() {
  const status = document.getElementById('wt-inbody-status');
  status.textContent = 'Loading sample image…';
  try {
    const res = await fetch('/media/samples/inbody3.jfif');
    if (!res.ok) throw new Error(`Failed to load sample image (${res.status})`);
    const blob = await res.blob();
    _wtSampleInbodyFile = new File([blob], 'inbody3.jfif', { type: blob.type || 'image/jpeg' });
    document.getElementById('wt-inbody-file').value = '';
    status.textContent = 'Sample image attached (inbody3.jfif).';
  } catch (err) {
    status.textContent = err.message;
  }
}

function clearSampleInbody() {
  _wtSampleInbodyFile = null;
  document.getElementById('wt-inbody-status').textContent = '';
}

async function submitMonthlyReview(sessionId) {
  const fileInput = document.getElementById('wt-inbody-file');
  const file = fileInput.files[0] || _wtSampleInbodyFile;
  const resultEl = document.getElementById('wt-monthly-review-result');

  if (!file) {
    resultEl.innerHTML = `<p style="color:var(--danger);">Attach an InBody file or click "Use sample image" first.</p>`;
    return;
  }

  const form = new FormData();
  form.append('same_goal', String(_wtSameGoal));
  form.append('inbody_file', file, file.name);

  if (!_wtSameGoal) {
    form.append('goal', getDropdownValue('wt-goal'));
    form.append('days_per_week', getDropdownValue('wt-days'));
    form.append('experience', getDropdownValue('wt-exp'));
    form.append('session_duration', getDropdownValue('wt-dur', v => `${v}min`));
    const optional = {
      injuries: getDropdownValue('wt-injuries'),
      priority: getDropdownValue('wt-priority'),
      sleep_quality: getDropdownValue('wt-sleep'),
      job_type: getDropdownValue('wt-job'),
    };
    Object.entries(optional).forEach(([k, v]) => { if (v) form.append(k, v); });
  }

  resultEl.innerHTML = `<p style="color:var(--text-muted);">Submitting…</p>`;
  document.getElementById('wt-monthly-review-submit').disabled = true;

  try {
    const token = await ensureAuthToken();
    const res = await fetch(`/plan/${sessionId}/monthly-review`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      let message = `Server returned ${res.status}`;
      if (typeof data?.detail === 'string') message = data.detail;
      else if (Array.isArray(data?.detail)) message = data.detail.map(e => `${e.loc?.at(-1)}: ${e.msg}`).join(', ');
      throw new Error(message);
    }

    window.tamrena.result = { session_id: data.session_id, inbody: data.inbody };
    window.tamrena.resumeStreamSessionId = data.session_id;
    navigate('processing');
  } catch (err) {
    resultEl.innerHTML = `<p style="color:var(--danger);">${escapeHtml(err.message)}</p>`;
    document.getElementById('wt-monthly-review-submit').disabled = false;
  }
}
