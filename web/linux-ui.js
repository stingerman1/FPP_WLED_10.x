// Linux capability and ownership notice added alongside upstream WLED's UI.
(() => {
  // ESP firmware reporting/upload paths do not apply to this Linux runtime.
  checkVersionUpgrade = () => {};
  // Keep upstream tooltips within the viewport, including top-bar controls.
  document.addEventListener('pointerover', event => {
    const tip=document.querySelector('.tooltip.visible');
    if(!tip)return;
    const control=event.target.closest('[data-title]')||event.target;
    const rect=control.getBoundingClientRect(), box=tip.getBoundingClientRect();
    const below=rect.top-box.height-10<8;
    tip.toggleAttribute('data-below',below);
    tip.style.top=Math.max(8,Math.min(innerHeight-box.height-8,below?rect.bottom+10:rect.top-box.height-10))+'px';
    tip.style.left=Math.max(8,Math.min(innerWidth-box.width-8,rect.left+(rect.width-box.width)/2))+'px';
  });
  // A palette selection seeds the editable effect slots. Keep the full palette
  // until the user edits a slot, then use WLED's native three-color gradient.
  function profileColors(id) {
    const stops = palettesData?.[id];
    if (!stops?.length || !stops.every(Array.isArray)) return null;
    const sample = position => {
      let left = stops[0], right = stops[stops.length - 1];
      for (const stop of stops) {
        if (stop[0] <= position) left = stop;
        if (stop[0] >= position) { right = stop; break; }
      }
      const amount = right[0] === left[0] ? 0 : Math.max(0, Math.min(1, (position-left[0])/(right[0]-left[0])));
      return [1,2,3].map(channel => Math.round(left[channel]+amount*(right[channel]-left[channel]))).concat(0);
    };
    // Palette 4 runs third -> background -> primary, preserving this order
    // when the user starts editing the three representative colors.
    return [sample(255), sample(128), sample(0)];
  }
  function lightingRequest(action, transform) {
    const send = requestJson;
    requestJson = function (body, ...args) { return send.call(this, transform(body), ...args); };
    try { return action(); } finally { requestJson = send; }
  }
  const nativeSetPalette = setPalette;
  setPalette = function (...args) {
    return lightingRequest(() => nativeSetPalette.apply(this, args), body => {
      const colors = profileColors(body?.seg?.pal);
      return colors ? {...body, seg:{...body.seg, col:colors}} : body;
    });
  };
  const nativeSetColor = setColor;
  setColor = function (...args) {
    return lightingRequest(() => nativeSetColor.apply(this, args), body =>
      body?.seg?.col && (selectedPal === 0 || selectedPal === 1 || selectedPal > 5)
        ? {...body, seg:{...body.seg, pal:4}} : body);
  };
  let previewRevision, refreshingPreviews = false;
  const nativeParseInfo = parseInfo;
  parseInfo = function (info) {
    nativeParseInfo(info);
    if (previewRevision === undefined) { previewRevision = info.palrev; return; }
    if (previewRevision === info.palrev || refreshingPreviews || !palettesData) return;
    refreshingPreviews = true;
    wledFetch('/api/palettes').then(async response => {
      if (!response.ok) throw Error('Could not refresh custom palettes');
      const data = await response.json();
      // Replace custom previews, including removed slots; keep built-in data.
      for (const id of Object.keys(palettesData)) if (Number(id) <= 200 && !lJson.some(palette => palette[0] === Number(id))) delete palettesData[id];
      Object.assign(palettesData, data.previews);
      previewRevision = info.palrev;
      populatePalettes(); redrawPalPrev(); updateSelectedPalette(selectedPal);
    }).catch(() => {}).finally(() => { refreshingPreviews = false; });
  };
  // Keep WLED's native power control, but name its next action explicitly.
  const nativeUpdateUI = updateUI;
  updateUI = function (...args) {
    const result = nativeUpdateUI.apply(this, args);
    const button = document.getElementById('buttonPower');
    const label = isOn ? 'Turn off' : 'Turn on';
    button.querySelector('.tab-label').textContent = label;
    button.title = label; button.setAttribute('aria-label', label);
    return result;
  };
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
  let savingPreset = false;
  window.wledSavePreset = async payload => {
    if (savingPreset) return;
    savingPreset = true;
    let feedback = document.getElementById('linux-preset-feedback');
    if (!feedback) {
      feedback = document.createElement('p'); feedback.id = 'linux-preset-feedback';
      feedback.setAttribute('role', 'status'); document.getElementById('putil').prepend(feedback);
    }
    feedback.textContent = 'Saving...';
    const abort = new AbortController(), timeout = setTimeout(() => abort.abort(), 15000);
    let acknowledged = false;
    try {
      const response = await wledFetch('/json/state', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload), signal:abort.signal});
      const reply = await response.json();
      if (!response.ok || reply.success !== true) throw Error(reply.error || 'The change was not accepted. Enable lighting controls and try again.');
      acknowledged = true;
      const catalog = await wledFetch('/presets.json', {cache:'no-store', signal:abort.signal});
      if (!catalog.ok) throw Error('Could not refresh the preset list.');
      pJson = await catalog.json(); populatePresets(); resetPUtil();
      showToast(payload.pdel ? 'Preset deleted.' : 'Preset saved.');
    } catch (error) {
      feedback.textContent = (acknowledged ? 'The change was saved, but the list could not refresh. Reload WLED. ' : 'Your draft is still here. ')
        + (error.name === 'AbortError' ? 'The request timed out; check saved presets before retrying.' : error.message);
    } finally { clearTimeout(timeout); savingPreset = false; }
  };
  // Linux status includes changing uptime/output counters. Upstream rebuilds
  // segments on every state/info message and resets the new-segment form.
  // Keep its actual DOM (including focus and drafts) through background updates.
  let updatingSegments = false;
  let lastSegmentView = null;
  const segmentEdits = new Map();
  document.addEventListener('input', event => {
    const input = event.target;
    if (input.matches('#segcont input.ptxt, #segcont input.segn')) segmentEdits.set(input.id, input.value);
  });
  const originalPopulateSegments = populateSegments;
  const originalResetUtil = resetUtil;
  resetUtil = function (...args) {
    if (updatingSegments && document.querySelector('#segutil input.ptxt')) return;
    return originalResetUtil.apply(this, args);
  };
  populateSegments = function (state) {
    // Uptime/ownership notifications must not recreate unchanged input fields.
    const view = JSON.stringify([state.seg, state.ledmap, isM, mw, mh, ledCount, maxSeg, cfg.comp, simplifiedUI, lastinfo.maps]);
    if (view === lastSegmentView) return;
    const focus = document.activeElement;
    const focusedId = focus?.id;
    const selection = focus?.type === 'text' ? [focus.selectionStart, focus.selectionEnd] : null;
    const draft = document.querySelector('#segutil input.ptxt');
    const draftId = draft ? Number(draft.id.match(/^seg(\d+)t$/)[1]) : null;
    // Another client may have used the same slot. Do not leave duplicate IDs
    // in the page or let this draft overwrite that client's new segment.
    if (draft && (state.seg || []).some(segment => segment.id === draftId)) {
      originalResetUtil();
      showToast('The segment list changed on another controller. Please add your segment again.', true);
    }
    updatingSegments = true;
    try {
      const result = originalPopulateSegments.call(this, state);
      lastSegmentView = view;
      for (const [id, value] of segmentEdits) {
        const input = document.getElementById(id);
        if (input) {
          input.value = value;
          if (input.classList.contains('ptxt')) input.classList.add('show');
        }
        else segmentEdits.delete(id); // a segment removed by another client
      }
      const replacement = document.getElementById(focusedId);
      if (replacement && replacement !== focus && segmentEdits.has(focusedId)) {
        replacement.focus({preventScroll:true});
        if (selection) replacement.setSelectionRange(...selection);
      }
      return result;
    }
    finally { updatingSegments = false; }
  };
  const originalSetSeg = setSeg;
  setSeg = function (id) {
    const input = suffix => document.getElementById(`seg${id}${suffix}`);
    // Validate only when applying, allowing empty/partial numbers while typing.
    const fields = [['s','Start pixel',0, isM ? mw-1 : ledCount-1],
      ['e',cfg.comp.seglen ? 'Pixel count' : 'End pixel',1,isM ? mw : ledCount],
      ['grp','Grouping',1,255],['spc','Spacing',0,255],['of','Offset',0,65535]];
    if (isM) fields.push(['sY','Start Y',0,mh-1], ['eY',cfg.comp.seglen ? 'Height' : 'End Y',1,mh]);
    for (const [suffix, label, min, max] of fields) {
      const field = input(suffix);
      if (!field) continue;
      const value = Number(field.value);
      if (field.value === '' || !Number.isInteger(value) || value < min || value > max) {
        showToast(`${label}: enter a whole number from ${min} to ${max}.`, true);
        field.focus(); return;
      }
    }
    for (const [start, end, limit] of [['s','e',isM ? mw : ledCount], ...(isM ? [['sY','eY',mh]] : [])]) {
      const first = Number(input(start).value);
      const stop = Number(input(end).value) + (cfg.comp.seglen ? first : 0);
      if (stop <= first || stop > limit) {
        showToast(`Choose an end after the start and no higher than ${limit}. The end is not included.`, true);
        input(end).focus(); return;
      }
    }
    for (const key of segmentEdits.keys()) if (key.match(/^seg(\d+)/)?.[1] === String(id)) segmentEdits.delete(key);
    return originalSetSeg.call(this, id);
  };
  function disableBootOverride() {
    // These upstream selectors are visible even though only their default
    // values are supported by the Linux port. Do not offer failing choices.
    document.querySelectorAll('#segcont select[id$="bm"], #segcont select[id$="si"]').forEach(input => {
      input.disabled = true;
      input.title = 'Not available in WLED for FPP yet. The default setting is used.';
    });
    document.querySelectorAll('#segcont [onclick^="setGrp("]').forEach(item => {
      item.removeAttribute('onclick');
      item.setAttribute('aria-disabled', 'true');
      item.title = 'Segment sets are not available in WLED for FPP yet.';
    });
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
  // Slot labels sit on actual lighting colors, so choose their contrast from RGB luminance.
  function slotContrast() {
    document.querySelectorAll('#csl button').forEach(button => {
      const rgb = getComputedStyle(button).backgroundColor.match(/[\d.]+/g);
      if (!rgb || rgb.length < 3) return;
      const linear = rgb.slice(0,3).map(v => { const c = Number(v)/255; return c <= .04045 ? c/12.92 : ((c+.055)/1.055)**2.4; });
      const luminance = linear[0]*.2126 + linear[1]*.7152 + linear[2]*.0722;
      const color = luminance > .179 ? 'rgb(0, 0, 0)' : 'rgb(255, 255, 255)';
      if (button.style.color !== color || button.style.getPropertyPriority('color')!=='important') button.style.setProperty('color',color,'important');
    });
  }
  const slots = document.getElementById('csl');
  if (slots) new MutationObserver(slotContrast).observe(slots, {subtree:true, attributes:true, attributeFilter:['style','class']});
  slotContrast();
  const nightlightButton = document.getElementById('buttonNl');
  if (nightlightButton) {
    nightlightButton.onclick = () => { wledNavigate(wledSettingsURL('#nightlight')); };
    nightlightButton.title = 'Nightlight timer';
  }
  const peek = document.getElementById('buttonSr');
  if (peek) {
    peek.onclick = () => { wledNavigate(wledSettingsURL('#ambient-lighting')); };
    peek.title = 'Open ambient pixel preview';
  }
  const sync = document.getElementById('buttonSync');
  if (sync) {
    sync.onclick = () => { wledNavigate(wledSettingsURL('#network')); };
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
      button.onclick = () => { wledNavigate(wledSettingsURL()); };
      continue;
    }
    if (/\/edit/.test(button.getAttribute('onclick') || '')) {
      button.title = 'Import and back up presets';
      button.setAttribute('aria-label', button.title);
      const label = button.parentElement.querySelector('.iconlabel');
      if (label) label.textContent = 'Presets';
      button.onclick = () => { wledNavigate(wledSettingsURL('#preset-import')); }; continue;
    }
    if (/\/cpal/.test(button.getAttribute('onclick') || '')) {
      button.onclick = () => { wledNavigate(wledSettingsURL('#custom-palettes')); };
      continue;
    }
    if (button.id === 'updBt') { button.textContent = 'Plugin updates & help'; button.onclick = () => { wledNavigate(wledOnFPP() ? '/plugin.php?plugin=FPP_WLED_10.x&page=plugin.php&manage=1' : wledSettingsURL('#compatibility')); }; continue; }
    if (['resetbtn'].includes(button.id) ||
        /\/(edit|pixelforge|palette|cpal)/.test(button.getAttribute('onclick') || '')) {
      button.disabled = true;
      button.title = 'Unavailable in the Linux alpha; see Setup and compatibility';
      button.style.opacity = '.4';
      const explanation=document.createElement('a');explanation.textContent='Why unavailable?';explanation.href=wledSettingsURL('#compatibility');explanation.style.cssText='display:block;font-size:11px;margin-top:4px;';button.parentElement.append(explanation);
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
  accessText.textContent = 'Click Enable lighting controls to change colors and save your favorite looks. This browser will remember your access.';
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
    } catch { access.hidden = false; accessText.textContent = 'Cannot reach WLED. Check the plugin status in FPP, then reload this page.'; }
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
  // The status strip can wrap; keep the device name above its measured height.
  new ResizeObserver(() => {
    document.documentElement.style.setProperty('--linux-status-height', notice.getBoundingClientRect().height + 'px');
  }).observe(notice);
  async function refresh() {
    try {
      const status = await (await wledFetch('/api/status')).json();
      notice.replaceChildren(document.createTextNode(status.allowed ? 'Background lighting ready · ' : 'Background lighting paused: ' + (status.sources.join(', ') || (!status.enabled ? 'turned off in settings' : 'waiting for FPP')) + ' · '));
      const link = document.createElement('a');
      link.href = wledSettingsURL(); link.textContent = 'Settings & help'; link.style.cssText = 'color:CanvasText;pointer-events:auto';
      notice.append(link);
    } catch { notice.textContent = 'Runtime unavailable'; }
  }
  refresh(); setInterval(refresh, 1000);
})();
