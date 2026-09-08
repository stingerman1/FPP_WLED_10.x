"""Sun nightlight semantics plus actual upstream effect frames."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import test_compatibility as fixtures
from runtime.state import State
from runtime.engine import Engine


class SunriseTests(unittest.TestCase):
    setUp = fixtures.CompatibilityTests.setUp
    idle = fixtures.CompatibilityTests.idle
    save = fixtures.CompatibilityTests.save

    def start(self, on=False):
        self.controller.post('/json/state', {'on': on, 'bri': 160, 'transition': 0,
                                           'nl': {'on': True, 'dur': 1, 'mode': 3}})
        self.controller.tick(25)

    def test_sunrise_uses_real_effect_and_holds_completed_sun(self):
        self.start(False)
        first = self.controller.latest_frame
        self.assertEqual(self.state.public()['seg'][0]['fx'], 104)
        self.assertEqual(self.state.public()['seg'][0]['sx'], 1)
        self.controller.tick(30000)
        middle = self.controller.latest_frame
        self.assertNotEqual(first, middle)
        self.assertGreater(sum(middle), sum(first))
        self.controller.tick(30000)
        self.assertTrue(self.state.value['on'])
        self.assertIsNone(self.state.nightlight)
        self.assertEqual(self.state.value['seg'][0]['fx'], 104)
        self.assertEqual(self.state.value['seg'][0]['sx'], 0)
        self.assertGreater(sum(self.controller.latest_frame), sum(middle))

    def test_sunset_restores_effect_settings_and_turns_off(self):
        self.state.set({'seg': {'fx': 9, 'sx': 42, 'pal': 11}})
        original = deepcopy(self.state.value['seg'])
        self.start(True)
        self.assertEqual(self.state.public()['seg'][0]['sx'], 61)
        first = self.controller.latest_frame
        self.controller.tick(30000)
        self.assertLess(sum(self.controller.latest_frame), sum(first))
        self.controller.tick(30000)
        self.assertFalse(self.state.value['on'])
        self.assertEqual(self.state.value['seg'], original)
        self.assertEqual(self.controller.latest_frame, bytes(36))

    def test_show_pauses_phase_and_does_not_reset_effect(self):
        self.start(False)
        self.controller.tick(20000)
        elapsed = self.state.nightlight.elapsed
        frame = self.controller.latest_frame
        timer = self.state.nightlight
        self.controller.ownership.command('show-start', 'test')
        self.controller.tick(30000)
        self.assertEqual(self.state.nightlight.elapsed, elapsed)
        self.assertEqual(self.controller.latest_frame, frame)
        self.controller.ownership.command('show-end', 'test')
        self.idle()
        with patch.object(self.controller.engine, 'apply', wraps=self.controller.engine.apply) as apply:
            self.controller.tick(1000)
            self.assertEqual(apply.call_count, 1)  # Resume applies state without the reset prepass.
        self.assertIs(self.state.nightlight, timer)
        self.assertGreaterEqual(sum(self.controller.latest_frame), sum(frame))

    def test_restarting_same_effect_restarts_its_phase(self):
        self.start(False)
        initial = self.controller.latest_frame
        self.controller.tick(30000)
        self.start(False)
        self.assertEqual(self.controller.latest_frame, initial)

    def test_cancel_restore_and_explicit_replacement(self):
        self.state.set({'seg': {'fx': 9, 'sx': 42, 'pal': 11}})
        self.start(False)
        self.controller.post('/json/state', {'nl': {'on': False}})
        self.assertEqual(self.state.value['seg'][0]['fx'], 9)
        self.assertTrue(self.state.value['on'])
        self.start(True)
        self.controller.post('/json/state', {'seg': {'fx': 0}, 'on': False})
        self.assertIsNone(self.state.nightlight)
        self.assertEqual(self.state.value['seg'][0]['fx'], 0)
        self.assertFalse(self.state.value['on'])

    def test_failure_atomic_and_restart_restores_saved_selection(self):
        self.state.set({'on': False, 'seg': {'fx': 9}})
        self.start(False)
        before = deepcopy(self.state.value)
        timer = self.state.nightlight
        with patch('runtime.state.save_json', side_effect=OSError('full')):
            with self.assertRaises(OSError):
                self.controller.post('/json/state', {'nl': {'on': False}})
        self.assertEqual(self.state.value, before)
        self.assertIs(self.state.nightlight, timer)
        restored = State(self.directory, self.state.engine)
        self.assertFalse(restored.public()['nl']['on'])
        self.assertFalse(restored.value['on'])
        self.assertEqual(restored.value['seg'][0]['fx'], 9)

    def test_duration_selection_and_freeze_validation(self):
        for body in ({'nl': {'on': True, 'mode': 3, 'dur': 61}},
                     {'seg': {'sel': False}, 'nl': {'on': True, 'mode': 3, 'dur': 1}},
                     {'seg': {'frz': True}, 'nl': {'on': True, 'mode': 3, 'dur': 1}},
                     {'seg': {'spc': 20}, 'nl': {'on': True, 'mode': 3, 'dur': 1}}):
            before = deepcopy(self.state.value)
            with self.assertRaises(ValueError):
                self.controller.post('/json/state', body)
            self.assertEqual(self.state.value, before)

    def test_preset_retains_original_selection_and_unselected_segments(self):
        self.state.set({'seg': [{'id': 0, 'stop': 6}, {'id': 1, 'start': 6, 'stop': 12, 'sel': False, 'fx': 9}]})
        original = deepcopy(self.state.value['seg'][1])
        self.save(1, o=True, on=False, nl={'on': True, 'mode': 3, 'dur': 1})
        self.state.select(1)
        self.assertEqual(self.state.public()['seg'][1], dict(original, lc=1))
        self.save(2)
        self.assertEqual(self.state.presets['2']['seg'][0]['fx'], 0)
        self.assertFalse(self.state.presets['2']['nl']['on'])

    def test_rgbw_matrix_animation_and_collapsed_geometry(self):
        config = {'pixels': {'count': 64, 'width': 8, 'height': 8, 'channels': 4}, 'devices': []}
        engine = Engine(fixtures.ROOT / 'build/libwled_linux.so', config)
        self.controller = fixtures.Controller(config, self.directory, engine, self.controller.ownership)
        self.addCleanup(self.controller.devices.close)
        self.state = self.controller.state
        self.start(False)
        initial = self.controller.latest_frame
        self.controller.tick(30000)
        self.assertEqual(len(self.controller.latest_frame), 256)
        self.assertNotEqual(initial, self.controller.latest_frame)
        with self.assertRaises(ValueError):
            self.controller.post('/json/state', {'seg': {'grp': 8}, 'nl': {'on': True, 'mode': 3, 'dur': 1}})
