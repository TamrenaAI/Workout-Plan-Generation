// ── Shared field helpers ──────────────────────────────────────────────────────

function stepHeader(step, total, title, subtitle) {
  return `
    <div style="margin-bottom:32px;">
      <div style="font-size:12px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">
        Step ${step} of ${total}${subtitle ? ' · ' + subtitle : ''}
      </div>
      <h1 style="font-size:28px;font-weight:700;">${title}</h1>
    </div>
  `;
}

// A <select> with a fixed option list plus an optional "Other" entry that
// reveals a free-text (or number) input for anything not in the list.
function dropdownField(id, label, options, config = {}) {
  const { otherType = 'none', otherPlaceholder = 'Type your own...', defaultValue } = config;
  const optsHtml = options.map(o =>
    `<option value="${o.value}" ${o.value === defaultValue ? 'selected' : ''}>${o.label}</option>`
  ).join('');
  const otherOptHtml = otherType !== 'none' ? `<option value="__other__">Other</option>` : '';
  const otherInputHtml = otherType !== 'none'
    ? `<input id="field-${id}-other" type="${otherType === 'number' ? 'number' : 'text'}"
         placeholder="${otherPlaceholder}" class="t-input" style="display:none;margin-top:8px;" />`
    : '';
  return `
    <div style="margin-bottom:24px;">
      <span class="t-label">${label}</span>
      <select id="field-${id}" class="t-select" ${otherType !== 'none' ? `onchange="toggleOtherInput('${id}')"` : ''}>
        ${optsHtml}
        ${otherOptHtml}
      </select>
      ${otherInputHtml}
    </div>
  `;
}

function toggleOtherInput(id) {
  const select = document.getElementById(`field-${id}`);
  const other = document.getElementById(`field-${id}-other`);
  if (!select || !other) return;
  other.style.display = select.value === '__other__' ? 'block' : 'none';
  if (select.value === '__other__') other.focus();
}

// Reads a dropdownField's resolved value — the selected option, or the
// free-text/number "Other" input if that's what was chosen.
function getDropdownValue(id, format) {
  const select = document.getElementById(`field-${id}`);
  if (!select) return undefined;
  if (select.value === '__other__') {
    const other = document.getElementById(`field-${id}-other`);
    const raw = other?.value?.trim();
    if (!raw) return undefined;
    return format ? format(raw) : raw;
  }
  return select.value || undefined;
}

// ── Step 1 — Goal + Days per week ─────────────────────────────────────────────

const GOAL_OPTIONS = [
  { value: 'hypertrophy',          label: 'Build Muscle (Hypertrophy)' },
  { value: 'strength',             label: 'Get Stronger (Strength)' },
  { value: 'fat loss',             label: 'Lose Fat' },
  { value: 'general fitness',      label: 'General Fitness / Health' },
  { value: 'athletic performance', label: 'Athletic Performance' },
  { value: 'endurance complement', label: 'Endurance Complement (Running / Cycling)' },
  { value: 'rehabilitation',       label: 'Rehab / Recovery' },
];

const DAYS_OPTIONS = [2, 3, 4, 5, 6].map(d => ({ value: String(d), label: `${d} days / week` }));

function renderIntake(container) {
  container.innerHTML = `
    <div class="t-screen">
      ${stepHeader(1, 4, 'Training Goal')}

      ${dropdownField('goal', 'What are you training for?', GOAL_OPTIONS, {
        defaultValue: 'hypertrophy', otherType: 'text', otherPlaceholder: 'Describe your goal...',
      })}
      ${dropdownField('days', 'Days per week', DAYS_OPTIONS, { defaultValue: '4' })}

      <button class="t-btn-primary" onclick="submitIntakeStep1()">Continue</button>
    </div>
  `;
}

function submitIntakeStep1() {
  saveIntake({
    goal: getDropdownValue('goal'),
    days_per_week: parseInt(getDropdownValue('days')),
  });
  navigate('intake-step2');
}

