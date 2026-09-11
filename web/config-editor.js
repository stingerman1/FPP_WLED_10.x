(() => {
  const $ = id => document.getElementById(id);
  let mappings = [], devices = [], saved = null, restarting = false;
  const number = id => { const input = $(id); if (input.value === '' || !input.checkValidity()) throw Error('Check ' + input.parentElement.firstChild.textContent.trim() + '.'); return Number(input.value); };
  const report = message => { $('configFeedback').textContent = message; };
  async function state() {
    const response = await wledFetch('/api/config/status');
    if (!response.ok) throw Error('Cannot read saved setup. Check that the runtime is updated and running.');
    return response.json();
  }
  function field(row, label, value, change, options) {
    const wrap = document.createElement('label'); wrap.textContent = label + ' ';
    const input = document.createElement(options ? 'select' : 'input');
    if (options) for (const [value, text] of options) input.add(new Option(text, value));
    else input.type = typeof value === 'number' ? 'number' : 'text';
    input.value = value; input.oninput = () => change(input.type === 'number' ? (input.value === '' ? NaN : Number(input.value)) : input.value);
    wrap.append(input); row.append(wrap);
  }
  function rows(id, items, fields) {
    const container = $(id); container.replaceChildren();
    items.forEach((item, index) => {
      const row = document.createElement('fieldset'); row.className = 'setup-row';
      const legend = document.createElement('legend'); legend.textContent = (id === 'mappingRows' ? 'Mapping ' : 'Device ') + (index + 1); row.append(legend);
      for (const [key, label, options] of fields) field(row, label, key === 'groups' ? (item[key] || []).join(', ') : item[key], value => {
        item[key] = key === 'groups' ? value.split(',').map(x => x.trim()).filter(Boolean) : value;
      }, options);
      const remove = document.createElement('button'); remove.textContent = 'Remove ' + (id === 'mappingRows' ? 'mapping' : 'device');
      remove.onclick = () => { items.splice(index, 1); renderRows(); }; row.append(remove); container.append(row);
    });
    if (!items.length) container.textContent = 'None configured.';
  }
  function renderRows() {
    rows('mappingRows', mappings, [['pixel','First WLED pixel (starts at 0)'],['count','Pixel count'],['channel','First FPP channel']]);
    rows('deviceRows', devices, [['id','Nickname'],['address','Network address'],['mode','Control mode', [['effect','Effects / presets'],['sync','Sync'],['fpp-stream','FPP pixel streaming']]],['groups','Groups (comma separated)']]);
  }
  function pending(status) {
    $('configPending').textContent = status.restart_required ? 'Saved. Click 2. Apply setup and restart WLED to use these changes.' : 'Your saved setup is in use. No restart needed.';
    $('restartRuntime').disabled = restarting || !status.restart_available || !status.restart_required;
    if (!status.restart_available) $('configPending').textContent += ' Restart is available only under the updated FPP service.';
  }
  async function load() {
    const status = await state(); saved = status.saved;
    $('config').value = JSON.stringify(saved, null, 2);
    for (const [id, value] of Object.entries({cfgCount:saved.pixels.count,cfgChannels:saved.pixels.channels,cfgWidth:saved.pixels.width || saved.pixels.count,cfgHeight:saved.pixels.height || 1,cfgFps:saved.fps || 40})) $(id).value = value;
    mappings = structuredClone(saved.mappings); devices = structuredClone(saved.devices || []); renderRows(); pending(status);
  }
  $('addMapping').onclick = () => { mappings.push({pixel:0,count:1,channel:1}); renderRows(); };
  $('addDevice').onclick = () => { devices.push({id:'',address:'',mode:'effect',groups:[]}); renderRows(); };
  window.wledEnrollDevice = node => {
    if (!saved) { report('Setup is still loading. Try again in a moment.'); return; }
    if (devices.some(device => device.address === node.address)) {
      report('This address is already in your device list.');
    } else {
      const base = (node.name || 'wled').replace(/[^a-zA-Z0-9_-]/g,'-').slice(0,48) || 'wled';
      let id = base, index = 2;
      while (devices.some(device => device.id === id)) id = base + '-' + index++;
      devices.push({id,address:node.address,mode:'effect',groups:[]}); renderRows();
      report('Controller added to your draft. Choose its mode, then Save setup and Apply setup.');
    }
    $('deviceRows').scrollIntoView({block:'center'});
  };
  let layoutPreview = null;
  const chosenLayout = () => [...$('fppLayoutItems').querySelectorAll('input:checked')].map(input => Number(input.value));
  $('readFppLayout').onclick = async () => {
    layoutPreview = null; $('saveFppLayout').disabled = true;
    $('layoutFeedback').textContent = 'Reading FPP lights...';
    try {
      const response = await wledFetch('/api/layout');
      if (!response.ok) throw Error('Could not read FPP lights.');
      const result = await response.json(), models = result.items.some(item => item.kind === 'model');
      $('fppLayoutItems').replaceChildren();
      for (const item of result.items) {
        const label = document.createElement('label'), check = document.createElement('input');
        check.type = 'checkbox'; check.value = item.id; check.checked = models ? item.kind === 'model' : true;
        check.onchange = () => { layoutPreview = null; $('saveFppLayout').disabled = true; };
        label.append(check, document.createTextNode(' ' + item.name + ' (' + item.kind + ')')); $('fppLayoutItems').append(label);
      }
      $('previewFppLayout').disabled = !result.items.length;
      $('layoutFeedback').textContent = result.warnings.join('\n') || 'Choose your lights, then preview the layout.';
    } catch (error) { $('layoutFeedback').textContent = error.message; }
  };
  $('previewFppLayout').onclick = async () => {
    $('saveFppLayout').disabled = true; layoutPreview = null;
    try {
      const items = chosenLayout(), result = await post('/api/layout', {items,preview:true});
      layoutPreview = {items,revision:result.config.imported_layout.revision};
      $('layoutFeedback').textContent = result.segments.map(segment => `${segment.n}: ${segment.stop-segment.start} × ${segment.stopY-segment.startY} pixels`).join('\n') + '\n\n' + result.warnings.join('\n');
      $('saveFppLayout').disabled = false;
    } catch (error) { $('layoutFeedback').textContent = error.message; }
  };
  $('saveFppLayout').onclick = async () => {
    if (!layoutPreview) return;
    $('saveFppLayout').disabled = true;
    try {
      await post('/api/layout', {...layoutPreview,preview:false});
      await load(); layoutPreview = null;
      $('layoutFeedback').textContent = 'Layout saved. Click Apply setup below to use it.';
    } catch (error) { $('layoutFeedback').textContent = error.message; $('saveFppLayout').disabled = false; }
  };
  $('reloadConfig').onclick = () => load().then(() => report('Saved setup loaded.')).catch(error => report(error.message));
  $('saveGuided').onclick = async () => {
    $('saveGuided').disabled = true;
    try {
      if (!saved) throw Error('Load the saved setup first.');
      const latest = (await state()).saved; // Retain live network/timer changes made in other sections.
      const candidate = {...latest, pixels:{...latest.pixels,count:number('cfgCount'),channels:number('cfgChannels'),width:number('cfgWidth'),height:number('cfgHeight')},fps:number('cfgFps'),mappings,devices};
      await post('/api/config', candidate); await load(); report('');
    } catch (error) { report(error.message); }
    finally { $('saveGuided').disabled = false; }
  };
  $('save').onclick = async () => {
    $('save').disabled = true;
    try { await post('/api/config', JSON.parse($('config').value)); await load(); report(''); }
    catch (error) { report(error.message); }
    finally { $('save').disabled = false; }
  };
  $('restartRuntime').onclick = async () => {
    restarting = true; $('restartRuntime').disabled = true;
    try {
      const before = (await state()).started;
      await post('/api/runtime/restart', {}); report('Restart requested. Waiting for WLED to return...');
      for (let i = 0; i < 30; i++) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        try { if ((await state()).started !== before) { await load(); report('WLED restarted. Your saved setup is now in use.'); return; } } catch { /* reconnect during restart */ }
      }
      report('Runtime has not returned yet. Check the WLED service log in FPP, then reload this page.');
    } catch (error) { report(error.message); }
    finally { restarting = false; try { pending(await state()); } catch { /* leave restart disabled */ } }
  };
  load().catch(error => report(error.message));
  setInterval(async () => { if (!document.hidden && !restarting) { try { pending(await state()); } catch { $('configPending').textContent = 'Cannot reach WLED to check whether your setup is in use.'; $('restartRuntime').disabled = true; } } }, 5000);
})();
