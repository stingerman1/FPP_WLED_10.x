// Linux capability and ownership notice added alongside upstream WLED's UI.
(() => {
  // ESP firmware reporting/upload paths do not apply to this Linux runtime.
  checkVersionUpgrade = () => {};
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
    nightlightButton.onclick = () => { location.href = wledURL('/settings#ambient-lighting'); };
    nightlightButton.title = 'Nightlight and lighting controls';
  }
  const peek = document.getElementById('buttonSr');
  if (peek) {
    peek.onclick = () => { location.href = wledURL('/settings#ambient-lighting'); };
    peek.title = 'Open ambient pixel preview';
  }
  for (const id of ['buttonSync']) {
    const button = document.getElementById(id);
    if (button) {
      button.disabled = true;
      button.title = 'Configure Linux schedules and UDP synchronization in Setup';
      button.style.opacity = '.4';
    }
  }
  for (const button of document.querySelectorAll('button')) {
    if (/\/cpal/.test(button.getAttribute('onclick') || '')) {
      button.onclick = () => { location.href = wledURL('/settings#custom-palettes'); };
      continue;
    }
    if (['updBt', 'resetbtn'].includes(button.id) ||
        /\/(edit|pixelforge|palette|cpal)/.test(button.getAttribute('onclick') || '')) {
      button.disabled = true;
      button.title = 'Unavailable in the Linux alpha; see Setup and compatibility';
      button.style.opacity = '.4';
    }
  }
  const style = document.createElement('style');
  style.textContent = '#rover button, #roverstar, #bsp {display:none!important}';
  document.head.append(style);
  const overlay = document.getElementById('rover');
  if (overlay) {
    overlay.replaceChildren();
    const message = document.createElement('p');
    message.id = 'lv';
    message.textContent = 'A show owns the managed outputs.';
    overlay.append(message, document.createTextNode('Ambient lighting resumes after all show sources end and the quiet period expires.'));
  }
  const notice = document.createElement('div');
  notice.id = 'linux-status-notice';
  notice.style.cssText = 'position:fixed;bottom:var(--bh,0px);left:0;right:0;z-index:9999;background:#222;color:#eee;padding:8px;text-align:center;font:14px sans-serif;pointer-events:none';
  document.body.append(notice);
  async function refresh() {
    try {
      const status = await (await wledFetch('/api/status')).json();
      notice.replaceChildren(document.createTextNode(status.allowed ? 'Linux alpha · Ambient active · ' : 'Linux alpha · Ambient suspended: ' + (status.sources.join(', ') || (!status.enabled ? 'disabled' : 'waiting for FPP / quiet period')) + ' · '));
      const link = document.createElement('a');
      link.href = wledURL('/settings'); link.textContent = 'Setup, login & compatibility'; link.style.cssText = 'color:#9ddcff;pointer-events:auto';
      notice.append(link);
    } catch { notice.textContent = 'Runtime unavailable'; }
  }
  refresh(); setInterval(refresh, 1000);
})();
