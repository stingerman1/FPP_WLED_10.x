import json
from pathlib import Path
import tempfile
import unittest
from runtime.ownership import Ownership


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ownership.json'
        self.now = 0
        self.gate = Ownership(self.path, clock=lambda: self.now)

    def advance(self, ms, sources=()):
        for _ in range(ms // 100):
            self.now += 100_000_000
            self.gate.observe(sources)

    def enable(self):
        self.gate.observe(())
        self.gate.command('ambient-enable')
        self.advance(2200)

    def test_unknown_observer_and_quiet_period(self):
        self.assertFalse(self.gate.status()['allowed'])
        with self.assertRaises(PermissionError):
            self.gate.command('ambient-enable')
        self.enable()
        self.assertTrue(self.gate.status()['allowed'])

    def test_overlapping_persistent_locks(self):
        self.enable()
        self.gate.command('show-start', 'local:main')
        self.gate.command('show-start', 'xschedule:other')
        self.gate.command('show-start', 'local:main')
        self.gate.command('show-end', 'local:main')
        self.advance(3000)
        self.assertFalse(self.gate.status()['allowed'])
        restored = Ownership(self.path, clock=lambda: self.now)
        self.assertEqual(restored.locks, {'xschedule:other'})
        self.assertTrue(restored.enabled)
        self.gate.command('show-end', 'xschedule:other')
        self.advance(1900)
        self.assertFalse(self.gate.status()['allowed'])
        self.advance(300)
        self.assertTrue(self.gate.status()['allowed'])

    def test_pause_gaps_black_live_and_remote_sources(self):
        self.enable()
        for source in ('fpp:playlist', 'fpp:sequence', 'fpp:live'):
            self.advance(3000, [source])
            self.assertFalse(self.gate.status()['allowed'])
            self.advance(1000)
            self.assertFalse(self.gate.status()['allowed'])
        self.advance(2200)
        self.assertTrue(self.gate.status()['allowed'])

    def test_expired_and_recovered_observer_restarts_quiet(self):
        self.enable()
        self.now += 501_000_000
        self.assertFalse(self.gate.status()['allowed'])
        self.advance(1900)
        self.assertFalse(self.gate.status()['allowed'])
        self.advance(300)
        self.assertTrue(self.gate.status()['allowed'])

    def test_disable_during_show_stays_disabled(self):
        self.enable()
        self.gate.command('show-start', 'show')
        self.gate.command('ambient-disable')
        self.gate.command('show-end', 'show')
        self.advance(3000)
        self.assertFalse(self.gate.status()['enabled'])
        self.assertFalse(self.gate.status()['allowed'])

    def test_corrupt_storage_fails_closed(self):
        self.path.write_text('{truncated')
        gate = Ownership(self.path)
        self.assertIsNotNone(gate.status()['fault'])
        with self.assertRaises(ValueError):
            gate.command('ambient-enable')

    def test_invalid_or_reserved_source(self):
        for source in ('', '../ bad', 'fpp:live', None, 'x' * 129):
            with self.assertRaises(ValueError):
                self.gate.command('show-start', source)
