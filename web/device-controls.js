(() => {
  const $ = id => document.getElementById(id);
  let devices = [], signature = '', sending = false;
  function actionFields() {
    $('deviceEffectLabel').hidden = $('deviceAction').value !== 'effect';
    $('devicePresetLabel').hidden = $('deviceAction').value !== 'preset';
  }
  $('deviceAction').onchange = actionFields;
  async function refresh() {
    try {
      const response = await wledFetch('/api/status');
      if (!response.ok) throw Error('Cannot check controller status.');
      const status = await response.json(); devices = status.devices;
      const next = JSON.stringify(devices.map(d => [d.id,d.mode,d.groups]));
      if (signature !== next) {
        signature = next;
        const chosen = $('deviceTarget').value, options = [];
        for (const device of devices) if (device.mode !== 'fpp-stream') options.push(new Option(device.id, device.id));
        for (const group of new Set(devices.flatMap(d => d.groups || []))) {
          if (devices.filter(d => d.groups.includes(group)).every(d => d.mode !== 'fpp-stream')) options.push(new Option('Group: ' + group, 'group:' + group));
        }
        $('deviceTarget').replaceChildren(...(options.length ? options : [new Option('Add a controller in Find devices, then save and apply setup', '')]));
        if (options.some(o => o.value === chosen)) $('deviceTarget').value = chosen;
      }
      $('applyDevice').disabled = sending || !status.allowed || !window.wledAuthenticated || !$('deviceTarget').value;
      $('deviceDelivery').replaceChildren();
      for (const d of devices) {
        const row = document.createElement('p');
        const state = d.mode === 'fpp-stream' ? 'Colors are sent by FPP' : d.last_command === 'sent'
          ? (d.mode === 'sync' ? 'Sync packet sent (delivery is not confirmed)' : 'Last command sent')
          : d.last_command === 'not probed' ? 'No command sent yet' : d.last_command;
        row.textContent = `${d.id} (${d.address}): ${state || 'Waiting'}${d.error ? ' — ' + d.error : ''}`;
        $('deviceDelivery').append(row);
      }
    } catch (error) { $('applyDevice').disabled = true; $('deviceDelivery').textContent = error.message; }
  }
  $('applyDevice').onclick = async () => {
    sending = true; $('applyDevice').disabled = true;
    const feedback = $('guidedDeviceFeedback'); feedback.textContent = 'Sending...';
    const abort = new AbortController(), timeout = setTimeout(() => abort.abort(), 15000);
    try {
      const target = $('deviceTarget').value, action = $('deviceAction').value;
      const chosen = devices.filter(d => target.startsWith('group:') ? d.groups.includes(target.slice(6)) : d.id === target);
      if (!chosen.length) throw Error('Choose a saved controller or group first.');
      let state;
      if (action === 'preset') {
        if (chosen.some(d => d.mode !== 'effect')) throw Error('Preset commands need Effects / presets mode for every selected controller.');
        const input = $('devicePreset');
        if (!input.value || !input.checkValidity()) throw Error('Enter a preset number from 1 to 250.');
        state = {ps:Number(input.value)};
      } else if (action === 'effect') state = {on:true,seg:{fx:Number($('deviceEffect').value)}};
      else state = {on:action === 'on'};
      const response = await wledFetch('/api/devices/command', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target,state}),signal:abort.signal});
      const result = await response.json();
      if (!response.ok) throw Error(result.error || 'Command not accepted.');
      feedback.textContent = 'Command queued for ' + result.accepted.join(', ') + '. Check delivery status below.';
    } catch (error) { feedback.textContent = error.name === 'AbortError' ? 'No reply yet. Check delivery status before trying again.' : error.message; }
    finally { clearTimeout(timeout); sending = false; refresh(); }
  };
  wledFetch('/json/effects').then(r => r.json()).then(names => {
    $('deviceEffect').replaceChildren(...names.flatMap((name,id) => name.startsWith('RSVD') ? [] : [new Option(name,id)]));
  }).catch(() => { $('deviceEffect').replaceChildren(new Option('Solid',0)); });
  refresh(); setInterval(() => { if (!document.hidden) refresh(); }, 3000);
})();
