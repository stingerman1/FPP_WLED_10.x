"""Solar scheduling, calendar edge cases and atomic live editing."""
from copy import deepcopy
import datetime as dt
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
import test_compatibility as fixtures
from runtime.config import validate_schedule
from runtime.storage import read_json, save_json
from runtime.timers import Timers, UTC

CHICAGO = {'latitude': 41.88, 'longitude': -87.63, 'timezone': 'America/Chicago'}
ALL_DAYS = list(range(7))


def solar(event='sunset', offset=0, days=None):
    return {'event': event, 'offset': offset, 'days': ALL_DAYS if days is None else days, 'preset': 1}


class SolarTests(unittest.TestCase):
    def test_published_london_example_and_timezone(self):
        # Astral's published 2009-04-22 example: 04:50 UTC / 19:08 UTC.
        location = {'latitude': 51.5, 'longitude': -0.116, 'timezone': 'Europe/London'}
        timer = Timers([solar('sunrise'), solar()], location)
        day = dt.date(2009, 4, 22)
        for event, hour, minute in [('sunrise', 4, 50), ('sunset', 19, 8)]:
            value = timer.solar(day, event)
            expected = dt.datetime(2009, 4, 22, hour, minute, tzinfo=UTC)
            self.assertLess(abs((value - expected).total_seconds()), 120)
            self.assertEqual(value.utcoffset(), dt.timedelta(hours=1))
        rise = timer.solar(day, 'sunrise').replace(second=0, microsecond=0)
        self.assertEqual(timer.due(rise.astimezone(UTC)), [1])
        self.assertEqual(timer.due(rise), [])

    def test_offsets_cross_midnight_using_event_weekday(self):
        zone = ZoneInfo('America/Chicago')
        monday = dt.datetime(2026, 9, 7, 19, tzinfo=zone)
        timers = Timers([solar(offset=720, days=[0])], CHICAGO)
        with patch.object(timers, 'solar', return_value=monday):
            self.assertEqual(timers.due(monday + dt.timedelta(hours=12)), [1])
        timers = Timers([solar('sunrise', -720, [0])], CHICAGO)
        monday = monday.replace(hour=6)
        with patch.object(timers, 'solar', return_value=monday):
            self.assertEqual(timers.due(monday - dt.timedelta(hours=12)), [1])

    def test_dst_gap_and_repeated_hour(self):
        zone = ZoneInfo('America/Chicago')
        timer = {'hour': 2, 'minute': 30, 'preset': 1, 'days': [6]}
        schedules = Timers([timer], CHICAGO)
        self.assertIsNone(schedules.occurrence(timer, dt.date(2026, 3, 8), zone))
        timer = dict(timer, hour=1)
        with tempfile.TemporaryDirectory() as folder:
            ledger = Path(folder) / 'fired.json'
            schedules = Timers([timer], CHICAGO, ledger)
            first = dt.datetime(2026, 11, 1, 1, 30, tzinfo=zone)
            self.assertEqual(schedules.due(first), [1])
            restarted = Timers([dict(timer, event='clock')], CHICAGO, ledger)
            self.assertEqual(restarted.due(first), [])
            self.assertEqual(restarted.due(first.replace(fold=1)), [])
        fresh = Timers([timer], CHICAGO)
        self.assertEqual(fresh.due(first.replace(fold=1)), [])

    def test_polar_days_skip_solar_but_clock_runs(self):
        location = {'latitude': 78.2, 'longitude': 15.6, 'timezone': 'Arctic/Longyearbyen'}
        timer = Timers([solar('sunrise'), solar(), {'hour': 12, 'minute': 0, 'days': ALL_DAYS, 'preset': 2}], location)
        now = dt.datetime(2026, 6, 21, 12, tzinfo=ZoneInfo(location['timezone']))
        self.assertEqual(timer.public(now)['solar'], {'sunrise': None, 'sunset': None})
        self.assertEqual(timer.due(now), [2])

    def test_solar_offset_uses_elapsed_minutes_across_dst(self):
        zone = ZoneInfo('America/Chicago')
        event = dt.datetime(2026, 11, 1, 0, 30, tzinfo=zone)
        timers = Timers([solar(offset=120, days=[6])], CHICAGO)
        with patch.object(timers, 'solar', return_value=event):
            first = event.replace(hour=1)
            self.assertEqual(timers.due(first), [])
            self.assertEqual(timers.due(first.replace(fold=1)), [1])

    def test_dateline_event_keeps_local_date(self):
        location = {'latitude': 1.87, 'longitude': -157.4, 'timezone': 'Pacific/Kiritimati'}
        timers = Timers([solar('sunrise')], location)
        day = dt.date(2026, 9, 7)
        rise = timers.solar(day, 'sunrise').replace(second=0, microsecond=0)
        self.assertEqual(rise.date(), day)
        self.assertNotEqual(rise.astimezone(UTC).date(), day)
        self.assertEqual(timers.due(rise.astimezone(UTC)), [1])

    def test_missed_minutes_no_catchup_and_ledger_failure_no_dispatch(self):
        definitions = [{'hour': 19, 'minute': 0, 'preset': 1, 'days': ALL_DAYS}]
        now = dt.datetime(2026, 9, 7, 19, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as folder:
            timer = Timers(definitions, ledger=Path(folder) / 'fired.json')
            self.assertEqual(timer.due(now + dt.timedelta(minutes=1)), [])
            with patch('runtime.timers.save_json', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    timer.due(now)
            self.assertEqual(timer.fired, {})
            self.assertEqual(timer.due(now), [1])

    def test_strict_schedule_validation(self):
        for location in (dict(CHICAGO, latitude=True), dict(CHICAGO, latitude=float('nan')),
                         dict(CHICAGO, longitude=181), dict(CHICAGO, timezone='../bad')):
            with self.assertRaises(ValueError):
                validate_schedule(location, [])
        for timer in (solar(offset=721), dict(solar(), hour=5), dict(solar(), enabled='false'),
                      dict(solar(), days=[]), dict(solar(), event='moonrise')):
            with self.assertRaises(ValueError):
                validate_schedule(CHICAGO, [timer])
        with self.assertRaises(ValueError):
            validate_schedule(None, [solar()])


class ScheduleAPITests(unittest.TestCase):
    setUp = fixtures.CompatibilityTests.setUp
    idle = fixtures.CompatibilityTests.idle
    save = fixtures.CompatibilityTests.save

    def request(self):
        self.save(1, o=True, bri=42)
        return {'location': CHICAGO, 'timers': [solar()], 'preview': True}

    def test_preview_and_save_preserve_state_locks_and_pending_config(self):
        request = self.request()
        pending = dict(self.controller.config, port=9000)
        save_json(self.directory / 'config.json', pending)
        self.controller.ownership.command('show-start', 'test')
        before = deepcopy(self.state.value)
        preview = self.controller.post('/api/schedules', request)
        self.assertFalse(preview['saved'])
        self.assertEqual(self.controller.timers.definitions, [])
        result = self.controller.post('/api/schedules', dict(request, preview=False, revision=preview['revision']))
        self.assertTrue(result['saved'])
        self.assertEqual(self.state.value, before)
        self.assertTrue(self.controller.ownership.status()['show_owned'])
        self.assertEqual(self.controller.timers.location, CHICAGO)
        self.assertEqual(read_json(self.directory / 'config.json', {})['port'], 9000)
        self.assertNotEqual(self.controller.config.get('port'), 9000)

    def test_conflict_missing_preset_and_storage_failure_are_atomic(self):
        request = self.request()
        preview = self.controller.post('/api/schedules', request)
        request.update(preview=False, revision=preview['revision'])
        with patch('runtime.schedules.save_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.controller.post('/api/schedules', request)
        self.assertEqual(self.controller.timers.definitions, [])
        save_json(self.directory / 'config.json', dict(self.controller.config, port=9000))
        with self.assertRaises(ValueError):
            self.controller.post('/api/schedules', request)
        with self.assertRaises(ValueError):
            self.controller.post('/api/schedules', dict(request, preview=True, timers=[dict(solar(), preset=99)]))
        self.assertEqual(self.controller.timers.definitions, [])

    def test_show_event_consumed_before_resume_and_restart(self):
        self.save(1, o=True, bri=42)
        now = dt.datetime(2026, 9, 7, 19, tzinfo=UTC)
        definitions = [{'hour': 19, 'minute': 0, 'preset': 1, 'days': ALL_DAYS}]
        ledger = self.directory / 'timers-fired.json'
        self.controller.timers = Timers(definitions, ledger=ledger)
        self.controller.ownership.command('show-start', 'fixture')
        before = deepcopy(self.state.value)
        with patch.object(self.controller.timers, 'local', return_value=now):
            self.controller.tick(25)
        self.assertEqual(self.state.value, before)
        restarted = Timers(definitions, ledger=ledger)
        self.assertEqual(restarted.due(now), [])
        self.assertEqual(restarted.due(now + dt.timedelta(minutes=1)), [])

    def test_allowed_event_selects_saved_preset(self):
        self.save(1, o=True, bri=42)
        now = dt.datetime(2026, 9, 7, 19, tzinfo=UTC)
        self.controller.timers = Timers([{'hour': 19, 'minute': 0, 'preset': 1, 'days': ALL_DAYS}],
                                       ledger=self.directory / 'timers-fired.json')
        with patch.object(self.controller.timers, 'local', return_value=now):
            self.controller.tick(25)
        self.assertEqual(self.state.value['bri'], 42)
        self.assertEqual(self.state.value['ps'], 1)
