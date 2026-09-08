"""Local WLED nightlight modes, measured in allowed ambient time."""
from copy import deepcopy
from math import isqrt
from .config import integer

DEFAULT = {'on': False, 'dur': 60, 'mode': 1, 'tbri': 0}


def sun_length(segment):
    """Pinned Segment::virtualLength geometry for the effect's static fallback."""
    width, height = segment['stop'] - segment['start'], segment['stopY'] - segment['startY']
    group = segment.get('grp', 1) + segment.get('spc', 0)
    if width > 1 and height > 1:
        if segment.get('tp', False):
            width, height = height, width
        width, height = (width + group - 1) // group, (height + group - 1) // group
        if segment.get('mi', False):
            width = (width + 1) // 2
        if segment.get('mY', False):
            height = (height + 1) // 2
        mapping = segment.get('m12', 0)
        return {1: height, 2: isqrt(width * width + height * height), 3: max(width, height),
                4: (max(width, height) + 15) & ~7}.get(mapping, width * height)
    length = (width + group - 1) // group
    return (length + 1) // 2 if segment.get('mi', False) else length


def settings(patch, base):
    if not isinstance(patch, dict) or set(patch) - set(DEFAULT):
        raise ValueError('nl accepts on, dur, mode and tbri only')
    result = dict(base, **patch)
    if result['on'] == 't':
        result['on'] = not base['on']
    if type(result['on']) is not bool:
        raise ValueError('nl.on must be boolean or t')
    integer(result['dur'], 1, 255, 'nightlight minutes')
    integer(result['mode'], 0, 3, 'nightlight mode')
    if result['mode'] == 3 and result['dur'] > 60:
        raise ValueError('sunrise/sunset animation supports 1..60 minutes')
    integer(result['tbri'], 0, 255, 'nightlight target brightness')
    return result


class Nightlight:
    def __init__(self, value):
        self.duration = value['nl']['dur'] * 60000
        self.elapsed = 0
        self.initial = value['bri'] if value['on'] else 0
        self.remembered = value['bri']
        self.mode = value['nl']['mode']
        self.sunset = bool(self.initial)
        if self.mode == 3:
            self.remembered = value['bri'] or 128
        self.colors = {s['id']: deepcopy(s['col'][:2]) for s in value['seg'] if s['sel']}

    def advance(self, value, elapsed):
        self.elapsed = min(self.duration, self.elapsed + max(0, elapsed))
        nl = value['nl']
        if self.mode == 3:
            return False  # Upstream effect 104 advances using the paused renderer clock.
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

    def render_state(self, value):
        result = deepcopy(value)
        result['transition'] = 0
        if self.mode == 3:
            result.update(on=True, bri=self.remembered)
            for segment in result['seg']:
                if segment['id'] in self.colors:
                    segment.update(fx=104, sx=self.duration // 60000 + (60 if self.sunset else 0), pal=0)
        return result

    def cancel_state(self, value):
        result = deepcopy(value)
        if self.mode == 3:
            result.update(on=True, bri=self.remembered)
        return result

    def finish(self, value):
        if self.mode != 3:
            return
        value.update(on=not self.sunset, bri=self.remembered)
        if not self.sunset:
            for segment in value['seg']:
                if segment['id'] in self.colors:
                    segment.update(fx=104, sx=0, pal=0)  # Upstream speed 0 holds the full sun.

    @property
    def remaining(self):
        return max(0, (self.duration - self.elapsed + 999) // 1000)
