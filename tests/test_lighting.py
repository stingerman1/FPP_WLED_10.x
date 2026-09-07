"""Timed lighting, ownership pause, persistence and output preview regressions."""
from copy import deepcopy
import unittest
import test_compatibility as fixtures
from runtime.state import State
from runtime.preset_import import import_presets


class LightingTests(unittest.TestCase):
    setUp = fixtures.CompatibilityTests.setUp
    idle = fixtures.CompatibilityTests.idle
    save = fixtures.CompatibilityTests.save

    def start(self, mode=1, target=0):
        self.controller.post('/json/state', {'nl': {'on': True, 'dur': 1, 'mode': mode, 'tbri': target}})

    def test_brightness_fade_and_remembered_power(self):
        self.state.set({'bri': 100})
        self.start()
        self.state.tick_nightlight(30000)
        self.assertEqual(self.state.value['bri'], 50)
        self.assertEqual(self.state.public()['nl']['rem'], 30)
        self.state.tick_nightlight(30000)
        self.assertFalse(self.state.value['on'])
        self.assertEqual(self.state.value['bri'], 100)
        self.assertFalse(self.state.public()['nl']['on'])
        self.assertIsNone(self.state.nightlight)

    def test_delayed_change_and_fade_from_off(self):
        self.state.set({'bri': 100})
        self.start(mode=0, target=20)
        self.assertFalse(self.state.tick_nightlight(59000))
        self.assertEqual(self.state.value['bri'], 100)
        self.state.tick_nightlight(1000)
        self.assertEqual(self.state.value['bri'], 20)
        self.state.set({'on': False})
        self.start(target=200)
        self.state.tick_nightlight(30000)
        self.assertTrue(self.state.value['on'])
        self.assertEqual(self.state.value['bri'], 100)

    def test_selected_rgbw_color_fade(self):
        self.state.set({'seg': [{'id': 0, 'stop': 6, 'col': [[100, 0, 0, 80], [0, 100, 0, 0]]},
                               {'id': 1, 'start': 6, 'stop': 12, 'sel': False}]})
        other = deepcopy(self.state.value['seg'][1])
        self.start(mode=2, target=128)
        self.state.tick_nightlight(30000)
        self.assertEqual(self.state.value['seg'][0]['col'][0], [50, 50, 0, 40])
        self.assertEqual(self.state.value['seg'][1], other)
        self.state.tick_nightlight(30000)
        self.assertEqual(self.state.value['seg'][0]['col'][0], [0, 100, 0, 0])

    def test_show_pauses_and_rejects_live_edits(self):
        self.start()
        self.controller.tick(100)
        before = self.state.public()
        self.controller.ownership.command('show-start', 'fixture')
        self.controller.tick(30000)
        self.assertEqual(self.state.public(), before)
        with self.assertRaises(PermissionError):
            self.start(mode=0)
        self.save(1, o=True, nl={'on': True, 'dur': 1, 'mode': 2})
        self.assertEqual(self.state.public(), before)
        self.controller.ownership.command('show-end', 'fixture')
        self.idle()
        self.controller.tick(1000)
        self.assertLess(self.state.public()['nl']['rem'], before['nl']['rem'])

    def test_invalid_settings_preserve_active_timer_and_catalog(self):
        self.start()
        timer = self.state.nightlight
        before = deepcopy(self.state.value)
        for patch in ({'mode': 3}, {'dur': 0}, {'dur': True}, {'tbri': 256}, {'on': 1}, {'rem': 0}):
            with self.assertRaises(ValueError):
                self.controller.post('/json/state', {'bri': 42, 'nl': patch})
            self.assertEqual(self.state.value, before)
            self.assertIs(self.state.nightlight, timer)
        report = import_presets(self.state, {'presets': {'1': {'nl': {'mode': 3}}}})
        self.assertFalse(report['valid'])

    def test_manual_changes_cancel_and_restart_does_not_rearm(self):
        self.start()
        restored = State(self.directory, self.state.engine)
        self.assertFalse(restored.public()['nl']['on'])
        self.state.tick_nightlight(30000)
        brightness = self.state.value['bri']
        self.controller.post('/json/state', {'nl': {'on': False}})
        self.assertIsNone(self.state.nightlight)
        self.assertEqual(self.state.value['bri'], brightness)
        self.start()
        self.controller.post('/json/state', {'seg': {'fx': 9}})
        self.assertIsNone(self.state.nightlight)

    def test_preset_recall_and_playlist_rejection(self):
        self.save(1, o=True, nl={'on': True, 'dur': 1, 'mode': 0, 'tbri': 0})
        self.state.select(1)
        self.assertIsNotNone(self.state.nightlight)
        with self.assertRaises(ValueError):
            self.state.start_playlist({'ps': [1]})
        self.save(2)
        self.assertFalse(self.state.presets['2']['nl']['on'])

    def test_preview_tracks_renderer_and_clears_during_show(self):
        self.controller.tick(25)
        preview = self.controller.get('/api/preview')
        self.assertEqual(len(preview['pixels']), 12)
        self.assertEqual(preview['pixels'][0][1:], list(self.controller.latest_frame[:3]))
        self.controller.ownership.command('show-start', 'fixture')
        self.assertEqual(self.controller.get('/api/preview')['pixels'], [])
        self.assertFalse(self.controller.get('/api/preview')['allowed'])

    def test_preview_bounds_and_rgbw_matrix_metadata(self):
        # Supply an already-rendered large frame; preview must never render or
        # truncate channels while sampling, regardless of physical frame size.
        self.controller.config['pixels'] = {'count': 8192, 'channels': 4}
        self.controller.engine.width, self.controller.engine.height = 128, 64
        self.controller.latest_frame = bytes([10, 20, 30, 40]) * 8192
        before = deepcopy(self.state.value)
        preview = self.controller.get('/api/preview')
        self.assertEqual((preview['width'], preview['height'], preview['stride']), (128, 64, 2))
        self.assertEqual(len(preview['pixels']), 4096)
        self.assertEqual(preview['pixels'][-1], [8190, 10, 20, 30, 40])
        self.assertEqual(self.state.value, before)
