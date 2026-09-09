(() => {
  const media = matchMedia('(prefers-color-scheme: dark)');
  const key = 'fpp-wled-appearance';
  let choice = 'fpp', inherited = document.documentElement.dataset.bsTheme;
  try { choice = localStorage.getItem(key) || 'fpp'; } catch {}
  function apply() {
    const theme = ['light','dark'].includes(choice) ? choice : ['light','dark'].includes(inherited) ? inherited : media.matches ? 'dark' : 'light';
    document.documentElement.dataset.bsTheme = theme;
    document.documentElement.style.colorScheme = theme;
    document.querySelectorAll('[data-wled-theme]').forEach(select => { select.value = choice; });
    const button = document.getElementById('wled-theme-toggle');
    if (button) {
      const label = theme === 'dark' ? 'Switch to normal mode' : 'Switch to dark mode';
      button.title = label; button.setAttribute('aria-label', label);
      button.textContent = theme === 'dark' ? '\u2600' : '\u263e';
    }
  }
  function set(value) {
    choice = ['light','dark'].includes(value) ? value : 'fpp';
    try { localStorage.setItem(key, choice); } catch {}
    apply();
  }
  window.wledTheme = {set, apply, toggle:() => set(document.documentElement.dataset.bsTheme === 'dark' ? 'light' : 'dark')};
  function bind() { document.querySelectorAll('[data-wled-theme]').forEach(select => { select.onchange = () => set(select.value); }); apply(); }
  bind(); document.addEventListener('DOMContentLoaded', bind);
  media.addEventListener('change', apply);
  window.addEventListener('storage', event => { if(event.key === key) { choice = event.newValue || 'fpp'; apply(); } });
  if (location.pathname.startsWith('/fpp-wled/') || document.getElementById('fpp-wled-settings')) {
    fetch('/api/settings/themeOverride').then(r => r.ok ? r.json() : {}).then(setting => { inherited = setting.value || ''; apply(); }).catch(() => {});
  }
})();
