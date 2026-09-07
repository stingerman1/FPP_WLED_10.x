"""Local WLED nightlight modes 0..2, measured in allowed ambient time."""
from copy import deepcopy
from .config import integer

DEFAULT = {'on': False, 'dur': 60, 'mode': 1, 'tbri': 0}


def settings(patch, base):
    if not isinstance(patch, dict) or set(patch) - set(DEFAULT):
        raise ValueError('nl accepts on, dur, mode and tbri only')
    result = dict(base, **patch)
    if result['on'] == 't':
        result['on'] = not base['on']
    if type(result['on']) is not bool:
        raise ValueError('nl.on must be boolean or t')
    integer(result['dur'], 1, 255, 'nightlight minutes')
    integer(result['mode'], 0, 2, 'nightlight mode (sunrise mode is not yet supported)')
    integer(result['tbri'], 0, 255, 'nightlight target brightness')
    return result


class Nightlight:
    def __init__(self, value):
        self.duration = value['nl']['dur'] * 60000
        self.elapsed = 0
        self.initial = value['bri'] if value['on'] else 0
        self.remembered = value['bri']
        self.colors = {s['id']: deepcopy(s['col'][:2]) for s in value['seg'] if s['sel']}

    def advance(self, value, elapsed):
        self.elapsed = min(self.duration, self.elapsed + max(0, elapsed))
        nl = value['nl']
        if nl['mode'] == 0 and self.elapsed < self.duration:
            return False
        ratio = self.elapsed / self.duration
        brightness = int(self.initial + (nl['tbri'] - self.initial) * ratio)
        value['on'] = brightness > 0
        value['bri'] = brightness if brightness else self.remembered
        if nl['mode'] == 2:
            for segment in value['seg']:
                if segment['id'] in self.colors:
                    primary, secondary = self.colors[segment['id']]
                    segment['col'][0] = [int(a + (b - a) * ratio) for a, b in zip(primary, secondary)]
        return True

    @property
    def remaining(self):
        return max(0, (self.duration - self.elapsed + 999) // 1000)
