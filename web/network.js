(() => {
  const id = name => document.getElementById('network' + name);
  let loaded = false;
  for (let group = 0; group < 8; group++) {
    const label = document.createElement('label'), input = document.createElement('input');
    input.type = 'checkbox'; input.value = 1 << group; input.checked = group === 0;
    label.append(input, document.createTextNode(' ' + (group + 1))); id('Groups').append(label);
  }
  async function refresh() {
    try {
      const response = await wledFetch('/api/network');
      if (!response.ok) throw Error('Network settings unavailable');
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
      const nodes = await (await wledFetch('/api/discovery')).json(), list = document.getElementById('discovered');
      list.replaceChildren();
      if (!nodes.length) list.textContent = 'No instances found yet. Discovery can take up to a minute.';
      for (const node of nodes) {
        const row = document.createElement('p'), link = document.createElement('a');
        link.textContent = node.name || node.address; link.href = node.url;
        row.append(link, document.createTextNode(` — ${node.address}${node.enrolled ? ' (enrolled: ' + node.mode + ')' : ''}`)); list.append(row);
      }
    } catch (error) { id('Status').textContent = error.message; }
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
  refresh(); setInterval(() => { if (!document.hidden) refresh(); }, 5000);
})();
