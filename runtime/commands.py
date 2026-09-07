"""Pure, bounded translations of pinned WLED util.cpp/set.cpp commands."""
import re
from urllib.parse import parse_qsl

from .config import integer


def number(value, current, low, high, name):
    """WLED increment/clamp/endpoint-wrap subset; reject malformed expressions."""
    if type(value) is int:
        return integer(value, low, high, name)
    if not isinstance(value, str) or not 1 <= len(value) <= 12:
        raise ValueError(name + ' requires an integer or supported numeric expression')
    bounded = re.fullmatch(r'(\d+)~(\d+)(w?~(?:-?\d*|\+\d+))', value)
    if bounded:
        lo, hi = int(bounded[1]), int(bounded[2])
        integer(lo, low, high, name + ' lower bound')
        integer(hi, lo, high, name + ' upper bound')
        return number(bounded[3], current, lo, hi, name)
    if re.fullmatch(r'\d+', value):
        return integer(int(value), low, high, name)
    match = re.fullmatch(r'(w?)~(-?\d*|\+\d+)', value)
    if not match:
        raise ValueError(name + ': unsupported numeric expression')
    step = match[2]
    if step in ('', '-'):
        result = current + (-1 if step == '-' else 1)
        return high if result < low else low if result > high else result
    delta = int(step)
    if delta == 0:
        return current
    if match[1] and current == high and delta > 0:
        return low
    if match[1] and current == low and delta < 0:
        return high
    return max(low, min(high, current + delta))


def lighting(command, base, effect_max):
    """Translate a lighting-only win string without executing any side effects."""
    if not isinstance(command, str) or not command or len(command) > 4096:
        raise ValueError('win must be a nonempty command string of at most 4096 characters')
    raw = command
    for prefix in ('/win', 'win'):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    raw = raw.lstrip('?&')
    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=32)
    args = dict(pairs)
    allowed = {'A', 'T', 'SS', 'FX', 'SX', 'IX', 'RV', 'MI',
               'R', 'G', 'B', 'W', 'R2', 'G2', 'B2', 'W2'}
    if not args or len(args) != len(pairs) or set(args) - allowed:
        raise ValueError('unsupported or duplicate win command; supported: ' + ', '.join(sorted(allowed)))
    patch = {}
    if 'A' in args:
        patch['bri'] = number(args['A'], base['bri'] if base['on'] else 0, 0, 255, 'A')
        patch['on'] = patch['bri'] > 0
    if 'T' in args:
        action = number(args['T'], 0, 0, 2, 'T')
        patch['on'] = not patch.get('on', base['on']) if action == 2 else bool(action)
    selected = next((s['id'] for s in base['seg'] if s.get('sel', True)), 0)
    if 'SS' in args:
        selected = number(args['SS'], selected, 0, len(base['seg']) - 1, 'SS')
    source = base['seg'][selected]
    update = {}
    for legacy, field in (('FX', 'fx'), ('SX', 'sx'), ('IX', 'ix')):
        if legacy in args:
            update[field] = number(args[legacy], source[field], 0, effect_max if legacy == 'FX' else 255, legacy)
    colors = [list(c) for c in source['col']]
    for slot, suffix in ((0, ''), (1, '2')):
        for channel, name in enumerate('RGBW'):
            key = name + suffix
            if key in args:
                colors[slot][channel] = number(args[key], colors[slot][channel], 0, 255, key)
                update['col'] = colors
    updates = []
    for segment in base['seg']:
        if segment['id'] == selected or ('SS' not in args and segment.get('sel', True)):
            item = dict(update, id=segment['id'])
            if segment['id'] == selected:
                for legacy, field in (('RV', 'rev'), ('MI', 'mi')):
                    if legacy in args:
                        item[field] = bool(number(args[legacy], 0, 0, 1, legacy))
            updates.append(item)
    patch['seg'] = updates
    return patch
