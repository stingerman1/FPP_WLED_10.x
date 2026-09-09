// Server-confirmed access state, shared by Settings tabs and browser restarts.
(() => {
  const byId = id => document.getElementById(id);
  async function refresh() {
    try {
      const response = await wledFetch('/api/auth');
      if (!response.ok) throw Error('Runtime access unavailable');
      const auth = await response.json();
      byId('loginFields').hidden = auth.authenticated;
      byId('logout').hidden = !auth.authenticated;
      byId('accessStatus').textContent = auth.authenticated
        ? 'Access saved on this browser. You do not need to enter a token again. It survives browser and runtime restarts.'
        : 'Read-only access. Enable lighting controls to make changes.';
      window.wledAuthenticated = auth.authenticated;
    } catch {
      byId('accessStatus').textContent = 'Cannot check access: runtime unavailable.';
      window.wledAuthenticated = false;
    }
  }
  window.refreshRuntimeAccess = refresh;
  byId('login').onclick = async () => {
    try {
      await post('/api/login', {}, byId('token').value);
      byId('token').value = '';
      await refresh();
    } catch { /* post displays the server error */ }
  };
  byId('logout').onclick = async () => {
    try { await post('/api/logout', {}); await refresh(); }
    catch { /* post displays the server error */ }
  };
  byId('connectRuntime').hidden = !wledOnFPP();
  byId('directAccessHelp').hidden = wledOnFPP();
  byId('connectRuntime').onclick = async () => {
    byId('connectRuntime').disabled = true;
    byId('accessStatus').textContent = 'Enabling lighting controls...';
    try { await wledEnableControls(); await refresh(); }
    catch (error) { byId('accessStatus').textContent = error.message; }
    finally { byId('connectRuntime').disabled = false; }
  };
  refresh();
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  setInterval(() => { if (!document.hidden) refresh(); }, 15000);
})();
