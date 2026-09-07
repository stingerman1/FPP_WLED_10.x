// Linux capability and ownership notice added alongside upstream WLED's UI.
(() => {
  for (const id of ['buttonNl', 'buttonSync', 'buttonSr']) {
    const button = document.getElementById(id);
    if (button) {
      button.disabled = true;
      button.title = 'Configure Linux schedules and UDP synchronization in Setup';
      button.style.opacity = '.4';
    }
  }
  for (const button of document.querySelectorAll('button')) {
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
  notice.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:9999;background:#222;color:#eee;padding:8px;text-align:center;font:14px sans-serif';
  document.body.append(notice);
  async function refresh() {
    try {
      const status = await (await fetch('/api/status')).json();
      notice.replaceChildren(document.createTextNode(status.allowed ? 'Linux alpha · Ambient active · ' : 'Linux alpha · Ambient suspended: ' + (status.sources.join(', ') || (!status.enabled ? 'disabled' : 'waiting for FPP / quiet period')) + ' · '));
      const link = document.createElement('a');
      link.href = '/settings'; link.textContent = 'Setup, login & compatibility'; link.style.color = '#9ddcff';
      notice.append(link);
    } catch { notice.textContent = 'Runtime unavailable'; }
  }
  refresh(); setInterval(refresh, 1000);
})();
