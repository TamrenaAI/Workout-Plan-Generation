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
