// Server-confirmed access state, shared by Settings tabs and browser restarts.
(() => {
  const byId = id => document.getElementById(id);
  function showAccess(allowed) {
    const known = allowed !== null;
    wledSetupSection('startDetails', allowed === true);
    wledSetupSection('accessDetails', allowed === true);
    byId('gettingStarted').classList.toggle('access-ready', allowed === true);
    byId('startAccessStatus').classList.toggle('enabled', allowed === true);
    byId('accessStatus').classList.toggle('enabled', allowed === true);
    byId('accessStatus').classList.add('access-indicator');
    byId('startAccessStatus').textContent = allowed === true ? 'Enabled — this browser can make changes.'
      : known ? 'Not enabled — this browser is view-only.' : 'Cannot check browser access. Check the plugin status in FPP, then reload this page.';
    byId('startReady').hidden = allowed !== true;
    byId('startGuide').hidden = allowed !== false;
    byId('loginFields').hidden = allowed !== false;
    byId('accessIntro').hidden = allowed !== false;
    byId('logout').hidden = allowed !== true;
    byId('disableAccessHelp').hidden = allowed !== true;
    byId('accessHeading').textContent = allowed === true ? 'This browser is allowed to make changes' : 'Browser lighting controls';
  }
  async function refresh() {
    try {
      const response = await wledFetch('/api/auth');
      if (!response.ok) throw Error('Runtime access unavailable');
      const auth = await response.json();
      showAccess(auth.authenticated);
      byId('accessStatus').textContent = auth.authenticated
        ? 'Enabled — access is saved on this browser.'
        : 'You can look at settings now. Click Enable lighting controls to change them.';
      window.wledAuthenticated = auth.authenticated;
    } catch {
      showAccess(null);
      byId('accessStatus').textContent = 'Cannot reach WLED. Check the plugin status in FPP, then reload this page.';
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
  byId('logout').onclick = byId('startLogout').onclick = async () => {
    byId('logout').disabled = byId('startLogout').disabled = true;
    try { await post('/api/logout', {}); await refresh(); }
    catch { /* post displays the server error */ }
    finally { byId('logout').disabled = byId('startLogout').disabled = false; }
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
