(() => {
  if (document.getElementById('fpp-wled-settings')) return; // FPP wrapper owns it.
  const media = matchMedia('(prefers-color-scheme: dark)');
  let override = '';
  function apply() {
    const theme = ['light','dark'].includes(override) ? override : media.matches ? 'dark' : 'light';
    document.documentElement.dataset.bsTheme = theme;
    document.documentElement.style.colorScheme = theme;
  }
  apply(); media.addEventListener('change', apply);
  if (location.pathname.startsWith('/fpp-wled/')) {
    fetch('/api/settings/themeOverride').then(r => r.ok ? r.json() : {}).then(setting => {
      override = setting.value || ''; apply();
    }).catch(() => {});
  }
})();
