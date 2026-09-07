from copy import deepcopy
import http.client
import json
from pathlib import Path
import tempfile
import unittest
from runtime.config import validate
from runtime.engine import Engine
from runtime.ownership import Ownership
from runtime.service import Controller, ROOT
from runtime.web import start_servers


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.now = 0
        config = {'version': 1, 'bind': '127.0.0.1', 'port': 8787,
                  'pixels': {'count': 12, 'channels': 3},
                  'mappings': [{'channel': 100, 'pixel': 0, 'count': 12}], 'devices': []}
        validate(config)
        engine = Engine(ROOT / 'build/libwled_linux.so', config)
        ownership = Ownership(self.directory / 'ownership.json', clock=lambda: self.now)
        self.control = Controller(config, self.directory, engine, ownership)
        self.addCleanup(self.control.devices.close)

    def idle(self, ms):
        for _ in range(ms // 100):
            self.now += 100_000_000
            self.control.ownership.observe([])

    def enable(self):
        self.control.ownership.observe([])
        self.control.post('/api/command', {'operation': 'ambient-enable'})
        self.idle(2200)

    def test_presets_can_be_edited_during_show_without_live_changes(self):
        self.enable()
        self.control.post('/api/command', {'operation': 'show-start', 'source': 'test'})
        original = deepcopy(self.control.state.value)
        self.control.post('/json/state', {'psave': 1, 'n': 'Red', 'seg': {'col': [[255, 0, 0]]}})
        self.assertEqual(original, self.control.state.value)
        with self.assertRaises(PermissionError):
            self.control.post('/json/state', {'ps': 1})
        self.assertTrue((self.directory / 'presets.json').exists())

    def test_playlist_resumes_at_interrupted_entry(self):
        self.enable()
        for pid in (1, 2, 3):
            self.control.post('/json/state', {'psave': pid, 'seg': {'col': [[pid, 0, 0]]}})
        self.control.post('/json/state', {'playlist': {'ps': [1, 2, 3], 'dur': [10]}})
        self.control.tick(25)
        self.control.tick(1000)
        self.assertEqual(self.control.state.entry, 1)
        self.control.post('/api/command', {'operation': 'show-start', 'source': 'show'})
        self.assertFalse(self.control.tick(1000)[1])
        self.control.post('/api/command', {'operation': 'show-end', 'source': 'show'})
        self.idle(2200)
        self.control.tick(25)
        self.assertEqual(self.control.state.entry, 1)
        self.assertEqual(self.control.state.remaining_ms, 1000)

    def test_invalid_patch_is_atomic(self):
        self.enable()
        original = deepcopy(self.control.state.value)
        with self.assertRaises(ValueError):
            self.control.post('/json/state', {'bri': 255, 'seg': {'start': 8, 'stop': 5}})
        self.assertEqual(original, self.control.state.value)
        with self.assertRaises(ValueError):
            self.control.post('/json/state', {'lor': 1})

    def test_upstream_ui_selected_segments_and_partial_colors(self):
        self.enable()
        self.control.post('/json/state', {'seg': [
            {'id': 0, 'start': 0, 'stop': 6, 'sel': True},
            {'id': 1, 'start': 6, 'stop': 12, 'sel': True}]})
        self.control.post('/json/state', {'v': True, 'time': 1788800000,
            'seg': {'fx': 9, 'fxdef': True, 'col': [[], [3, 4, 5, None], []]}})
        for segment in self.control.state.value['seg']:
            self.assertEqual(segment['fx'], 9)
            self.assertEqual(segment['col'][1], [3, 4, 5, 0])
            self.assertEqual(segment['col'][0], [255, 160, 0, 0])

    def test_playlist_entry_survives_runtime_reconstruction(self):
        from runtime.state import State
        self.enable()
        for pid in (1, 2):
            self.control.post('/json/state', {'psave': pid, 'n': str(pid)})
        self.control.post('/json/state', {'playlist': {'ps': [1, 2], 'dur': [10]}})
        self.control.tick(25)
        self.control.tick(1000)
        restored = State(self.directory, self.control.engine)
        self.assertEqual(restored.entry, 1)
        self.assertEqual(restored.value['ps'], 2)
        self.assertEqual(restored.remaining_ms, 1000)

    def test_names_cannot_inject_html_into_upstream_ui(self):
        with self.assertRaises(ValueError):
            self.control.state.save_preset(1, {'n': '<img src=x onerror=alert(1)>'})
        with self.assertRaises(ValueError):
            self.control.state.set({'seg': {'n': '<script>'}})

    def test_upstream_cached_preset_recall_and_playlist_stop(self):
        self.enable()
        self.control.post('/json/state', {'psave': 1, 'n': 'Rainbow', 'seg': {'fx': 9}})
        preset = self.control.get('/presets.json')['1']
        self.assertNotIn('ps', preset)
        self.control.post('/json/state', {'pd': 1, **preset})
        self.assertEqual(self.control.state.value['ps'], 1)
        self.assertEqual(self.control.state.value['seg'][0]['fx'], 9)
        self.control.post('/json/state', {'playlist': {'ps': [1], 'dur': [10]}})
        self.control.post('/json/state', {'playlist': {}})
        self.assertIsNone(self.control.state.playlist)
        self.assertEqual(self.control.state.value['pl'], -1)

    def test_http_auth_gating_and_unsupported_endpoints(self):
        self.control.config['port'] = 0 # ephemeral port is test-only, bypasses install validation
        run_dir = self.directory / 'run'
        run_dir.mkdir()
        servers = start_servers(self.control, run_dir, self.directory)
        def close():
            for server in servers:
                server.stop_event.set()
                server.shutdown()
                server.server_close()
        self.addCleanup(close)
        port = servers[0].server_address[1]
        def request(method, path, body=None, token=False):
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
            headers = {'Content-Type': 'application/json'}
            if token:
                headers['Authorization'] = 'Bearer ' + servers[0].token
            conn.request(method, path, json.dumps(body) if body is not None else None, headers)
            response = conn.getresponse()
            data = response.read()
            conn.close()
            return response.status, data
        self.assertEqual(request('GET', '/api/status')[0], 200)
        self.assertEqual(request('GET', '/update')[0], 404)
        self.assertEqual(request('POST', '/json/state', {'on': True})[0], 401)
        self.assertEqual(request('POST', '/json/state', {'on': True}, True)[0], 409)
        self.enable()
        self.assertEqual(request('POST', '/json/state', {'bri': 64}, True)[0], 200)
        self.assertEqual(request('POST', '/json/state', {'bri': -1}, True)[0], 422)


class ConfigTests(unittest.TestCase):
    def test_boundaries_overlap_duplicate_devices(self):
        config = json.loads((ROOT / 'config.example.json').read_text())
        validate(config)
        config['mappings'].append({'pixel': 0, 'count': 1, 'channel': 2})
        with self.assertRaises(ValueError):
            validate(config)
        config['mappings'] = [{'pixel': 999, 'count': 2, 'channel': 1}]
        with self.assertRaises(ValueError):
            validate(config)
        config['mappings'] = []
        config['devices'] = [{'id': 'a', 'address': '192.0.2.1', 'mode': 'effect'},
                             {'id': 'b', 'address': '192.0.2.1', 'mode': 'fpp-stream'}]
        with self.assertRaises(ValueError):
            validate(config)
