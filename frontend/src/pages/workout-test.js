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
