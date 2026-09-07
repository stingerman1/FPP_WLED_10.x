"""Clock and solar preset schedules. Missed/show-owned events are never queued."""
from copy import deepcopy
import datetime as dt
import hashlib
import json
from zoneinfo import ZoneInfo
from .config import validate_schedule
from .storage import read_json, save_json

UTC = dt.timezone.utc


class Timers:
    def __init__(self, definitions, location=None, ledger=None):
        validate_schedule(location, definitions)
        self.definitions, self.location = deepcopy(definitions), deepcopy(location)
        self.zone = ZoneInfo(location['timezone']) if location else None
        self.ledger = ledger
        self.fired = read_json(ledger, {}) if ledger else {}
        if not isinstance(self.fired, dict) or len(self.fired) > 4096:
            raise ValueError('invalid timer ledger')
        for key, day in self.fired.items():
            if not isinstance(key, str) or not isinstance(day, str):
                raise ValueError('invalid timer ledger entry')
            dt.date.fromisoformat(day)
        self.cache = {}
        self.minute = None

    def local(self, now=None):
        now = now or dt.datetime.now().astimezone()
        if now.tzinfo is None:
            now = now.replace(tzinfo=self.zone) if self.zone else now.astimezone()
        return now.astimezone(self.zone) if self.zone else now

    def solar(self, day, event):
        key = (day, event)
        if key not in self.cache:
            from astral import Observer
            from astral.sun import sunrise, sunset
            observer = Observer(self.location['latitude'], self.location['longitude'])
            try:
                self.cache[key] = (sunrise if event == 'sunrise' else sunset)(observer, day, self.zone)
            except ValueError:
                self.cache[key] = None  # Polar day/night: no substitute event.
        return self.cache[key]

    def occurrence(self, timer, day, zone):
        if not timer.get('enabled', True) or day.weekday() not in timer['days']:
            return None
        if timer.get('event', 'clock') == 'clock':
            result = dt.datetime.combine(day, dt.time(timer['hour'], timer['minute']), zone)
            # Skip nonexistent spring-forward wall times; fall-back uses fold=0.
            if result.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != result.replace(tzinfo=None):
                return None
            return result
        event = self.solar(day, timer['event'])
        if event is None:
            return None
        return (event.astimezone(UTC) + dt.timedelta(minutes=timer.get('offset', 0))).astimezone(zone).replace(second=0, microsecond=0)

    def token(self, timer, day):
        event = timer.get('event', 'clock')
        identity = {'event': event, 'preset': timer['preset'], 'days': sorted(set(timer['days']))}
        identity.update({'hour': timer['hour'], 'minute': timer['minute']} if event == 'clock'
                        else {'offset': timer.get('offset', 0)})
        location = dict(self.location, latitude=float(self.location['latitude']),
                        longitude=float(self.location['longitude'])) if self.location else None
        encoded = json.dumps([location, identity, day.isoformat()], sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()

    def due(self, now=None):
        now = self.local(now).replace(second=0, microsecond=0)
        minute = now.astimezone(UTC)
        if minute == self.minute:
            return []
        candidates, result = {}, []
        for timer in self.definitions:
            for delta in (-1, 0, 1):
                day = now.date() + dt.timedelta(days=delta)
                event = self.occurrence(timer, day, now.tzinfo)
                key = self.token(timer, day)
                if event and event.astimezone(UTC) == minute and key not in self.fired and key not in candidates:
                    candidates[key] = day.isoformat()
                    result.append(timer['preset'])
        if candidates:
            earliest = (now.date() - dt.timedelta(days=8)).isoformat()
            saved = {key: day for key, day in self.fired.items() if day >= earliest}
            saved.update(candidates)
            if len(saved) > 4096:
                raise ValueError('timer ledger capacity exceeded')
            if self.ledger:
                save_json(self.ledger, saved)  # Record before execution, including skipped show events.
            self.fired = saved
        self.minute = minute
        if len(self.cache) > 64:
            self.cache = {}
        return result

    def public(self, now=None):
        now = self.local(now)
        rows = []
        for index, timer in enumerate(self.definitions):
            upcoming = []
            for delta in range(-1, 9):
                day = now.date() + dt.timedelta(days=delta)
                event = self.occurrence(timer, day, now.tzinfo)
                if event and event.astimezone(UTC) >= now.astimezone(UTC) and self.token(timer, day) not in self.fired:
                    upcoming.append(event)
            rows.append({'index': index, 'preset': timer['preset'],
                         'next': min(upcoming, key=lambda x: x.timestamp()).isoformat() if upcoming else None})
        solar = {}
        if self.location:
            for name in ('sunrise', 'sunset'):
                value = self.solar(now.date(), name)
                solar[name] = value.isoformat() if value else None
        return {'timezone': str(now.tzinfo), 'date': now.date().isoformat(), 'solar': solar, 'upcoming': rows}
