import ctypes as C
import json


class Engine:
    """The renderer is single-threaded; all calls belong to the coordinator loop."""
    def __init__(self, library, config):
        self.lib = C.CDLL(str(library))
        self.lib.wled_init.argtypes = [C.c_uint, C.c_uint, C.c_uint, C.c_int, C.c_uint32]
        self.lib.wled_mode.argtypes = [C.c_uint]
        self.lib.wled_mode.restype = C.c_char_p
        self.lib.wled_palettes.restype = C.c_char_p
        self.lib.wled_compile_palette.argtypes = [C.POINTER(C.c_uint8), C.c_uint, C.POINTER(C.c_uint8)]
        self.lib.wled_custom_palettes.argtypes = [C.POINTER(C.c_uint8), C.c_uint]
        self.lib.wled_palette_preview.argtypes = [C.c_uint, C.POINTER(C.c_uint8)]
        self.lib.wled_segment.argtypes = [C.c_uint] * 14
        self.lib.wled_options.argtypes = [C.c_uint] * 9 + [C.c_char_p]
        self.lib.wled_render.argtypes = [C.c_uint32, C.POINTER(C.c_uint8), C.c_uint]
        self.config = config
        p = config['pixels']
        self.width, self.height = p.get('width', p['count']), p.get('height', 1)
        if self.lib.wled_init(p['count'], self.width, self.height, p['channels'] == 4, 0x12345678):
            raise RuntimeError('WLED could not initialize its pixel buffers')
        self.buffer = (C.c_uint8 * (p['count'] * p['channels']))()
        self.metadata = [self.lib.wled_mode(i).decode() for i in range(self.lib.wled_modes())]
        self.effects = [m.split('@')[0] for m in self.metadata]
        self.palettes = json.loads(self.lib.wled_palettes())
        self.palette_ids = set(range(len(self.palettes)))
        self.unsupported = {i for i, m in enumerate(self.metadata) if m.startswith('RSVD')}
        # Sound-reactive metadata encodes volume/frequency support with v/f suffixes.
        for i, m in enumerate(self.metadata):
            fields = m.split(';')
            if len(fields) > 3 and any(c in fields[3] for c in 'vf'):
                self.unsupported.add(i)
            if self.height == 1 and len(fields) > 3 and '2' in fields[3] and '1' not in fields[3]:
                self.unsupported.add(i)

    def compile_palette(self, stops):
        source = (C.c_uint8 * len(stops))(*stops)
        output = (C.c_uint8 * 48)()
        if self.lib.wled_compile_palette(source, len(stops) // 4, output):
            raise ValueError('renderer rejected gradient stops')
        return list(output)

    def set_custom_palettes(self, colors, ids):
        source = (C.c_uint8 * len(colors))(*colors)
        if self.lib.wled_custom_palettes(source, len(colors) // 48):
            raise ValueError('renderer rejected custom palette table')
        self.palette_ids = set(range(len(self.palettes))) | set(ids)

    def palette_preview(self, pid):
        tokens = {1: ['r'] * 4, 2: ['c1'], 3: ['c1', 'c1', 'c2', 'c2'],
                  4: ['c3', 'c2', 'c1'], 5: ['c1'] * 5 + ['c2'] * 5 + ['c3'] * 5 + ['c1']}
        if pid in tokens:
            return tokens[pid]
        output = (C.c_uint8 * 72)()
        count = self.lib.wled_palette_preview(pid, output)
        if count < 0:
            raise ValueError('palette preview unavailable')
        return [list(output[i * 4:i * 4 + 4]) for i in range(count)]

    def apply(self, state):
        self.lib.wled_brightness(state['bri'] if state['on'] else 0, state.get('transition', 7) * 100)
        self.lib.wled_mainsegment(state.get('mainseg', 0))
        for i, s in enumerate(state['seg']):
            if s['fx'] in self.unsupported:
                raise ValueError(f'effect {s["fx"]} is unsupported in this Linux alpha')
            def packed(color):
                color = color + [0] * (4 - len(color))
                r, g, b, w = color
                return (w << 24) | (r << 16) | (g << 8) | b
            colors = s['col'] + [[0, 0, 0]] * (3 - len(s['col']))
            options = int(s.get('on', True)) | (int(s.get('rev', False)) << 1) | (int(s.get('mi', False)) << 2) | (int(s.get('sel', True)) << 3)
            if self.lib.wled_segment(i, s['start'], s['stop'], s.get('startY', 0), s.get('stopY', 1),
                                     s['fx'], s['sx'], s['ix'], s['pal'], *(packed(c) for c in colors),
                                     s.get('bri', 255), options):
                raise ValueError('WLED rejected segment geometry or effect')
            flags = sum(int(s.get(k, False)) << bit for bit, k in enumerate(['o1', 'o2', 'o3', 'rY', 'mY', 'tp', 'frz']))
            if self.lib.wled_options(i, s.get('grp', 1), s.get('spc', 0), s.get('of', 0), s.get('m12', 0),
                                      s.get('c1', 128), s.get('c2', 128), s.get('c3', 16), flags, s.get('n', '').encode()):
                raise ValueError('WLED rejected segment options')
        self.lib.wled_trim(len(state['seg']))

    def defaults(self, mode):
        result = {'sx': 128, 'ix': 128, 'c1': 128, 'c2': 128, 'c3': 16,
                  'o1': False, 'o2': False, 'o3': False, 'm12': 0}
        for pair in self.metadata[mode].split(';')[-1].split(','):
            key, separator, value = pair.partition('=')
            if separator and key in {*result, 'pal', 'rev', 'mi', 'rY', 'mY'}:
                number = int(value)
                result[key] = bool(number) if key in ('o1', 'o2', 'o3', 'rev', 'mi', 'rY', 'mY') else number
        return result

    def render(self, elapsed_ms):
        result = self.lib.wled_render(elapsed_ms & 0xffffffff, self.buffer, len(self.buffer))
        if result:
            raise RuntimeError(f'WLED rendering failed: {result}')
        data = bytes(self.buffer)
        mapping = self.config.get('ledmap')
        if mapping is None:
            return data
        channels = self.config['pixels']['channels']
        result = bytearray(len(data))
        for logical, physical in enumerate(mapping):
            if physical >= 0:
                result[physical * channels:(physical + 1) * channels] = data[logical * channels:(logical + 1) * channels]
        return bytes(result)
