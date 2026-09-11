(() => {
  // FPP owns the outer document's theme. Plugin preferences must never change it.
  if (document.getElementById('fpp-wled-settings')) {
    document.querySelectorAll('[data-wled-theme]').forEach(select => {
      const note=document.createElement('p');note.className='text-body-secondary';
      note.textContent='Appearance follows FPP. Use FPP settings to change the page theme.';
      select.closest('p').replaceWith(note);
    });
    window.wledTheme={apply:()=>{},set:()=>{},toggle:()=>{}};
    return;
  }
  if (window.parent !== window && new URLSearchParams(location.search).has('embedded')) {
    document.documentElement.dataset.fppEmbedded='true';
    function inherit() {
      const root=parent.document.documentElement, style=parent.getComputedStyle(root);
      document.documentElement.dataset.bsTheme=root.dataset.bsTheme||'light';
      document.documentElement.style.colorScheme=root.dataset.bsTheme||'light';
      for(const name of ['body-bg','body-color','secondary-bg','tertiary-bg','secondary-color','border-color','primary','primary-bg-subtle','primary-text-emphasis','success-bg-subtle','success-text-emphasis','success-border-subtle','warning-bg-subtle','warning-text-emphasis','warning-border-subtle','link-color'])
        document.documentElement.style.setProperty('--bs-'+name,style.getPropertyValue('--bs-'+name));
    }
    inherit();new MutationObserver(inherit).observe(parent.document.documentElement,{attributes:true,attributeFilter:['data-bs-theme']});
    window.wledTheme={apply:inherit,set:()=>{},toggle:()=>{}};
    return;
  }
  const media = matchMedia('(prefers-color-scheme: dark)');
  const key = 'fpp-wled-appearance';
  let choice = 'dark', inherited = document.documentElement.dataset.bsTheme;
  try { choice = localStorage.getItem(key) || 'dark'; } catch {}
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
      button.setAttribute('aria-pressed', String(theme === 'dark'));
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
  window.addEventListener('storage', event => { if(event.key === key || event.key === null) { choice = event.newValue || 'dark'; apply(); } });
  if (location.pathname.startsWith('/fpp-wled/') || document.getElementById('fpp-wled-settings')) {
    fetch('/api/settings/themeOverride').then(r => r.ok ? r.json() : {}).then(setting => { inherited = setting.value || ''; apply(); }).catch(() => {});
  }
})();
