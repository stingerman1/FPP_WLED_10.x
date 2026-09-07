"""Persistent native-format gradients using WLED's own 16-color conversion."""
from copy import deepcopy
import hashlib
import json
import re

from .config import integer
from .storage import read_json, save_json


def normalize(document):
    if not isinstance(document, dict) or set(document) != {'palette'}:
        raise ValueError('palette document must contain only palette')
    values = document['palette']
    if not isinstance(values, list) or not values:
        raise ValueError('palette must be a list of gradient stops')
    hex_format = len(values) > 1 and isinstance(values[1], str)
    stride = 2 if hex_format else 4
    if len(values) % stride or not 2 <= len(values) // stride <= 18:
        raise ValueError('palette requires 2..18 complete stops')
    stops = []
    for i in range(0, len(values), stride):
        position = integer(values[i], 0, 255, 'gradient position')
        if hex_format:
            color = values[i + 1]
            if not isinstance(color, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})', color):
                raise ValueError('palette colors must be RRGGBB or WWRRGGBB hex strings')
            color = int(color, 16)  # native custom palettes use RGB; white is ignored
            rgb = [(color >> 16) & 255, (color >> 8) & 255, color & 255]
        else:
            rgb = [integer(c, 0, 255, 'palette channel') for c in values[i + 1:i + 4]]
        if stops and (position < stops[-4] or stops[-4] == 255):
            raise ValueError('gradient positions must be ordered, with 255 only at the end')
        stops.extend([position, *rgb])
    if stops[0] != 0 or stops[-4] != 255:
        raise ValueError('gradient must begin at 0 and end at 255')
    return {'palette': stops}


class Palettes:
    def __init__(self, directory, engine):
        self.path, self.engine = directory / 'custom-palettes.json', engine
        self.max_slot = 200 - len(engine.palettes)
        stored = read_json(self.path, {'version': 1, 'palettes': {}})
        if not isinstance(stored, dict) or stored.get('version') != 1 or not isinstance(stored.get('palettes'), dict):
            raise ValueError('invalid custom-palettes.json')
        self.saved = {}
        for key, value in stored['palettes'].items():
            if not key.isascii() or not key.isdigit() or str(int(key)) != key:
                raise ValueError('invalid custom palette slot')
            integer(int(key), 0, self.max_slot, 'palette slot')
            self.saved[key] = normalize(value)
        self.fixed = {str(pid): engine.palette_preview(pid) for pid in range(len(engine.palettes))}
        self.publish(self.saved, self.prepare(self.saved))

    def prepare(self, saved):
        count = max((int(key) + 1 for key in saved), default=0)
        colors, previews = [], {}
        for slot in range(count):
            document = saved.get(str(slot))
            compiled = self.engine.compile_palette(document['palette']) if document else [128] * 48
            colors.extend(compiled)
            previews[str(200 - slot)] = [[i * 16, *compiled[i * 3:i * 3 + 3]] for i in range(16)]
        return colors, previews, count

    def publish(self, saved, prepared):
        colors, self.previews, self.count = prepared
        self.engine.set_custom_palettes(colors, [200 - int(slot) for slot in saved])
        self.saved = saved
        self.revision = hashlib.sha256(json.dumps(saved, sort_keys=True).encode()).hexdigest()[:16]

    def page(self, page):
        integer(page, 0, 100000, 'palette page')
        ids = list(self.fixed) + [str(200 - slot) for slot in range(self.count)]
        maximum = len(ids) // 8  # matches upstream, including an empty final page
        page = min(page, maximum)
        return {'m': maximum, 'p': {pid: deepcopy((self.fixed if pid in self.fixed else self.previews)[pid])
                                   for pid in ids[page * 8:page * 8 + 8]}}

    def public(self):
        return {'palettes': deepcopy(self.saved), 'max_slot': self.max_slot, 'revision': self.revision,
                'ids': {slot: 200 - int(slot) for slot in self.saved}, 'previews': deepcopy(self.previews)}

    def update(self, request, state, allowed):
        if not isinstance(request, dict) or set(request) - {'slot', 'palette', 'delete'}:
            raise ValueError('palette request accepts slot, palette and delete')
        slot = integer(request.get('slot'), 0, self.max_slot, 'palette slot')
        delete = request.get('delete', False)
        if type(delete) is not bool or (delete and 'palette' in request):
            raise ValueError('delete must be boolean and cannot accompany palette data')
        pid, key = 200 - slot, str(slot)
        def references(preset):
            segments = preset.get('seg', []) if isinstance(preset, dict) else []
            segments = [segments] if isinstance(segments, dict) else segments
            return isinstance(segments, list) and any(isinstance(s, dict) and s.get('pal') == pid for s in segments)
        if delete and (references(state.value) or any(references(p) for p in state.presets.values())):
            raise ValueError('palette is referenced by current state or a saved preset')
        if not allowed and references(state.value):
            raise PermissionError('editing the active palette is blocked while ambient is suspended')
        candidate = deepcopy(self.saved)
        if delete:
            candidate.pop(key, None)
        else:
            candidate[key] = normalize({'palette': request.get('palette')})
        prepared = self.prepare(candidate)
        save_json(self.path, {'version': 1, 'palettes': candidate})
        self.publish(candidate, prepared)
        return {'saved': True, 'slot': slot, 'id': pid, 'revision': self.revision}
