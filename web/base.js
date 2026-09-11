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
function wledStyleControls(root) {
  if (!document.getElementById('fpp-wled-settings')) return;
  root.querySelectorAll('button').forEach(button=>button.classList.add('btn','btn-outline-primary'));
  root.querySelectorAll('select').forEach(select=>select.classList.add('form-select'));
  root.querySelectorAll('input').forEach(input=>input.classList.add(input.type==='checkbox'?'form-check-input':'form-control'));
}
// Standalone WLED pages need a way back to the player's own navigation.
// Wrapped setup pages already have FPP's header and must not add a duplicate.
function wledAddFPPNavigation() {
  if (document.getElementById('fpp-wled-settings') || document.getElementById('fpp-navigation')) return;
  const menu = document.querySelector('#top .btnwrap') || document.querySelector('nav[aria-label="Setup sections"]');
  if (!menu) return;
  const link = document.createElement('a'), icon = document.createElement('img'), label = document.createElement('span');
  link.id = 'fpp-navigation'; link.title = 'Return to FPP'; link.setAttribute('aria-label', 'Return to FPP');
  icon.alt = ''; icon.width = 32; icon.height = 28; label.textContent = 'FPP';
  link.append(icon, label); menu.append(link);
  const target = new URL('/index.php', location.href);
  if (!wledOnFPP()) target.port = ''; // The renderer's port is not FPP's web port.
  function update() {
    link.href = target.href;
    icon.src = new URL('/images/redesign/fpp-logo.svg', target).href;
  }
  update();
  // Direct runtime access can use the advertised FPP HTTP port.
  if (!wledOnFPP()) wledFetch('/api/network').then(r => r.ok ? r.json() : {}).then(data => {
    const port = data.config?.discovery_http_port;
    if (Number.isInteger(port) && port > 0 && port <= 65535) { target.port = String(port); update(); }
  }).catch(() => {});
}
wledAddFPPNavigation();
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
