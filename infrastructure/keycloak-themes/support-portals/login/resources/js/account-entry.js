// Use Keycloak's own fresh-account action before asking for a password.
// This restarts only this authentication attempt; it does not log out portal sessions.
document.addEventListener('DOMContentLoaded', () => {
  const reset = document.getElementById('reset-login');
  if (!reset) return;
  reset.click();
});
