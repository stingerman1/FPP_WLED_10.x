(() => {
  const byId = id => document.getElementById(id);
  const value = byId('wled-token-value');
  const result = byId('wled-token-result');
  const status = byId('wled-token-status');
  const get = byId('wled-get-token');
  const show = byId('wled-show-token');
  function clear() {
    value.value = '';
    value.type = 'password';
    show.textContent = 'Show token';
    result.hidden = true;
  }
  async function refreshAccess() {
    try {
      const response = await fetch('/fpp-wled/api/auth', {cache: 'no-store'});
      if (!response.ok) throw Error();
      const auth = await response.json();
      byId('wled-saved-access').textContent = auth.authenticated
        ? 'Runtime access is saved on this browser. WLED Settings is connected.'
        : 'Runtime access is not saved on this browser yet.';
    } catch { byId('wled-saved-access').textContent = 'Runtime access status unavailable.'; }
  }
  refreshAccess();
  window.addEventListener('focus', refreshAccess);
  setInterval(() => { if (!document.hidden) refreshAccess(); }, 15000);
  get.onclick = async () => {
    if (!window.confirm('This token permits lighting, preset and configuration changes. Retrieve the existing token from this FPP installation? Keep it private.')) return;
    clear();
    get.disabled = true;
    status.textContent = 'Retrieving token...';
    try {
      const response = await fetch('plugin.php?plugin=FPP_WLED_10.x&page=runtime-token.php&nopage=1', {
        method: 'POST', headers: {'X-FPP-WLED-Action': 'retrieve-token'}, cache: 'no-store'
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || 'Unable to retrieve the token.');
      value.value = data.token;
      result.hidden = false;
      status.textContent = 'Token retrieved. Copy it into Runtime access, or log in here for this browser.';
    } catch (error) { status.textContent = error.message; }
    finally { get.disabled = false; }
  };
  show.onclick = () => {
    value.type = value.type === 'password' ? 'text' : 'password';
    show.textContent = value.type === 'password' ? 'Show token' : 'Hide token';
  };
  byId('wled-copy-token').onclick = async () => {
    try {
      if (!navigator.clipboard) throw Error('Clipboard unavailable');
      await navigator.clipboard.writeText(value.value);
      status.textContent = 'Token copied. Keep it private.';
    } catch {
      value.type = 'text'; show.textContent = 'Hide token';
      value.focus(); value.select();
      status.textContent = 'Automatic copy is unavailable here. The token is selected; use Copy or Ctrl+C.';
    }
  };
  byId('wled-token-login').onclick = async () => {
    const button = byId('wled-token-login');
    button.disabled = true;
    try {
      const response = await fetch('/fpp-wled/api/login', {
        method: 'POST', headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + value.value}, body: '{}'
      });
      if (!response.ok) throw Error('Runtime login failed. Check that the runtime is running, then retrieve the token again.');
      clear();
      await refreshAccess();
      status.textContent = 'Access saved on this browser across restarts. WLED Settings will show your connected status.';
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  };
  byId('wled-clear-token').onclick = () => { clear(); status.textContent = 'Token cleared from this page. Existing logins remain active.'; };
  window.addEventListener('pagehide', clear);
})();
