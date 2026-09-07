"""Validated WLED JSON state subset and persistent presets/playlists."""
from copy import deepcopy
from .config import integer
from .storage import save_json, read_json


def default_segment(width, height):
    return {'id': 0, 'start': 0, 'stop': width, 'startY': 0, 'stopY': height,
            'on': True, 'bri': 255, 'fx': 0, 'sx': 128, 'ix': 128, 'pal': 0,
            'col': [[255, 160, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
            'sel': True, 'rev': False, 'mi': False}


class State:
    def __init__(self, directory, engine):
        self.directory, self.engine = directory, engine
        self.value = {'on': True, 'bri': 128, 'transition': 7, 'ps': -1, 'pl': -1, 'mainseg': 0,
                      'seg': [default_segment(engine.width, engine.height)]}
        saved = read_json(directory / 'state.json', self.value)
        self.value = self.merge(saved)
        self.presets = read_json(directory / 'presets.json', {})
        if not isinstance(self.presets, dict):
            raise ValueError('presets.json must be an object')
        self.playlist = None
        self.entry = 0
        self.remaining_ms = 0
        self.repeats_left = 0
        saved_playlist = read_json(directory / 'playlist.json', None)
        if saved_playlist:
            self.validate_playlist(saved_playlist['playlist'])
            self.playlist = saved_playlist['playlist']
            self.entry = integer(saved_playlist['entry'], 0, len(self.playlist['ps']) - 1, 'playlist entry')
            self.repeats_left = integer(saved_playlist['repeats_left'], 0, 65535, 'remaining repeats')
            self.restart_entry()

    def persist_playlist(self):
        save_json(self.directory / 'playlist.json', None if self.playlist is None else {
            'version': 1, 'playlist': self.playlist, 'entry': self.entry, 'repeats_left': self.repeats_left})

    def stop_playlist(self):
        self.playlist = None
        self.value['pl'] = -1
        self.value['ps'] = -1
        self.persist_playlist()
        save_json(self.directory / 'state.json', self.value)

    def merge(self, patch, base=None):
        if not isinstance(patch, dict):
            raise ValueError('state must be a JSON object')
        allowed = {'on', 'bri', 'transition', 'seg', 'ps', 'pl', 'mainseg', 'v', 'tt', 'n', 'time'}
        extra = set(patch) - allowed
        if extra:
            raise ValueError('unsupported state fields: ' + ', '.join(sorted(extra)))
        result = deepcopy(self.value if base is None else base)
        for key in ('ps', 'pl'):
            if key in patch:
                result[key] = integer(patch[key], -1, 250, key)
        for key in ('bri', 'transition', 'mainseg'):
            if key in patch:
                result[key] = integer(patch[key], 0, 655 if key == 'transition' else (31 if key == 'mainseg' else 255), key)
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
            seg_allowed = {'id', 'start', 'stop', 'startY', 'stopY', 'len', 'on', 'bri', 'fx', 'sx', 'ix', 'pal', 'col', 'sel', 'rev', 'mi', 'n',
                           'grp', 'spc', 'of', 'm12', 'c1', 'c2', 'c3', 'o1', 'o2', 'o3', 'rY', 'mY', 'tp', 'lc', 'fxdef', 'frz'}
            if set(update) - seg_allowed:
                raise ValueError('unsupported segment fields: ' + ', '.join(sorted(set(update) - seg_allowed)))
            sid = integer(update.get('id', index), 0, 31, 'segment id')
            if sid > len(result['seg']):
                raise ValueError('segment ids must be contiguous')
            if sid == len(result['seg']):
                result['seg'].append(default_segment(self.engine.width, self.engine.height))
            segment = result['seg'][sid]
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
                                  ('fx', 0, len(self.engine.effects) - 1), ('pal', 0, len(self.engine.palettes) - 1),
                                  ('sx', 0, 255), ('ix', 0, 255), ('bri', 0, 255)]:
                integer(segment[field], lo, hi, field)
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
        return result

    def set(self, patch, persist=True):
        value = self.merge(patch)
        if persist:
            save_json(self.directory / 'state.json', value)
        self.value = value
        return deepcopy(value)

    def save_preset(self, pid, patch):
        key = str(integer(pid, 1, 250, 'preset id'))
        candidate = deepcopy(self.presets)
        if 'playlist' in patch:
            self.validate_playlist(patch['playlist'])
            preset = {'playlist': deepcopy(patch['playlist']), 'n': patch.get('n', 'Playlist ' + key)}
        else:
            preset = self.merge(patch)
            preset['n'] = patch.get('n', 'Preset ' + key)
            preset.pop('ps', None)
            preset.pop('pl', None)
        if not isinstance(preset['n'], str) or len(preset['n']) > 128:
            raise ValueError('preset name must be a string of at most 128 characters')
        if any(c in preset['n'] for c in '<>&'):
            raise ValueError('preset names cannot contain HTML markup characters')
        candidate[key] = preset
        save_json(self.directory / 'presets.json', candidate)
        self.presets = candidate

    def delete_preset(self, pid):
        key = str(integer(pid, 1, 250, 'preset id'))
        if self.playlist and pid in self.playlist['ps']:
            raise ValueError('stop the active ambient playlist before deleting one of its entries')
        candidate = deepcopy(self.presets)
        candidate.pop(key, None)
        save_json(self.directory / 'presets.json', candidate)
        self.presets = candidate

    def select(self, pid):
        integer(pid, 1, 250, 'preset id')
        preset = self.presets.get(str(pid))
        if not isinstance(preset, dict):
            raise ValueError('preset does not exist')
        if 'playlist' in preset:
            self.start_playlist(preset['playlist'])
            self.value['pl'] = pid
        else:
            self.stop_playlist()
            self.set(preset)
            self.value.update(ps=pid, pl=-1)
        save_json(self.directory / 'state.json', self.value)

    def validate_playlist(self, playlist):
        if not isinstance(playlist, dict) or set(playlist) - {'ps', 'dur', 'transition', 'repeat', 'end', 'r'}:
            raise ValueError('unsupported playlist fields')
        ids = playlist.get('ps')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
            raise ValueError('playlist must have 1..100 preset entries')
        for pid in ids:
            integer(pid, 1, 250, 'playlist preset')
            if str(pid) not in self.presets or 'playlist' in self.presets[str(pid)]:
                raise ValueError('playlist entries must refer to existing non-playlist presets')
        for field, default, low in [('dur', 100, 1), ('transition', 7, 0)]:
            values = playlist.get(field, [default])
            if type(values) is int:
                values = [values]
            if not isinstance(values, list) or len(values) not in (1, len(ids)):
                raise ValueError(field + ' must have one value or one per entry')
            for val in values:
                integer(val, low, 65535, field)
        integer(playlist.get('repeat', 0), 0, 65535, 'repeat')
        if playlist.get('r', False):
            raise ValueError('randomized playlists are not yet supported')
        end = integer(playlist.get('end', 0), 0, 250, 'end')
        if end and (str(end) not in self.presets or 'playlist' in self.presets[str(end)]):
            raise ValueError('end must refer to an existing non-playlist preset')

    def start_playlist(self, playlist):
        self.validate_playlist(playlist)
        self.playlist = deepcopy(playlist)
        self.entry = 0
        self.repeats_left = playlist.get('repeat', 0)
        self.restart_entry()
        self.persist_playlist()

    def restart_entry(self):
        if self.playlist is None:
            return
        def entry_value(key, default):
            values = self.playlist.get(key, [default])
            return values if type(values) is int else values[self.entry % len(values)]
        pid = self.playlist['ps'][self.entry]
        preset = deepcopy(self.presets[str(pid)])
        preset['transition'] = min(entry_value('transition', 7), 655)
        self.set(preset, persist=False)
        self.value['ps'] = pid
        self.remaining_ms = entry_value('dur', 100) * 100

    def tick(self, elapsed_ms):
        if self.playlist is None:
            return False
        self.remaining_ms -= elapsed_ms
        if self.remaining_ms > 0:
            return False
        self.entry += 1
        if self.entry == len(self.playlist['ps']):
            self.entry = 0
            if self.repeats_left == 1:
                end = self.playlist.get('end', 0)
                self.playlist = None
                self.value['pl'] = -1
                self.persist_playlist()
                if end:
                    self.select(end)
                return True
            if self.repeats_left:
                self.repeats_left -= 1
        self.restart_entry()
        self.persist_playlist()
        return True

    def public(self):
        state = deepcopy(self.value)
        for segment in state['seg']:
            segment['lc'] = 3 if self.engine.config['pixels']['channels'] == 4 else 1
        state.update(nl={'on': False, 'dur': 60, 'mode': 1, 'tbri': 0, 'rem': -1},
                     udpn={'send': False, 'recv': False, 'sgrp': 1, 'rgrp': 1}, lor=0)
        return state
