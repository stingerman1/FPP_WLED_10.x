(() => {
  const id = name => document.getElementById('network' + name);
  let loaded = false, refreshing = false, previousNodes = null;
  const refreshButton = document.getElementById('discover');
  const feedback = document.getElementById('discoveryFeedback');
  for (let group = 0; group < 8; group++) {
    const label = document.createElement('label'), input = document.createElement('input');
    input.type = 'checkbox'; input.value = 1 << group; input.checked = group === 0;
    label.append(input, document.createTextNode(' ' + (group + 1))); id('Groups').append(label);
  }
  async function refresh() {
    if (refreshing) return;
    refreshing = true;
    refreshButton.disabled = true;
    refreshButton.textContent = 'Checking discovered devices…';
    feedback.textContent = 'Checking background discovery results…';
    const abort = new AbortController();
    const timeout = setTimeout(() => abort.abort(), 10000);
    try {
      const response = await wledFetch('/api/network', {signal: abort.signal});
      if (!response.ok) throw Error(`Network settings unavailable (HTTP ${response.status})`);
      const status = await response.json(), config = status.config, udp = config.udp || {};
      if (!loaded) {
        id('Name').value = config.name || 'WLED for FPP';
        id('HttpPort').value = config.discovery_http_port || 80;
        for (const [name, value] of Object.entries({Discovery: !!config.discovery, Advertise: config.discoverable !== false,
          Sync: !!udp.enabled, Auto: udp.auto_peers !== false, Send: udp.send !== false, Receive: udp.receive !== false})) id(name).checked = value;
        id('Port').value = udp.port || 21324; id('Peers').value = (udp.peers || []).join(', ');
        id('Groups').querySelectorAll('input').forEach(input => input.checked = !!((udp.groups || 1) & Number(input.value)));
        loaded = true;
      }
      id('Status').textContent = `Discovery: ${status.discovery_active ? 'running' : 'off'} | Sync: ${status.sync_active ? 'running' : 'off'}\nPeers: ${status.peers.join(', ') || 'none yet'}\nSent: ${status.sent} | Received: ${status.received}` + (status.error ? '\nError: ' + status.error : '');
      const discoveryResponse = await wledFetch('/api/discovery', {signal: abort.signal});
      if (!discoveryResponse.ok) throw Error(`Discovery results unavailable (HTTP ${discoveryResponse.status})`);
      const nodes = await discoveryResponse.json(), list = document.getElementById('discovered');
      if (!Array.isArray(nodes)) throw Error('Runtime returned invalid discovery results');
      const signature = JSON.stringify(nodes.map(node => [node.address, node.name, node.url, node.enrolled, node.mode]).sort());
      const unchanged = signature === previousNodes;
      previousNodes = signature;
      list.replaceChildren();
      if (!nodes.length) list.textContent = status.discovery_active
        ? 'No devices found yet. Leave discovery running for at least a minute. Devices must be reachable on this network; multicast or broadcast filtering can prevent discovery.'
        : 'No discovered devices. Enable Discovery above and click Save discovery & sync. If it is already enabled, check the network status for an error.';
      for (const node of nodes) {
        const row = document.createElement('p'), link = document.createElement('a');
        link.textContent = node.name || node.address; link.href = node.url;
        row.append(link, document.createTextNode(` — ${node.address}${node.enrolled ? ' (enrolled: ' + node.mode + ')' : ''}`)); list.append(row);
      }
      feedback.textContent = `Checked ${new Date().toLocaleTimeString()}: ${nodes.length} device${nodes.length === 1 ? '' : 's'} found${unchanged ? ' — no changes' : ''}.`
        + (status.discovery_active ? '' : ' Discovery is off; any listed results may be outdated.');
    } catch (error) {
      feedback.textContent = 'Refresh failed: ' + (error.name === 'AbortError' ? 'runtime did not respond within 10 seconds.' : error.message)
        + ' Previous results, if any, have been kept. Try again.';
    } finally {
      clearTimeout(timeout);
      refreshing = false;
      refreshButton.disabled = false;
      refreshButton.textContent = 'Refresh discovered devices';
    }
  }
  document.getElementById('saveNetwork').onclick = async () => {
    const button = document.getElementById('saveNetwork'); button.disabled = true;
    try {
      const groups = [...id('Groups').querySelectorAll('input:checked')].reduce((mask, input) => mask | Number(input.value), 0);
      await post('/api/network', {name: id('Name').value, discovery: id('Discovery').checked,
        discoverable: id('Advertise').checked, discovery_http_port: Number(id('HttpPort').value),
        udp: {enabled: id('Sync').checked, auto_peers: id('Auto').checked,
          send: id('Send').checked, receive: id('Receive').checked, port: Number(id('Port').value), groups,
          peers: id('Peers').value.split(',').map(s => s.trim()).filter(Boolean)}});
      loaded = false;
      await refresh();
      const config = await (await wledFetch('/api/config')).json();
      document.getElementById('config').value = JSON.stringify(config, null, 2);
    } catch (error) { id('Status').textContent = error.message; }
    finally { button.disabled = false; }
  };
  document.getElementById('discover').onclick = refresh;
  refresh(); setInterval(() => { if (!document.hidden && !refreshing && !document.getElementById('saveNetwork').disabled) refresh(); }, 15000);
})();
