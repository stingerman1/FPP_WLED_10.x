"""Native recovery uses observed lighting, preserves ownership, and retries safely."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from runtime.devices import Devices
from runtime.native_restore import snapshot
from runtime.ownership import Ownership
from runtime.state import default_segment
from runtime.storage import read_json


class NativeRestoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.now = 0
        self.lock = threading.RLock()
        self.gate = Ownership(self.directory / 'ownership.json', clock=lambda: self.now)
        self.gate.observe([])
        self.gate.command('ambient-enable')
        self.idle()
        self.config = {'devices': [{'id': 'one', 'address': '192.0.2.1', 'mode': 'effect'}]}
        self.devices = Devices(self.config, self.gate, self.lock, self.directory)
        self.addCleanup(self.devices.close)
        self.recovery = self.devices.recovery
        self.recovery.clock = lambda: self.now / 1e9
        self.document = {'info': {'mac': '112233445566', 'live': False, 'ver': '16.0.1', 'leds': {'maxseg': 4}},
                         'state': {'on': False, 'bri': 73, 'transition': 7, 'ps': 3, 'pl': -1,
                                   'seg': [default_segment(12, 1)], 'nl': {'on': False},
                                   'lor': 2, 'udpn': {'send': True}, 'rb': True, 'usermod': {'danger': True}}}
        self.writes = []
        self.devices.request = self.request

    def idle(self):
        for _ in range(23):
            self.now += 100_000_000
            self.gate.observe([])

    def request(self, address, path, payload=None):
        if payload is not None:
            self.writes.append(deepcopy(payload))
            if 'playlist' in payload:
                self.document['state']['pl'] = -1
            if 'ps' in payload:
                self.document['state']['pl'] = payload['ps']
            return {'success': True}
        return deepcopy(self.document if path == '/json' else self.document[path.rsplit('/', 1)[1]])

    def tick(self):
        with self.lock:
            self.recovery.tick()
        self.devices.drain()

    def capture(self):
        self.tick()
        self.assertTrue(self.recovery.public('one')['snapshot_available'])

    def takeover(self):
        with self.lock:
            self.gate.command('show-start', 'show')

    def resume(self):
        with self.lock:
            self.gate.command('show-end', 'show')
        self.idle()
        with self.lock:
            self.devices.resume()
        self.tick()

    def test_restore_actual_state_with_safe_projection_and_persistence(self):
        self.devices.desired = {'one': {'bri': 200}}
        self.capture()
        self.takeover()
        self.document['state']['bri'] = 255
        self.document['state']['on'] = True
        self.resume()
        self.assertEqual(len(self.writes), 1)
        payload = self.writes[0]
        self.assertFalse(payload['on'])
        self.assertEqual(payload['bri'], 73)
        self.assertEqual(payload['pd'], 3)
        self.assertEqual(payload['udpn'], {'nn': True})
        self.assertEqual(len(payload['seg']), 4)
        self.assertEqual(payload['seg'][1], {'id': 1, 'stop': 0})
        for field in ('lor', 'live', 'rb', 'usermod', 'psave', 'pdel'):
            self.assertNotIn(field, payload)
        self.assertFalse(self.recovery.public('one')['restore_pending'])
        stored = read_json(self.directory / 'native-snapshots.json', {})
        self.assertEqual(stored['devices']['one']['payload']['bri'], 73)

    def test_explicit_capture_updates_cache_and_overlapping_locks_do_not_release(self):
        self.capture()
        self.document['state']['bri'] = 91
        self.takeover()
        self.recovery.capture_before_show(self.gate.epoch)
        self.gate.command('show-start', 'second')
        self.gate.command('show-end', 'show')
        self.idle()
        self.tick()
        self.assertEqual(self.writes, [])
        self.gate.command('show-end', 'second')
        self.idle()
        self.devices.resume()
        self.tick()
        self.assertEqual(self.writes[0]['bri'], 91)

    def test_realtime_defers_and_retries_until_device_releases(self):
        self.capture()
        self.takeover()
        self.document['info']['live'] = True
        self.resume()
        self.assertEqual(self.writes, [])
        self.assertTrue(self.recovery.public('one')['restore_pending'])
        self.document['info']['live'] = False
        self.idle()
        self.tick()
        self.assertEqual(len(self.writes), 1)

    def test_device_identity_change_never_receives_snapshot(self):
        self.capture()
        self.takeover()
        self.document['info']['mac'] = 'different-device'
        self.resume()
        self.assertEqual(self.writes, [])
        self.assertIn('identity changed', self.recovery.public('one')['recovery_detail'])

    def test_saved_playlist_selection_restarts_then_restores_power(self):
        self.document['state']['pl'] = 8
        self.capture()
        self.takeover()
        self.resume()
        self.assertEqual([set(p) - {'udpn'} for p in self.writes], [{'playlist'}, {'ps'}, {'on', 'bri'}])
        self.assertEqual(self.writes[1]['ps'], 8)
        self.assertFalse(self.writes[2]['on'])
        self.assertIn('beginning', self.recovery.public('one')['recovery_detail'])

    def test_unsupported_adhoc_playlist_and_nightlight_are_reported(self):
        for patch in ({'pl': 0}, {'pl': -1, 'nl': {'on': True}}):
            with self.subTest(patch=patch):
                self.document['state'].update(patch)
                self.recovery.next_poll.clear()
                self.recovery.pending.clear()
                self.capture()
                self.takeover()
                self.resume()
                self.assertEqual(self.writes, [])
                self.assertTrue(self.recovery.public('one')['restore_pending'])

    def test_restart_loads_snapshot_and_changed_address_blocks_restore(self):
        self.capture()
        self.takeover()
        other = Devices(self.config, self.gate, self.lock, self.directory)
        self.addCleanup(other.close)
        other.request = self.request
        self.gate.command('show-end', 'show')
        self.idle()
        other.resume()
        with self.lock:
            other.recovery.tick()
        other.drain()
        self.assertEqual(self.writes[0]['bri'], 73)
        self.writes.clear()
        other.config['one'] = {**other.config['one'], 'address': '192.0.2.2'}
        other.resume()
        with self.lock:
            other.recovery.tick()
        other.drain()
        self.assertEqual(self.writes, [])
        self.assertIn('address changed', other.recovery.public('one')['recovery_detail'])

    def test_new_command_cancels_restore_and_invalidates_old_snapshot(self):
        self.capture()
        self.document['info']['live'] = True
        self.takeover()
        self.resume()
        self.document['info']['live'] = False
        self.devices.command('one', {'bri': 100})
        self.devices.drain()
        self.assertEqual(self.writes, [{'bri': 100}])
        self.assertFalse(self.recovery.public('one')['restore_pending'])
        self.assertFalse(self.recovery.public('one')['snapshot_available'])

    def test_takeover_during_capture_discards_late_response(self):
        entered, release = threading.Event(), threading.Event()
        def delayed(*args):
            entered.set()
            release.wait(2)
            return self.request(*args)
        self.devices.request = delayed
        with self.lock:
            self.recovery.tick()
        self.assertTrue(entered.wait(1))
        self.takeover()
        release.set()
        self.devices.drain()
        self.assertFalse(self.recovery.public('one')['snapshot_available'])

    def test_takeover_between_realtime_check_and_write_is_blocked(self):
        self.capture()
        def racing(address, path, payload=None):
            if path == '/json/info':
                self.takeover()
            return self.request(address, path, payload)
        self.devices.request = racing
        self.devices.resume()
        self.tick()
        self.assertEqual(self.writes, [])

    def test_missing_realtime_flag_and_malformed_colors_reject_capture(self):
        bad = deepcopy(self.document)
        del bad['info']['live']
        with self.assertRaises(PermissionError):
            snapshot(bad, '192.0.2.1')
        bad = deepcopy(self.document)
        bad['state']['seg'][0]['col'] = ['r']
        with self.assertRaises(ValueError):
            snapshot(bad, '192.0.2.1')

    def test_unreachable_device_does_not_block_other_device_recovery(self):
        config = {'devices': [self.config['devices'][0], {'id': 'two', 'address': '192.0.2.2', 'mode': 'effect'}]}
        devices = Devices(config, self.gate, self.lock, self.directory / 'multi')
        self.addCleanup(devices.close)
        def request(address, path, payload=None):
            if address == '192.0.2.2':
                raise OSError('device unreachable')
            return self.request(address, path, payload)
        devices.request = request
        with self.lock:
            devices.recovery.tick()
        devices.drain()
        self.takeover()
        devices.recovery.capture_before_show(self.gate.epoch)
        self.gate.command('show-end', 'show')
        self.idle()
        devices.resume()
        with self.lock:
            devices.recovery.tick()
        devices.drain()
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(devices.recovery.public('two')['recovery'], 'capture failed')

    def test_explicit_capture_deadline_discards_late_show_state(self):
        self.capture()
        self.takeover()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def delayed(*args):
            entered.set()
            release.wait(2)
            return self.request(*args)
        self.devices.request = delayed
        def deadline(jobs, timeout):
            self.assertTrue(entered.wait(1))
            return set(), set(jobs)
        with patch('runtime.native_restore.wait', side_effect=deadline):
            self.recovery.capture_before_show(self.gate.epoch)
        self.document['state']['bri'] = 255
        release.set()
        self.devices.drain()
        self.assertEqual(self.recovery.saved['one']['payload']['bri'], 73)
        self.assertEqual(self.recovery.public('one')['recovery'], 'capture timeout')

    def test_native_rejection_remains_pending(self):
        self.capture()
        self.takeover()
        def rejected(address, path, payload=None):
            if payload is not None:
                return {'error': 9}
            return self.request(address, path)
        self.devices.request = rejected
        self.resume()
        self.assertTrue(self.recovery.public('one')['restore_pending'])
        self.assertIn('rejected', self.recovery.public('one')['recovery_detail'])

    def test_rejected_command_does_not_discard_checkpoint(self):
        self.capture()
        def rejected(address, path, payload=None):
            return {'error': 9} if payload is not None else self.request(address, path)
        self.devices.request = rejected
        self.devices.command('one', {'bri': 99})
        self.devices.drain()
        self.assertEqual(self.devices.public()[0]['last_command'], 'failed')
        self.assertTrue(self.recovery.public('one')['snapshot_available'])

    def test_failed_snapshot_write_preserves_previous_checkpoint(self):
        self.capture()
        original = deepcopy(self.recovery.saved)
        self.document['state']['bri'] = 99
        self.takeover()
        with patch('runtime.native_restore.save_json', side_effect=OSError('disk full')):
            self.recovery.capture_before_show(self.gate.epoch)
        self.assertEqual(self.recovery.saved, original)
        self.assertEqual(read_json(self.recovery.path, {})['devices'], original)
        self.assertEqual(self.recovery.public('one')['recovery'], 'capture failed')

    def test_snapshot_with_older_command_does_not_override_new_desired_intent(self):
        self.capture()
        # Simulate a crash after the desired command was saved but before the
        # old checkpoint could be invalidated by the device worker.
        self.devices.desired['one'] = {'bri': 201}
        self.takeover()
        self.resume()
        self.assertEqual(self.writes, [{'bri': 201}])

    def test_sync_and_stream_modes_do_not_get_http_snapshot_jobs(self):
        for mode in ('sync', 'fpp-stream'):
            self.devices.config['one']['mode'] = mode
            self.tick()
            self.takeover()
            self.recovery.capture_before_show(self.gate.epoch)
            self.resume()
        self.assertFalse(self.recovery.saved)
        self.assertEqual(self.writes, [])

    def test_http_wire_capture_and_restore(self):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self):
                self.reply(owner.request('', self.path))
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                self.reply(owner.request('', self.path, payload))
            def reply(self, data):
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.devices.config['one']['address'] = '127.0.0.1:' + str(server.server_port)
        self.devices.request = Devices.request.__get__(self.devices)
        self.capture()
        self.takeover()
        self.resume()
        self.assertEqual(self.writes[0]['bri'], 73)
