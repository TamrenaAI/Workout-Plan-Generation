function renderHome(container) {
  container.innerHTML = `
    <div class="t-screen" style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;text-align:center;">
      <div style="margin-bottom:48px;">
        <div style="font-size:42px;font-weight:700;color:var(--accent-primary);letter-spacing:2px;">TAMRENA</div>
        <div style="font-size:13px;color:var(--text-muted);letter-spacing:6px;text-transform:uppercase;margin-top:4px;">AI Training System</div>
      </div>

      <p style="color:var(--text-secondary);font-size:16px;max-width:300px;line-height:1.6;margin-bottom:48px;">
        Your body. Your data. Your protocol.
      </p>

      <div style="width:100%;max-width:320px;">
        <button class="t-btn-primary" onclick="navigate('intake')">Begin Assessment</button>
      </div>

      <button class="t-btn-ghost" style="margin-top:16px;width:auto;padding:0 16px;font-size:12px;" onclick="navigate('workout-test')">Workout Feature Test</button>

      <div class="t-badge" style="margin-top:32px;">Hunter Rank System</div>
    </div>
  `;
}
