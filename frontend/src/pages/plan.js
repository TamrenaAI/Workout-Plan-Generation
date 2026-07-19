function renderPlan(container) {
  const result = window.tamrena.result;

  if (!result || result.error) {
    container.innerHTML = `
      <div class="t-screen" style="text-align:center;padding-top:80px;">
        <div style="font-size:32px;margin-bottom:16px;">⚠️</div>
        <h2 style="color:var(--danger);margin-bottom:8px;">Generation Failed</h2>
        <p style="color:var(--text-muted);">${result?.error || 'Unknown error'}</p>
        <button class="t-btn-ghost no-print" style="margin-top:32px;" onclick="navigate('capture')">Try Again</button>
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
          <div class="print-only" style="font-size:11px;color:#666;margin-top:6px;">
            Generated ${formatDate(result.generated_at)}
          </div>
        </div>
        <button onclick="window.print()" class="t-btn-ghost no-print"
          style="width:auto;height:36px;padding:0 16px;font-size:13px;">Download PDF</button>
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
        ${parsePlanToHtml(result.plan)}
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

// ── Plan markdown → structured HTML ───────────────────────────────────────────
// The agents write a fairly consistent markdown subset (### headings, **bold**
// labels, pipe tables, "- " bullet lists — see prompts/plan_assembler.md). This
// walks it line-by-line and renders each piece as real HTML — proper <table>
// elements for the sets/reps/rest/RPE data instead of dumping raw pipe-text
// into a <pre> block. That's what actually makes it print/PDF-friendly: browser
// print handles structured HTML far better than preformatted text, which tends
// to clip or overflow awkwardly on a page.
function parsePlanToHtml(markdown) {
  if (!markdown) return `<p style="color:var(--text-muted);">No plan generated.</p>`;

  const lines = markdown.split('\n');
  let html = '';
  let cardOpen = false;
  let i = 0;

  const closeCard = () => { if (cardOpen) { html += '</div>'; cardOpen = false; } };

  while (i < lines.length) {
    const line = lines[i];

    // Heading — "### Day 1 — Upper: Chest Focus" or "### Weekly Volume Summary".
    // The backend's memory file starts the schedule with its own "## Weekly
    // Schedule" (or "## Full Workout Plan") section marker — skip that one,
    // since the "Weekly Schedule" .t-section-title above is already rendered
    // by renderPlan() itself; rendering it again here would produce a
    // redundant, empty card.
    const heading = line.match(/^#{2,3}\s+(.*)/);
    if (heading) {
      const title = heading[1].trim();
      i++;
      if (/^(weekly schedule|full workout plan)$/i.test(title)) continue;
      closeCard();
      html += `<div class="t-card plan-card">`;
      html += `<div class="plan-card-title">${escapeHtml(title)}</div>`;
      cardOpen = true;
      continue;
    }

    // Pipe table — consume every consecutive "|"-prefixed line as one table
    if (line.trim().startsWith('|')) {
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        tableLines.push(lines[i]);
        i++;
      }
      html += renderPlanTable(tableLines);
      continue;
    }

    // "**Label:** text" — e.g. "**Warm-up:** ..." / "**Coaching notes:** ..."
    const boldLine = line.match(/^\*\*(.+?):\*\*\s*(.*)/);
    if (boldLine) {
      html += `<div class="plan-note"><span class="plan-note-label">${escapeHtml(boldLine[1])}:</span> ${escapeHtml(boldLine[2])}</div>`;
      i++;
      continue;
    }

    // Bullet list
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ''));
        i++;
      }
      html += `<ul class="plan-list">${items.map(it => `<li>${escapeHtml(it)}</li>`).join('')}</ul>`;
      continue;
    }

    // Horizontal rule / blank line — just section separators, no visible output
    if (/^-{3,}\s*$/.test(line.trim()) || !line.trim()) {
      i++;
      continue;
    }

    // Plain paragraph
    html += `<p class="plan-paragraph">${escapeHtml(line.trim())}</p>`;
    i++;
  }

  closeCard();
  return html || `<pre style="white-space:pre-wrap;color:var(--text-secondary);font-size:13px;line-height:1.7;">${escapeHtml(markdown)}</pre>`;
}

function renderPlanTable(tableLines) {
  const rows = tableLines
    .filter(l => !/^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$/.test(l)) // drop the "|---|---|" separator row
    .map(l => {
      const cells = l.split('|').map(c => c.trim());
      // drop the empty leading/trailing cells produced by a leading/trailing "|"
      if (cells[0] === '') cells.shift();
      if (cells[cells.length - 1] === '') cells.pop();
      return cells;
    });

  if (rows.length === 0) return '';
  const [header, ...body] = rows;

  return `
    <table class="exercise-table">
      <thead><tr>${header.map(h => `<th>${escapeHtml(h)}</th>`).join('')}</tr></thead>
      <tbody>${body.map(r => `<tr>${r.map(c => `<td>${escapeHtml(c)}</td>`).join('')}</tr>`).join('')}</tbody>
    </table>
  `;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
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

function formatDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}
