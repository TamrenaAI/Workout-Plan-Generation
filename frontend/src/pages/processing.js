const STEPS = [
  { id: 'validate', label: 'Image validated' },
  { id: 'extract', label: 'Analysing body composition' },
  { id: 'flags', label: 'Computing training flags' },
  { id: 'plan', label: 'Generating Training Protocol' },
];

function renderProcessing(container) {
  container.innerHTML = `
    <div class="t-screen" style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;text-align:center;">
      <div class="t-spinner"></div>
      <h2 style="font-size:20px;font-weight:600;margin-bottom:8px;">Building your protocol...</h2>
      <p style="color:var(--text-muted);font-size:13px;margin-bottom:40px;"></p>

      <div class="step-list" style="text-align:left;width:100%;max-width:280px;" id="steps">
        ${STEPS.map((s, i) => `
          <div class="step-item ${i === 0 ? 'active' : ''}" id="step-${s.id}">
            <div class="step-icon">${i === 0 ? '⟳' : ''}</div>
            <span>${s.label}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  // Simulate step progress (real progress comes from API response timing)
  animateSteps();
}

function animateSteps() {
  const delays = [0, 4000, 8000, 14000];  // approximate timing per stage
  STEPS.forEach((step, i) => {
    setTimeout(() => {
      const el = document.getElementById(`step-${step.id}`);
      if (!el) return;
      el.className = 'step-item done';
      el.querySelector('.step-icon').textContent = '✓';

      const next = STEPS[i + 1];
      if (next) {
        const nextEl = document.getElementById(`step-${next.id}`);
        if (nextEl) {
          nextEl.className = 'step-item active';
          nextEl.querySelector('.step-icon').textContent = '⟳';
        }
      }
    }, delays[i]);
  });
}
