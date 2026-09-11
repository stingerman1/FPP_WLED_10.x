"""Validated WLED JSON state subset and persistent presets/playlists."""
from copy import deepcopy
import random
from .config import integer
from .storage import save_json, read_json
from .commands import lighting, number
from .nightlight import DEFAULT as NIGHTLIGHT_DEFAULT, Nightlight, settings as nightlight_settings, sun_length


def default_segment(width, height):
    return {'id': 0, 'start': 0, 'stop': width, 'startY': 0, 'stopY': height,
            'on': True, 'bri': 255, 'fx': 0, 'sx': 128, 'ix': 128, 'pal': 0,
            'col': [[255, 160, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
            'sel': True, 'rev': False, 'mi': False}


class State:
    def __init__(self, directory, engine, persist_import=True):
        self.directory, self.engine = directory, engine
        self.value = {'on': True, 'bri': 128, 'transition': 7, 'ps': -1, 'pl': -1, 'mainseg': 0,
                      'seg': [default_segment(engine.width, engine.height)]}
        saved = read_json(directory / 'state.json', self.value)
        imported = engine.config.get('imported_layout')
        apply_layout = imported and read_json(directory / 'layout-applied.json', '') != imported['revision']
        if apply_layout:
            saved = {**saved, 'seg':[{**default_segment(engine.width, engine.height), **segment} for segment in imported['segments']],
                     'mainseg':0, 'ps':-1, 'pl':-1}
        self.value = self.merge(saved)
        self.value['nl']['on'] = False  # Never restart a timed action after a process restart.
        self.nightlight = None
        self.presets = read_json(directory / 'presets.json', {})
        if not isinstance(self.presets, dict):
            raise ValueError('presets.json must be an object')
        self.playlist = None
        self.entry = 0
        self.remaining_ms = 0
        self.repeats_left = 0
        self.order = []
        self.return_preset = 0
        self.random = random.Random()
        saved_playlist = None if apply_layout else read_json(directory / 'playlist.json', None)
        if saved_playlist:
            self.validate_playlist(saved_playlist['playlist'])
            self.playlist = saved_playlist['playlist']
            self.entry = integer(saved_playlist['entry'], 0, len(self.playlist['ps']) - 1, 'playlist entry')
            self.repeats_left = integer(saved_playlist['repeats_left'], 0, 65535, 'remaining repeats')
            self.order = saved_playlist.get('order', list(range(len(self.playlist['ps']))))
            if (not isinstance(self.order, list) or any(type(i) is not int for i in self.order)
                    or sorted(self.order) != list(range(len(self.playlist['ps'])))):
                raise ValueError('invalid saved playlist order')
            self.return_preset = integer(saved_playlist.get('return_preset', 0), 0, 250, 'return preset')
            self.restart_entry()
        if apply_layout and persist_import:
            save_json(directory / 'state.json', self.value)
            save_json(directory / 'playlist.json', None)
            save_json(directory / 'layout-applied.json', imported['revision'])

    def persist_playlist(self):
        save_json(self.directory / 'playlist.json', None if self.playlist is None else {
            'version': 1, 'playlist': self.playlist, 'entry': self.entry, 'repeats_left': self.repeats_left,
            'order': self.order, 'return_preset': self.return_preset})

    def stop_playlist(self):
        self.playlist = None
        self.value['pl'] = -1
        self.value['ps'] = -1
        self.persist_playlist()
        save_json(self.directory / 'state.json', self.value)

    def merge(self, patch, base=None):
        if not isinstance(patch, dict):
            raise ValueError('state must be a JSON object')
        patch = deepcopy(patch)
        if 'win' in patch:
            if set(patch) - {'win', 'n', 'ql', 'v', 'transition'}:
                raise ValueError('win supports only n, ql, v and transition alongside the command')
            translated = lighting(patch.pop('win'), self.value if base is None else base,
                                  len(self.engine.effects) - 1)
            patch = dict(translated, **patch)
        # Stock exports include defaults for hardware/advanced features. Neutral
        # values can be translated without pretending their non-default behavior exists.
        for key, default in (('bs', 0), ('ledmap', 0)):
            if key in patch:
                integer(patch.pop(key), default, default, key + ' (only the default is supported)')
        allowed = {'on', 'bri', 'transition', 'seg', 'ps', 'pl', 'mainseg', 'v', 'tt', 'n', 'ql', 'time', 'nl'}
        extra = set(patch) - allowed
        if extra:
            raise ValueError('unsupported state fields: ' + ', '.join(sorted(extra)))
        result = deepcopy(self.value if base is None else base)
        result['nl'] = nightlight_settings(patch.get('nl', {}), result.get('nl', NIGHTLIGHT_DEFAULT))
        for key in ('ps', 'pl'):
            if key in patch:
                result[key] = integer(patch[key], -1, 250, key)
        for key in ('bri', 'transition', 'mainseg'):
            if key in patch:
                result[key] = (number(patch[key], result[key], 0, 255, key) if key == 'bri' else
                               integer(patch[key], 0, 655 if key == 'transition' else 31, key))
        if 'on' in patch:
            if patch['on'] == 't':
                result['on'] = not result['on']
            elif type(patch['on']) is bool:
                result['on'] = patch['on']
            else:
                raise ValueError('on must be true, false or "t"')
        segments = patch.get('seg', [])
        if isinstance(segments, dict):
            segments = ([dict(segments, id=s['id']) for s in result['seg'] if s.get('sel', True)]
                        if 'id' not in segments else [segments])
        if not isinstance(segments, list) or len(segments) > 32:
            raise ValueError('seg must be an object or list of at most 32 segments')
        for index, update in enumerate(segments):
            if not isinstance(update, dict):
                raise ValueError('each segment must be an object')
            for key, default in (('cct', 127), ('set', 0), ('si', 0), ('bm', 0)):
                if key in update:
                    integer(update.pop(key), default, default, key + ' (only the default is supported)')
            seg_allowed = {'id', 'start', 'stop', 'startY', 'stopY', 'len', 'on', 'bri', 'fx', 'sx', 'ix', 'pal', 'col', 'sel', 'rev', 'mi', 'n',
                           'grp', 'spc', 'of', 'm12', 'c1', 'c2', 'c3', 'o1', 'o2', 'o3', 'rY', 'mY', 'tp', 'lc', 'fxdef', 'frz'}
            if set(update) - seg_allowed:
                raise ValueError('unsupported segment fields: ' + ', '.join(sorted(set(update) - seg_allowed)))
            sid = integer(update.get('id', index), 0, 31, 'segment id')
            if sid >= len(result['seg']) and update.get('stop') == 0:
                continue # upstream saved presets pad unused slots with stop:0
            if sid > len(result['seg']):
                raise ValueError('segment ids must be contiguous')
            if sid == len(result['seg']):
                result['seg'].append(default_segment(self.engine.width, self.engine.height))
            segment = result['seg'][sid]
            for field in ('fx', 'sx', 'ix', 'bri', 'c1', 'c2', 'c3'):
                if field in update:
                    update[field] = number(update[field], segment.get(field, 16 if field == 'c3' else 128), 0,
                                           len(self.engine.effects) - 1 if field == 'fx' else
                                           (31 if field == 'c3' else 255), field)
            old_colors = deepcopy(segment['col'])
            if update.get('fxdef', False) and update.get('fx', segment['fx']) != segment['fx']:
                mode = integer(update['fx'], 0, len(self.engine.effects) - 1, 'effect')
                segment.update(self.engine.defaults(mode))
            segment.update(update)
            segment.pop('fxdef', None)
            segment['id'] = sid
            if update.get('stop') == 0:
                segment['stop'] = 0
                continue
            if 'len' in update and 'stop' not in update:
                segment['stop'] = segment['start'] + integer(update['len'], 1, self.engine.width, 'segment length')
            for field, lo, hi in [('start', 0, self.engine.width - 1), ('stop', 1, self.engine.width),
                                  ('startY', 0, self.engine.height - 1), ('stopY', 1, self.engine.height),
                                  ('fx', 0, len(self.engine.effects) - 1), ('pal', 0, 200),
                                  ('sx', 0, 255), ('ix', 0, 255), ('bri', 0, 255)]:
                integer(segment[field], lo, hi, field)
            if segment['pal'] not in self.engine.palette_ids:
                raise ValueError('palette is unavailable; import its custom palette file first')
            if segment['start'] >= segment['stop'] or segment['startY'] >= segment['stopY']:
                raise ValueError('segment has an empty or inverted range')
            if segment['fx'] in self.engine.unsupported:
                raise ValueError(f'effect {segment["fx"]} is unsupported on Linux')
            for field, lo, hi, default in [('grp', 1, 255, 1), ('spc', 0, 255, 0), ('of', 0, 65535, 0),
                                          ('m12', 0, 7, 0), ('c1', 0, 255, 128), ('c2', 0, 255, 128), ('c3', 0, 31, 16)]:
                segment[field] = integer(segment.get(field, default), lo, hi, field)
            for field in ('o1', 'o2', 'o3', 'rY', 'mY', 'tp', 'frz'):
                segment.setdefault(field, False)
            for field in ('on', 'sel', 'rev', 'mi', 'o1', 'o2', 'o3', 'rY', 'mY', 'tp', 'frz'):
                if type(segment[field]) is not bool:
                    raise ValueError(field + ' must be boolean')
            if not isinstance(segment.get('n', ''), str) or len(segment.get('n', '').encode()) > 128:
                raise ValueError('segment name must be at most 128 UTF-8 bytes')
            if any(c in segment.get('n', '') for c in '<>&'):
                raise ValueError('segment names cannot contain HTML markup characters')
            colors = segment['col']
            if not isinstance(colors, list) or not 1 <= len(colors) <= 3:
                raise ValueError('col must contain 1..3 RGB or RGBW arrays')
            colors = deepcopy(colors)
            for slot, color in enumerate(colors):
                if color is None or color == []:
                    colors[slot] = old_colors[slot]
                    continue
                if isinstance(color, str) and len(color) in (6, 8):
                    try:
                        value = int(color, 16)
                    except ValueError:
                        raise ValueError('invalid hexadecimal color') from None
                    color = [(value >> 16) & 255, (value >> 8) & 255, value & 255, (value >> 24) & 255]
                if isinstance(color, list):
                    color = [0 if value is None else value for value in color]
                colors[slot] = color
                if not isinstance(color, list) or len(color) not in (3, 4):
                    raise ValueError('colors must be RGB or RGBW arrays')
                for channel in color:
                    integer(channel, 0, 255, 'color channel')
            segment['col'] = [color + [0] * (4 - len(color)) for color in colors]
            segment['col'] += old_colors[len(colors):]
            segment.pop('lc', None)
            segment.pop('len', None)
        result['seg'] = [s for s in result['seg'] if s['stop'] != 0]
        if not result['seg']:
            raise ValueError('at least one segment is required; use on:false to turn off')
        for index, segment in enumerate(result['seg']):
            segment['id'] = index
        if result['mainseg'] >= len(result['seg']):
            result['mainseg'] = 0
        if 'nl' in patch and result['nl']['on'] and result['nl']['mode'] == 3:
            selected = [s for s in result['seg'] if s['sel']]
            if 104 in self.engine.unsupported or not selected:
                raise ValueError('sunrise requires supported effect 104 and a selected segment')
            for segment in selected:
                if sun_length(segment) <= 1 or segment.get('frz', False):
                    raise ValueError('sunrise requires at least two virtual pixels and unfrozen selected segments')
        return result

    def set(self, patch, persist=True):
        base = self.nightlight.cancel_state(self.value) if self.nightlight else self.value
        # Remove the old activation before validating an unrelated replacement.
        base = deepcopy(base)
        if 'nl' not in patch:
            base['nl']['on'] = False
        value = self.merge(patch, base)
        # A new lighting selection replaces the timed action; editing only its
        # settings restarts it from the current light level. All validation precedes this.
        if 'nl' not in patch:
            value['nl']['on'] = False
        nightlight = Nightlight(value) if value['nl']['on'] else None
        if persist:
            save_json(self.directory / 'state.json', value)
        self.value = value
        self.nightlight = nightlight
        return deepcopy(value)

    def tick_nightlight(self, elapsed_ms):
        if self.nightlight is None:
            return False
        changed = self.nightlight.advance(self.value, elapsed_ms)
        if self.nightlight.remaining == 0:
            self.nightlight.finish(self.value)
            self.value['nl']['on'] = False
            self.nightlight = None
            save_json(self.directory / 'state.json', self.value)
            changed = True
        return changed

    def save_preset(self, pid, patch, options=None):
        key = str(integer(pid, 1, 250, 'preset id'))
        options = options or {}
        for name in ('ib', 'sb', 'sc', 'o'):
            if name in options and type(options[name]) is not bool:
                raise ValueError(name + ' must be boolean')
        candidate = deepcopy(self.presets)
        if 'playlist' in patch:
            self.validate_playlist(patch['playlist'])
            preset = {'playlist': deepcopy(patch['playlist']), 'n': patch.get('n', 'Playlist ' + key)}
        else:
            checked = self.merge(patch)
            if 'nl' not in patch:
                checked['nl']['on'] = False
            if options.get('o', False):
                if 'ps' in patch or 'pl' in patch:
                    raise ValueError('custom preset references are not yet supported')
                # Custom JSON presets remain patches: absent fields follow the
                # current state when recalled, rather than freezing save-time values.
                preset = {k: deepcopy(v) for k, v in patch.items() if k not in ('v', 'time', 'ps', 'pl')}
            else:
                preset = checked
                if not options.get('ib', True):
                    for field in ('on', 'bri', 'transition'):
                        preset.pop(field, None)
                if options.get('sc', False):
                    preset['seg'] = [s for s in preset['seg'] if s['sel']]
                if not options.get('sb', True):
                    for segment in preset['seg']:
                        for field in ('start', 'stop', 'startY', 'stopY'):
                            segment.pop(field, None)
                elif not options.get('sc', False):
                    # Disable extra segments added after this bounded snapshot.
                    preset['seg'] += [{'stop': 0} for _ in range(32 - len(preset['seg']))]
            preset['n'] = patch.get('n', 'Preset ' + key)
            preset.pop('ps', None)
            preset.pop('pl', None)
        if not isinstance(preset['n'], str) or len(preset['n']) > 128:
            raise ValueError('preset name must be a string of at most 128 characters')
        if any(c in preset['n'] for c in '<>&'):
            raise ValueError('preset names cannot contain HTML markup characters')
        label = patch.get('ql', '')
        if not isinstance(label, str) or len(label.encode()) > 8 or any(c in label for c in '<>&'):
            raise ValueError('quick-load label must be at most 8 UTF-8 bytes without HTML markup')
        if label:
            preset['ql'] = label
        candidate[key] = preset
        save_json(self.directory / 'presets.json', candidate)
        self.presets = candidate

    def delete_preset(self, pid):
        key = str(integer(pid, 1, 250, 'preset id'))
        if self.playlist and (pid in self.playlist['ps'] or pid == self.return_preset or pid == self.playlist.get('end')):
            raise ValueError('stop the active ambient playlist before deleting one of its entries')
        candidate = deepcopy(self.presets)
        candidate.pop(key, None)
        save_json(self.directory / 'presets.json', candidate)
        self.presets = candidate

    def select(self, pid):
        pid = number(pid, self.value['ps'], 1, 250, 'preset id')
        integer(pid, 1, 250, 'preset id')
        preset = self.presets.get(str(pid))
        if not isinstance(preset, dict):
            raise ValueError('preset does not exist')
        if 'playlist' in preset:
            self.start_playlist(preset['playlist'])
            self.value['pl'] = pid
        else:
            self.merge(preset) # reject malformed saved state before stopping the playlist
            self.stop_playlist()
            self.set(preset)
            self.value.update(ps=pid, pl=-1)
        save_json(self.directory / 'state.json', self.value)

    def validate_playlist(self, playlist, presets=None):
        presets = self.presets if presets is None else presets
        if not isinstance(playlist, dict) or set(playlist) - {'ps', 'dur', 'transition', 'repeat', 'end', 'r'}:
            raise ValueError('unsupported playlist fields')
        ids = playlist.get('ps')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
            raise ValueError('playlist must have 1..100 preset entries')
        for pid in ids:
            integer(pid, 1, 250, 'playlist preset')
            if not isinstance(presets.get(str(pid)), dict) or 'playlist' in presets[str(pid)]:
                raise ValueError('playlist entries must refer to existing non-playlist presets')
            self.merge(presets[str(pid)])
            if presets[str(pid)].get('nl', {}).get('on', False):
                raise ValueError('active nightlights cannot be playlist entries')
        for field, default, low in [('dur', 100, 0), ('transition', 7, 0)]:
            values = playlist.get(field, [default])
            if type(values) is int:
                values = [values]
            if not isinstance(values, list) or not 1 <= len(values) <= len(ids):
                raise ValueError(field + ' must contain 1..entry-count values; the final value repeats')
            for val in values:
                integer(val, low, 42949670 if field == 'dur' else 655, field)
        integer(playlist.get('repeat', 0), -255, 65535, 'repeat')
        if type(playlist.get('r', False)) not in (bool, int) or playlist.get('r', False) not in (False, True, 0, 1):
            raise ValueError('playlist r must be boolean or 0/1')
        end = integer(playlist.get('end', 0), 0, 255, 'end')
        if end not in (0, 255) and (not isinstance(presets.get(str(end)), dict) or 'playlist' in presets[str(end)]):
            raise ValueError('end must refer to an existing non-playlist preset')
        if 1 <= end <= 250:
            self.merge(presets[str(end)])

    def start_playlist(self, playlist):
        self.validate_playlist(playlist)
        self.playlist = deepcopy(playlist)
        self.entry = 0
        self.repeats_left = max(0, playlist.get('repeat', 0))
        previous = self.value.get('ps', -1)
        self.return_preset = previous if (playlist.get('end') == 255 and str(previous) in self.presets
                                          and 'playlist' not in self.presets[str(previous)]) else 0
        self.order = list(range(len(playlist['ps'])))
        if self.shuffled():
            self.random.shuffle(self.order)
        self.restart_entry()
        self.persist_playlist()

    def shuffled(self):
        return self.playlist and (self.playlist.get('r', False) or self.playlist.get('repeat', 0) < 0)

    def restart_entry(self):
        if self.playlist is None:
            return
        index = self.order[self.entry]
        def entry_value(key, default):
            values = self.playlist.get(key, [default])
            return values if type(values) is int else values[min(index, len(values) - 1)]
        pid = self.playlist['ps'][index]
        preset = deepcopy(self.presets[str(pid)])
        preset['transition'] = min(entry_value('transition', 7), 655)
        playlist_id = self.value['pl']
        self.set(preset, persist=False)
        self.value['pl'] = playlist_id
        self.value['ps'] = pid
        duration = entry_value('dur', 100)
        self.remaining_ms = duration * 100 if duration else None

    def tick(self, elapsed_ms, advance=False):
        if self.playlist is None or not self.value['on'] or self.value['bri'] == 0:
            return False
        if not advance:
            if self.remaining_ms is None:
                return False
            self.remaining_ms -= elapsed_ms
            if self.remaining_ms > 0:
                return False
        self.entry += 1
        if self.entry == len(self.playlist['ps']):
            self.entry = 0
            if self.repeats_left == 1:
                end = self.playlist.get('end', 0)
                if end == 255:
                    end = self.return_preset
                self.playlist = None
                self.value['pl'] = -1
                self.persist_playlist()
                if end:
                    self.select(end)
                else:
                    save_json(self.directory / 'state.json', self.value)
                return True
            if self.repeats_left:
                self.repeats_left -= 1
            if self.shuffled():
                self.random.shuffle(self.order)
        self.restart_entry()
        self.persist_playlist()
        return True

    def public(self):
        state = self.nightlight.render_state(self.value) if self.nightlight and self.nightlight.mode == 3 else deepcopy(self.value)
        state['transition'] = self.value['transition']
        for segment in state['seg']:
            segment['lc'] = 3 if self.engine.config['pixels']['channels'] == 4 else 1
        state['nl']['rem'] = self.nightlight.remaining if self.nightlight else -1
        state.update(udpn={'send': False, 'recv': False, 'sgrp': 1, 'rgrp': 1}, lor=0)
        return state
