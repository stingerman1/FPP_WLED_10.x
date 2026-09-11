// Local schedule editor. Draft edits never mutate the running schedule.
(() => {
  const byId = id => document.getElementById(id);
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  let timers = [], revision = null, generation = 0, editing = null;
  function changed() {
    generation++;
    byId('saveSchedules').disabled = true;
    byId('scheduleReport').textContent = 'Unsaved changes. Preview to review upcoming events.';
  }
  function number(id, low, high) {
    const input = byId(id), n = Number(input.value);
    if (input.value === '' || !input.checkValidity() || !Number.isFinite(n) || n < low || n > high)
      throw Error('Check ' + input.parentElement.firstChild.textContent.trim() + '.');
    return n;
  }
  function eventFields() {
    const clock = byId('scheduleEvent').value === 'clock';
    byId('scheduleClockLabel').hidden = !clock;
    byId('scheduleOffsetLabel').hidden = clock;
  }
  function resetEditor() {
    editing = null;
    byId('scheduleEditorTitle').textContent = 'Add a timer';
    byId('addSchedule').textContent = 'Add timer';
    byId('cancelScheduleEdit').hidden = true;
  }
  function edit(index) {
    const timer = timers[index];
    editing = index;
    byId('scheduleEditorTitle').textContent = 'Edit timer ' + (index + 1);
    byId('addSchedule').textContent = 'Update timer';
    byId('cancelScheduleEdit').hidden = false;
    byId('scheduleEvent').value = timer.event || 'clock';
    byId('scheduleClock').value = `${String(timer.hour || 0).padStart(2,'0')}:${String(timer.minute || 0).padStart(2,'0')}`;
    byId('scheduleOffset').value = timer.offset || 0;
    byId('schedulePreset').value = String(timer.preset);
    byId('scheduleEnabled').checked = timer.enabled !== false;
    days.forEach((_, i) => byId('scheduleDay' + i).checked = timer.days.includes(i));
    eventFields();
  }
  function render() {
    byId('scheduleList').replaceChildren();
    byId('scheduleEmpty').hidden = timers.length > 0;
    timers.forEach((timer, index) => {
      const row = document.createElement('li');
      row.style.marginBottom = '14px';
      const title = document.createElement('div');
      const event = timer.event || 'clock';
      const when = event === 'clock' ? `${String(timer.hour).padStart(2,'0')}:${String(timer.minute).padStart(2,'0')}`
        : `${event} ${timer.offset || 0} min`;
      title.textContent = `${when} → preset ${timer.preset}${timer.enabled === false ? ' · disabled' : ''}`;
      const detail = document.createElement('div');
      detail.className = 'lighting-note';
      detail.textContent = timer.days.map(i => days[i]).join(', ');
      const editButton = document.createElement('button');
      editButton.textContent = 'Edit'; editButton.setAttribute('aria-label', 'Edit timer ' + (index + 1));
      editButton.onclick = () => edit(index);
      const remove = document.createElement('button');
      remove.textContent = 'Remove'; remove.setAttribute('aria-label', 'Remove timer ' + (index + 1));
      remove.onclick = () => { timers.splice(index, 1); resetEditor(); changed(); render(); };
      row.append(title, detail, editButton, document.createTextNode(' '), remove);
      byId('scheduleList').append(row);
    });
  }
  function report(preview, message) {
    function time(value) {
      try {
        return new Intl.DateTimeFormat(undefined, {timeZone: preview.timezone, dateStyle: 'medium', timeStyle: 'short'}).format(new Date(value));
      } catch {
        return `${value.slice(0,10)} at ${value.slice(11,16)} UTC${value.slice(-6)}`;
      }
    }
    const lines = [message, `${preview.date} · ${preview.timezone}`];
    for (const [name, value] of Object.entries(preview.solar))
      lines.push(`${name}: ${value ? time(value) : 'No event on this date (polar day/night)'}`);
    for (const row of preview.upcoming)
      lines.push(`Timer ${row.index + 1} → preset ${row.preset}: ${row.next ? time(row.next) : 'Disabled or no event in the next 8 days'}`);
    byId('scheduleReport').textContent = lines.join('\n');
  }
  async function load() {
    const version = ++generation;
    byId('saveSchedules').disabled = true;
    try {
      const [response, presetsResponse] = await Promise.all([wledFetch('/api/schedules'), wledFetch('/presets.json')]);
      if (!response.ok || !presetsResponse.ok) throw Error('Schedules unavailable');
      const data = await response.json(), presets = await presetsResponse.json();
      if (version !== generation) return;
      timers = data.timers; revision = data.revision;
      byId('scheduleLocation').checked = Boolean(data.location);
      byId('scheduleCoordinates').hidden = !data.location;
      byId('scheduleLatitude').value = data.location?.latitude ?? '';
      byId('scheduleLongitude').value = data.location?.longitude ?? '';
      byId('scheduleZone').value = data.location?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
      const options = Object.entries(presets).filter(([id]) => Number(id) > 0)
        .map(([id, preset]) => new Option(`${id} · ${preset.n || 'Preset'}`, id));
      byId('schedulePreset').replaceChildren(...(options.length ? options : [new Option('Save a preset in WLED first', '')]));
      resetEditor(); render(); report(data.preview, 'Active schedules loaded.');
    } catch (e) { byId('scheduleReport').textContent = e.message; }
  }
  function request(preview) {
    return {preview, revision, timers, location: byId('scheduleLocation').checked ? {
      latitude: number('scheduleLatitude', -90, 90), longitude: number('scheduleLongitude', -180, 180),
      timezone: byId('scheduleZone').value.trim()
    } : null};
  }
  async function submit(preview) {
    const version = generation;
    byId('saveSchedules').disabled = true;
    try {
      const body = request(preview);
      const result = await post('/api/schedules', body);
      if (version !== generation) return;
      revision = result.revision;
      report(result.preview, result.saved ? 'Saved. These schedules are active now.' : 'Preview only. Save to apply these schedules.');
      byId('saveSchedules').disabled = !preview;
      if (result.saved) {
        // Keep unrelated edits in the raw configuration editor intact.
        try {
          const draft = JSON.parse(byId('config').value);
          if (draft && typeof draft === 'object' && !Array.isArray(draft)) {
            draft.timers = body.timers;
            if (body.location) draft.location = body.location; else delete draft.location;
            byId('config').value = JSON.stringify(draft, null, 2);
          }
        } catch { /* Leave an unfinished JSON draft untouched. */ }
      }
    } catch (e) {
      byId('scheduleReport').textContent = e.message;
      if (version === generation && !preview) byId('saveSchedules').disabled = false;
    }
  }
  days.forEach((day, i) => {
    const label = document.createElement('label'), input = document.createElement('input');
    input.id = 'scheduleDay' + i; input.type = 'checkbox'; input.checked = true;
    label.append(input, document.createTextNode(' ' + day)); byId('scheduleDays').append(label);
  });
  byId('addSchedule').onclick = () => {
    try {
      if (editing === null && timers.length >= 64) throw Error('At most 64 timers are supported.');
      const event = byId('scheduleEvent').value;
      const timer = {event, preset: number('schedulePreset', 1, 250),
        days: days.flatMap((_, i) => byId('scheduleDay' + i).checked ? [i] : []),
        enabled: byId('scheduleEnabled').checked};
      if (!timer.days.length) throw Error('Select at least one day.');
      if (event === 'clock') {
        if (!/^\d{2}:\d{2}$/.test(byId('scheduleClock').value)) throw Error('Choose a clock time.');
        [timer.hour, timer.minute] = byId('scheduleClock').value.split(':').map(Number);
      } else timer.offset = number('scheduleOffset', -720, 720);
      if (editing === null) timers.push(timer); else timers[editing] = timer;
      resetEditor(); changed(); render();
    } catch (e) { byId('scheduleReport').textContent = e.message; }
  };
  byId('scheduleEvent').onchange = eventFields;
  byId('scheduleLocation').onchange = () => { byId('scheduleCoordinates').hidden = !byId('scheduleLocation').checked; changed(); };
  ['scheduleLatitude','scheduleLongitude','scheduleZone'].forEach(id => byId(id).oninput = changed);
  byId('cancelScheduleEdit').onclick = resetEditor;
  byId('reloadSchedules').onclick = load;
  byId('previewSchedules').onclick = () => submit(true);
  byId('saveSchedules').onclick = () => submit(false);
  load();
})();
