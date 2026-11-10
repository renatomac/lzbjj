/* Apply before paint so navigation never flashes the other theme. */
(() => {
  const key = 'crm-theme';
  const valid = value => value === 'dark' || value === 'light';
  function savedTheme() {
    try { const value = localStorage.getItem(key); if (valid(value)) return value; } catch (_) {}
    return 'light';
  }
  function apply(theme) {
    document.documentElement.dataset.bsTheme = theme;
    document.documentElement.style.colorScheme = theme;
    document.querySelectorAll('[data-theme-select]').forEach(select => { select.value = theme; });
  }
  apply(savedTheme());
  document.addEventListener('DOMContentLoaded', () => {
    apply(document.documentElement.dataset.bsTheme);
    document.querySelectorAll('[data-theme-select]').forEach(select => {
      select.addEventListener('change', () => {
        if (!valid(select.value)) return;
        apply(select.value);
        let message = 'Theme saved.';
        try { localStorage.setItem(key, select.value); }
        catch (_) { message = 'Theme applied. Browser storage is unavailable, so it may reset when you leave this page.'; }
        document.querySelectorAll('[data-theme-status]').forEach(status => { status.textContent = message; });
      });
    });
  });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) apply(savedTheme());
  });
})();