// ── Step 2 — Experience + Session duration ────────────────────────────────────

const EXPERIENCE_OPTIONS = [
  { value: 'beginner', label: 'Novice (0-1 year)' },
  { value: 'intermediate', label: 'Intermediate (1-3 years)' },
  { value: 'advanced', label: 'Advanced (3+ years)' },
];

const DURATION_OPTIONS = [
  { value: '45min', label: '45 minutes' },
  { value: '60min', label: '60 minutes' },
  { value: '75min', label: '75 minutes' },
  { value: '90min', label: '90 minutes' },
];

function renderIntakeStep2(container) {
  container.innerHTML = `
    <div class="t-screen">
      ${stepHeader(2, 4, 'Training Setup')}

      ${dropdownField('exp', 'Experience level', EXPERIENCE_OPTIONS, { defaultValue: 'intermediate' })}
      ${dropdownField('dur', 'Session duration', DURATION_OPTIONS, {
        defaultValue: '60min', otherType: 'number', otherPlaceholder: 'Minutes, e.g. 50',
      })}

      <button class="t-btn-primary" onclick="submitIntakeStep2()">Continue</button>
    </div>
  `;
}

function submitIntakeStep2() {
  saveIntake({
    experience: getDropdownValue('exp'),
    session_duration: getDropdownValue('dur', v => `${v}min`),
  });
  navigate('intake-optional');
}

// ── Step 3 — Optional details ─────────────────────────────────────────────────

const INJURY_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'knee', label: 'Knee' },
  { value: 'lower back', label: 'Lower back' },
  { value: 'shoulder', label: 'Shoulder' },
  { value: 'wrist or elbow', label: 'Wrist / Elbow' },
  { value: 'hip', label: 'Hip' },
];

const PRIORITY_OPTIONS = [
  { value: '', label: 'No priority' },
  { value: 'chest', label: 'Chest' },
  { value: 'back', label: 'Back' },
  { value: 'shoulders', label: 'Shoulders' },
  { value: 'arms', label: 'Arms' },
  { value: 'legs', label: 'Legs' },
];

const SLEEP_OPTIONS = [
  { value: '', label: '— skip —' },
  { value: 'good', label: 'Good (7-9h)' },
  { value: 'average', label: 'Average (5-7h)' },
  { value: 'poor', label: 'Poor (<5h)' },
];

const JOB_OPTIONS = [
  { value: '', label: '— skip —' },
  { value: 'desk', label: 'Desk job' },
  { value: 'light_physical', label: 'Light physical / on your feet' },
  { value: 'heavy_physical', label: 'Heavy physical / manual labor' },
];

function renderIntakeOptional(container) {
  container.innerHTML = `
    <div class="t-screen">
      ${stepHeader(3, 4, 'Extra Details', 'Optional')}
      <p style="color:var(--text-muted);font-size:14px;margin-bottom:24px;">
        Skip anything you don't want to share — these just help fine-tune the protocol.
      </p>

      ${dropdownField('injuries', 'Injuries / Limitations', INJURY_OPTIONS, {
        defaultValue: '', otherType: 'text', otherPlaceholder: 'Describe the injury / limitation...',
      })}
      ${dropdownField('priority', 'Priority muscle group', PRIORITY_OPTIONS, {
        defaultValue: '', otherType: 'text', otherPlaceholder: 'Describe what to prioritise...',
      })}
      ${dropdownField('sleep_quality', 'Sleep quality', SLEEP_OPTIONS, { defaultValue: '' })}
      ${dropdownField('job_type', 'Job type', JOB_OPTIONS, { defaultValue: '' })}

      <button class="t-btn-primary" onclick="submitIntakeOptional()">Continue to Scan</button>
    </div>
  `;
}

function submitIntakeOptional() {
  saveIntake({
    injuries: getDropdownValue('injuries'),
    priority: getDropdownValue('priority'),
    sleep_quality: getDropdownValue('sleep_quality'),
    job_type: getDropdownValue('job_type'),
  });
  navigate('capture');
}
