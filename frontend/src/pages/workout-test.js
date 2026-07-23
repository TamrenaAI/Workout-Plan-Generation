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
