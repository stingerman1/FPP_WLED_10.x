import datetime
from pathlib import Path
import tempfile
import threading
import unittest
from runtime.devices import Devices
from runtime.integrations import ha_command
from runtime.ownership import Ownership
from runtime.state import default_segment
from runtime.timers import Timers
from runtime.udp import encode, decode


class NetworkTests(unittest.TestCase):
    def test_udp_v12_roundtrip_and_malformed_packets(self):
        segment = default_segment(100, 1)
        segment.update(fx=9, sx=42, ix=80, pal=11, c1=200, o1=True)
        state = {'on': True, 'bri': 64, 'transition': 7, 'seg': [segment]}
        packet = encode(state, 2)
        self.assertEqual(packet[11], 12)
        decoded = decode(packet, 2)
        self.assertEqual(decoded['bri'], 64)
        self.assertEqual(decoded['seg'][0]['fx'], 9)
        self.assertEqual(decoded['seg'][0]['c1'], 200)
        self.assertTrue(decoded['seg'][0]['o1'])
        for size in range(len(packet)):
            with self.assertRaises(ValueError):
                decode(packet[:size], 2)
        with self.assertRaises(ValueError):
            decode(packet, 1)
        with self.assertRaises(ValueError):
            decode(bytes([1]) + packet[1:], 2)

    def test_home_assistant_translation(self):
        patch = ha_command({'state': 'ON', 'brightness': 123, 'effect': 'Rainbow',
                            'color': {'r': 20, 'g': 30, 'b': 40}, 'transition': 0.5}, ['Solid', 'Rainbow'])
        self.assertEqual(patch, {'on': True, 'bri': 123, 'transition': 5,
                                 'seg': {'fx': 1, 'col': [[20, 30, 40, 0]]}})
        with self.assertRaises(ValueError):
            ha_command({'lor': 1}, [])

    def test_native_takeover_and_realtime_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [0]
            gate = Ownership(Path(directory) / 'ownership.json', clock=lambda: now[0])
            gate.observe([])
            gate.command('ambient-enable')
            for index in range(23):
                now[0] = index * 100_000_000
                gate.observe([])
            lock = threading.RLock()
            devices = Devices({'devices': [{'id': 'one', 'address': '192.0.2.1', 'mode': 'effect'}]},
                              gate, lock, Path(directory))
            self.addCleanup(devices.close)
            entered, release = threading.Event(), threading.Event()
            writes = []
            def request(address, path, payload=None):
                if payload is not None:
                    writes.append(payload)
                else:
                    entered.set()
                    release.wait(2)
                return {'ver': '16.0.1', 'live': False}
            devices.request = request
            devices.command('one', {'ps': 1})
            self.assertTrue(entered.wait(1))
            with lock:
                gate.command('show-start', 'show')
            release.set()
            devices.drain()
            self.assertEqual(writes, [])
            self.assertEqual(devices.public()[0]['last_command'], 'blocked')
            gate.command('show-end', 'show')
            for _ in range(23):
                now[0] += 100_000_000
                gate.observe([])
            devices.request = lambda *_: {'ver': '16.0.1', 'live': True}
            devices.command('one', {'ps': 1})
            devices.drain()
            self.assertIn('realtime', devices.public()[0]['error'])

    def test_timers_once_per_minute_and_skipped_show_event(self):
        timers = Timers([{'hour': 19, 'minute': 30, 'days': [0], 'preset': 2}])
        now = datetime.datetime(2026, 9, 7, 19, 30)
        self.assertEqual(timers.due(now), [2])
        self.assertEqual(timers.due(now), [])
        self.assertEqual(timers.due(now + datetime.timedelta(minutes=1)), [])
