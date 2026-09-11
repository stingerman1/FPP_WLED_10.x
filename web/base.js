// Keep plugin requests on FPP's origin, while retaining direct runtime access.
// Collapse on a completed-state transition, not every background refresh.
// Users can reopen a completed section without the poll closing it again.
function wledSetupSection(id, complete) {
  const section = document.getElementById(id);
  if (!section) return;
  const state = complete ? 'complete' : 'attention';
  const linkedOnLoad = !section.dataset.setupState && location.hash === '#' + section.parentElement.id;
  if (section.dataset.setupState !== state) section.open = !complete || linkedOnLoad;
  section.dataset.setupState = state;
}
document.addEventListener('click', event => {
  const link = event.target.closest('a[href^="#"]');
  const target = link && document.getElementById(link.getAttribute('href').slice(1));
  const details = target?.querySelector(':scope > details.setup-disclosure');
  if (details) details.open = true;
});
function wledURL(path) {
  return (window.location.pathname.startsWith('/fpp-wled/') || document.getElementById('fpp-wled-settings') ? '/fpp-wled' : '') + path;
}
function wledSettingsURL(hash = '') {
  return location.pathname.startsWith('/fpp-wled/') ? '/plugin.php?plugin=FPP_WLED_10.x&page=settings.php' + hash : '/settings' + hash;
}
function wledFetch(path, options) {
  return window.fetch(wledURL(path), options);
}

function wledOnFPP() {
  return location.pathname.startsWith('/fpp-wled/') || !!document.getElementById('fpp-wled-settings');
}
// Explicit user action authorizes the browser; never persist the raw token in JS storage.
async function wledEnableControls() {
  if (!wledOnFPP()) throw Error('Open WLED through FPP to enable controls automatically, or enter your API token in Settings.');
  const response = await fetch('/plugin.php?plugin=FPP_WLED_10.x&page=runtime-token.php&nopage=1', {
    method: 'POST', headers: {'X-FPP-WLED-Action': 'retrieve-token'}, cache: 'no-store'
  });
  let data;
  try { data = await response.json(); } catch { throw Error('FPP token access is unavailable. Update the plugin and open it through FPP.'); }
  if (!response.ok) throw Error(data.error || 'FPP could not authorize this browser.');
  try {
    const login = await wledFetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json', Authorization:'Bearer ' + data.token}, body:'{}'});
    if (!login.ok) throw Error('Lighting runtime login failed. Check the runtime service and retry.');
  } finally { delete data.token; }
}
