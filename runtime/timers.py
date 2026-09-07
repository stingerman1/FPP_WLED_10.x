"""Local-time preset timers. Missed timers during shows are skipped, never queued."""
import datetime


class Timers:
    def __init__(self, definitions):
        self.definitions = definitions
        self.fired = set()
        self.day = None

    def due(self, now=None):
        now = now or datetime.datetime.now().astimezone()
        day = now.date().isoformat()
        if self.day != day:
            self.day, self.fired = day, set()
        result = []
        for index, timer in enumerate(self.definitions):
            if not timer.get('enabled', True) or index in self.fired:
                continue
            if now.weekday() in timer['days'] and timer['hour'] == now.hour and timer['minute'] == now.minute:
                self.fired.add(index)
                result.append(timer['preset'])
        return result
