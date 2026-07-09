function renderIntake(container) {
  // State held in the DOM — read values on submit
  container.innerHTML = `
    <div class="t-screen">
      <div style="margin-bottom:32px;">
        <div style="font-size:12px;color:var(--purple-light);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Step 1 of 2</div>
        <h1 style="font-size:28px;font-weight:700;">Hunter Profile</h1>
      </div>

      <!-- Goal -->
      <div style="margin-bottom:24px;">
        <span class="t-label">Training Goal</span>
        <div class="pill-group" id="goal-pills">
          <button class="pill active" data-value="hypertrophy">Hypertrophy</button>
          <button class="pill" data-value="strength">Strength</button>
          <button class="pill" data-value="fat_loss">Fat Loss</button>
          <button class="pill" data-value="general_fitness">General Fitness</button>
        </div>
      </div>

      <!-- Days per week -->
      <div style="margin-bottom:24px;">
        <span class="t-label">Days per Week</span>
        <div class="pill-group" id="days-pills">
          ${[2,3,4,5,6].map((d,i) => `
            <button class="pill ${i===2?'active':''}" data-value="${d}">${d} days</button>
          `).join('')}
        </div>
      </div>

      <!-- Experience -->
      <div style="margin-bottom:24px;">
        <span class="t-label">Experience Level</span>
        <div class="pill-group" id="exp-pills">
          <button class="pill active" data-value="beginner">Novice</button>
          <button class="pill" data-value="intermediate">Intermediate</button>
          <button class="pill" data-value="advanced">Advanced</button>
        </div>
      </div>

      <!-- Session duration -->
      <div style="margin-bottom:32px;">
        <span class="t-label">Session Duration</span>
        <div class="pill-group" id="dur-pills">
          <button class="pill active" data-value="45min">45 min</button>
          <button class="pill" data-value="60min">60 min</button>
          <button class="pill" data-value="90min">90 min</button>
        </div>
      </div>

      <!-- Optional section -->
      <div style="margin-bottom:32px;">
        <button class="t-btn-ghost" onclick="toggleOptional(this)" style="margin-bottom:12px;">
          + Optional Details
        </button>
        <div id="optional-fields" style="display:none;">
          <div style="display:flex;flex-direction:column;gap:12px;">
            ${optionalField('injuries', 'Injuries / Limitations', 'e.g. left knee, lower back')}
            ${optionalField('priority', 'Priority Muscle Group', 'e.g. back, legs')}
            ${optionalField('age', 'Age', '', 'number')}
            ${selectField('sleep_quality', 'Sleep Quality', ['Good (7-9h)', 'Average (5-7h)', 'Poor (<5h)'])}
            ${selectField('job_type', 'Job Type', ['Desk job', 'Active job', 'Standing job'])}
          </div>
        </div>
      </div>

      <button class="t-btn-primary" onclick="submitIntake()">Continue to Scan</button>
    </div>
  `;

  // Wire up pill groups
  ['goal','days','exp','dur'].forEach(id => {
    document.getElementById(`${id}-pills`).addEventListener('click', e => {
      const pill = e.target.closest('.pill');
      if (!pill) return;
      document.querySelectorAll(`#${id}-pills .pill`).forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
    });
  });
}

function optionalField(id, label, placeholder, type = 'text') {
  return `
    <div>
      <span class="t-label">${label}</span>
      <input id="field-${id}" type="${type}" placeholder="${placeholder}"
        style="width:100%;height:44px;background:var(--bg-input);border:1px solid var(--border-default);
               border-radius:10px;padding:0 14px;color:var(--text-primary);font-size:14px;outline:none;" />
    </div>
  `;
}

function selectField(id, label, options) {
  return `
    <div>
      <span class="t-label">${label}</span>
      <select id="field-${id}"
        style="width:100%;height:44px;background:var(--bg-input);border:1px solid var(--border-default);
               border-radius:10px;padding:0 14px;color:var(--text-primary);font-size:14px;outline:none;appearance:none;">
        <option value="">— optional —</option>
        ${options.map(o => `<option value="${o.toLowerCase().replace(/\s+/g,'_')}">${o}</option>`).join('')}
      </select>
    </div>
  `;
}

function toggleOptional(btn) {
  const el = document.getElementById('optional-fields');
  const hidden = el.style.display === 'none';
  el.style.display = hidden ? 'block' : 'none';
  btn.textContent = hidden ? '− Optional Details' : '+ Optional Details';
}

function submitIntake() {
  const getActive = id => document.querySelector(`#${id}-pills .pill.active`)?.dataset.value;
  const getField  = id => document.getElementById(`field-${id}`)?.value || undefined;

  window.tamrena.intake = {
    goal:             getActive('goal'),
    days_per_week:    parseInt(getActive('days')),
    experience:       getActive('exp'),
    session_duration: getActive('dur'),
    injuries:         getField('injuries'),
    priority:         getField('priority'),
    age:              getField('age') ? parseInt(getField('age')) : undefined,
    sleep_quality:    getField('sleep_quality'),
    job_type:         getField('job_type'),
  };

  navigate('capture');
}
