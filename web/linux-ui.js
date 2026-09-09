// Linux capability and ownership notice added alongside upstream WLED's UI.
(() => {
  // ESP firmware reporting/upload paths do not apply to this Linux runtime.
  checkVersionUpgrade = () => {};
  // Use one persistent appearance preference across WLED and its settings.
  tglTheme = () => window.wledTheme.toggle();
  const oldTheme = document.querySelector('[onclick="tglTheme()"]');
  if (oldTheme) {
    const toggle = document.createElement('button');
    toggle.id = 'wled-theme-toggle'; toggle.type = 'button';
    toggle.onclick = tglTheme; oldTheme.replaceWith(toggle); window.wledTheme.apply();
  }
  // Upstream assumes each WS message is state/info. Handle the Linux API's
  // explicit rejection response before it reaches that state parser.
  function hookErrors() {
    if (!ws || ws.linuxErrors) return;
    ws.linuxErrors = true;
    const readMessage = ws.onmessage;
    ws.onmessage = event => {
      if (typeof event.data === 'string') {
        const value = JSON.parse(event.data);
        if (value.error) {
          clearTimeout(jsonTimeout);
          jsonTimeout = null;
          const safe = document.createElement('span');
          safe.textContent = value.message || 'Linux runtime rejected the command';
          showToast(safe.innerHTML, true);
          return;
        }
      }
      readMessage(event);
    };
  }
  const originalMakeWS = makeWS;
  makeWS = function () { originalMakeWS(); hookErrors(); };
  hookErrors();
  function disableBootOverride() {
    document.querySelectorAll('input[id$="bps"]').forEach(input => {
      input.checked = false;
      input.disabled = true;
      input.parentElement.style.pointerEvents = 'none';
      input.parentElement.title = 'Linux restores the interrupted ambient selection; boot preset overrides are unavailable';
      input.parentElement.style.opacity = '.4';
    });
  }
  new MutationObserver(disableBootOverride).observe(document.body, {childList:true, subtree:true});
  disableBootOverride();
  const nightlightButton = document.getElementById('buttonNl');
  if (nightlightButton) {
    nightlightButton.onclick = () => { location.href = wledSettingsURL('#ambient-lighting'); };
    nightlightButton.title = 'Nightlight and lighting controls';
  }
  const peek = document.getElementById('buttonSr');
  if (peek) {
    peek.onclick = () => { location.href = wledSettingsURL('#ambient-lighting'); };
    peek.title = 'Open ambient pixel preview';
  }
  const sync = document.getElementById('buttonSync');
  if (sync) {
    sync.onclick = () => { location.href = wledSettingsURL('#network'); };
    sync.title = 'Discovery and synchronization settings';
  }
  // Render network-supplied names as text; use advertised paths and avoid the
  // upstream unauthenticated remote toggle, which bypasses FPP ownership.
  populateNodes = (info, data) => {
    const panel = document.getElementById('kn');
    panel.replaceChildren();
    const heading = document.createElement('p');
    heading.textContent = 'Current instance: ' + info.name;
    panel.append(heading);
    for (const node of data.nodes || []) {
      const link = document.createElement('a');
      link.className = 'btn'; link.textContent = node.name || node.ip;
      link.href = node.url; link.style.display = 'block'; panel.append(link);
    }
    const setup = document.createElement('a');
    setup.href = wledSettingsURL('#network'); setup.textContent = 'Discovery and sync settings';
    panel.append(setup);
  };
  for (const button of document.querySelectorAll('button')) {
    if ((button.getAttribute('onclick') || '').includes("getURL('/settings')")) {
      button.onclick = () => { location.href = wledSettingsURL(); };
      continue;
    }
    if (/\/edit/.test(button.getAttribute('onclick') || '')) { button.title = 'Import and back up presets'; button.onclick = () => { location.href = wledSettingsURL('#preset-import'); }; continue; }
    if (/\/cpal/.test(button.getAttribute('onclick') || '')) {
      button.onclick = () => { location.href = wledSettingsURL('#custom-palettes'); };
      continue;
    }
    if (button.id === 'updBt') { button.textContent = 'Plugin updates & help'; button.onclick = () => { location.href = wledOnFPP() ? '/plugin.php?plugin=FPP_WLED_10.x&page=plugin.php' : wledSettingsURL('#compatibility'); }; continue; }
    if (['resetbtn'].includes(button.id) ||
        /\/(edit|pixelforge|palette|cpal)/.test(button.getAttribute('onclick') || '')) {
      button.disabled = true;
      button.title = 'Unavailable in the Linux alpha; see Setup and compatibility';
      button.style.opacity = '.4';
    }
  }
  const style = document.createElement('style');
  style.textContent = '#rover button, #roverstar, #bsp {display:none!important} #updBt {display:inline-block!important}';
  document.head.append(style);
  const overlay = document.getElementById('rover');
  if (overlay) {
    overlay.replaceChildren();
    const message = document.createElement('p');
    message.id = 'lv';
    message.textContent = 'A show owns the managed outputs.';
    overlay.append(message, document.createTextNode('Ambient lighting resumes after all show sources end and the quiet period expires.'));
  }
  const access = document.createElement('section');
  access.id = 'linux-access-notice';
  access.style.cssText = 'position:fixed;bottom:calc(var(--bh,0px) + 36px);left:0;right:0;z-index:10000;background:Canvas;color:CanvasText;padding:12px;text-align:center;border-top:1px solid GrayText';
  const accessText = document.createElement('p');
  accessText.textContent = 'Read-only access. Enable controls to change lighting, presets and configuration. Access is remembered on this browser.';
  const connect = document.createElement('button');
  connect.className = 'btn'; connect.textContent = 'Enable lighting controls';
  const accessLink = document.createElement('a');
  accessLink.href = wledSettingsURL('#runtime-access'); accessLink.textContent = 'Access settings';
  access.append(accessText, connect, document.createTextNode(' '), accessLink);
  document.body.prepend(access);
  connect.hidden = !wledOnFPP();
  async function refreshAccess() {
    try {
      const response = await wledFetch('/api/auth');
      if (!response.ok) throw Error();
      const auth = await response.json();
      access.hidden = auth.authenticated;
    } catch { access.hidden = false; accessText.textContent = 'Runtime access unavailable. Check the service, then retry.'; }
  }
  connect.onclick = async () => {
    connect.disabled = true;
    try { await wledEnableControls(); location.reload(); }
    catch (error) { accessText.textContent = error.message; connect.disabled = false; }
  };
  refreshAccess();
  window.addEventListener('focus', refreshAccess);
  setInterval(() => { if (!document.hidden) refreshAccess(); }, 15000);
  const notice = document.createElement('div');
  notice.id = 'linux-status-notice';
  notice.style.cssText = 'position:fixed;bottom:var(--bh,0px);left:0;right:0;z-index:9999;background:Canvas;color:CanvasText;padding:8px;text-align:center;font:14px sans-serif;pointer-events:none';
  document.body.append(notice);
  async function refresh() {
    try {
      const status = await (await wledFetch('/api/status')).json();
      notice.replaceChildren(document.createTextNode(status.allowed ? 'Linux alpha · Ambient active · ' : 'Linux alpha · Ambient suspended: ' + (status.sources.join(', ') || (!status.enabled ? 'disabled' : 'waiting for FPP / quiet period')) + ' · '));
      const link = document.createElement('a');
      link.href = wledSettingsURL(); link.textContent = 'Settings & access'; link.style.cssText = 'color:CanvasText;pointer-events:auto';
      notice.append(link);
    } catch { notice.textContent = 'Runtime unavailable'; }
  }
  refresh(); setInterval(refresh, 1000);
})();
