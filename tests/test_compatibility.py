"""Regression examples grounded in pinned WLED json.cpp/presets.cpp/playlist.cpp."""
from copy import deepcopy
from pathlib import Path
import random
import tempfile
import unittest
from runtime.engine import Engine
from runtime.ownership import Ownership
from runtime.service import Controller, ROOT
from runtime.state import State


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.now = 0
        config = {'pixels': {'count': 12, 'channels': 3}, 'devices': []}
        engine = Engine(ROOT / 'build/libwled_linux.so', config)
        gate = Ownership(self.directory / 'ownership.json', clock=lambda: self.now)
        self.controller = Controller(config, self.directory, engine, gate)
        self.addCleanup(self.controller.devices.close)
        self.state = self.controller.state
        gate.observe([])
        gate.command('ambient-enable')
        self.idle()

    def idle(self):
        for _ in range(23):
            self.now += 100_000_000
            self.controller.ownership.observe([])

    def save(self, pid, **patch):
        return self.controller.post('/json/state', {'psave': pid, **patch})

    def presets(self):
        for pid in range(1, 5):
            self.save(pid, seg={'col': [[pid, 0, 0]]})

    def test_save_flags_preserve_recall_brightness_and_geometry(self):
        self.state.set({'seg': [
            {'id': 0, 'stop': 6, 'sel': False},
            {'id': 1, 'start': 6, 'stop': 12, 'sel': True, 'fx': 9}]})
        self.save(1, ib=False, sb=False, sc=True, n='Rainbow', ql='🌈')
        saved = self.state.presets['1']
        self.assertNotIn('bri', saved)
        self.assertNotIn('on', saved)
        self.assertEqual([s['id'] for s in saved['seg']], [1])
        self.assertNotIn('stop', saved['seg'][0])
        self.state.set({'bri': 42, 'seg': [{'id': 1, 'start': 3, 'stop': 9, 'fx': 0}]})
        self.state.select(1)
        self.assertEqual(self.state.value['bri'], 42)
        self.assertEqual(self.state.value['seg'][1]['start'], 3)
        self.assertEqual(self.state.value['seg'][1]['stop'], 9)
        self.assertEqual(self.state.value['seg'][1]['fx'], 9)
        self.assertEqual(self.state.value['seg'][0]['fx'], 0)
        self.assertEqual(saved['ql'], '🌈')

    def test_bounded_snapshot_removes_later_extra_segments(self):
        self.save(1, ib=True, sb=True, sc=False)
        self.state.set({'seg': [{'id': 1, 'start': 6, 'stop': 12}]})
        self.state.select(1)
        self.assertEqual(len(self.state.value['seg']), 1)

    def test_custom_json_stays_partial_and_show_edit_does_not_change_live_state(self):
        self.controller.ownership.command('show-start', 'fixture')
        original = deepcopy(self.state.value)
        self.save(1, o=True, n='Dim', bri=42, ql='D')
        self.assertEqual(self.state.value, original)
        self.assertEqual(self.state.presets['1'], {'n': 'Dim', 'bri': 42, 'ql': 'D'})
        self.state.set({'seg': {'fx': 9}})
        self.controller.ownership.command('show-end', 'fixture')
        self.idle()
        self.controller.post('/json/state', {'ps': 1})
        self.assertEqual(self.state.value['seg'][0]['fx'], 9)
        self.assertEqual(self.state.value['bri'], 42)

    def test_neutral_export_fields_translate_but_real_unsupported_values_reject(self):
        patch = {'bs': 0, 'ledmap': 0, 'seg': {'cct': 127, 'set': 0, 'si': 0, 'bm': 0, 'fx': 9}}
        self.save(1, o=True, **patch)
        self.state.select(1)
        self.assertEqual(self.state.value['seg'][0]['fx'], 9)
        original = deepcopy(self.state.value)
        for bad in ({'bs': 2}, {'seg': {'cct': 20}}, {'seg': {'bm': 2}}):
            with self.assertRaises(ValueError):
                self.state.set(bad)
            self.assertEqual(self.state.value, original)

    def test_quick_label_validation_and_invalid_save_are_atomic(self):
        for label in ('<x>', '123456789', 42):
            with self.assertRaises(ValueError):
                self.save(1, ql=label)
        with self.assertRaises(ValueError):
            self.save(1, ib='false')
        with self.assertRaises(ValueError):
            self.save(1, o=True, ps=2)
        self.assertEqual(self.state.presets, {})

    def test_shuffled_order_and_interrupted_entry_survive_restart(self):
        self.presets()
        self.state.random = random.Random(4)
        self.state.start_playlist({'ps': [1, 2, 3, 4], 'dur': [1, 2, 3, 4], 'r': True})
        self.assertNotEqual(self.state.order, [0, 1, 2, 3])
        self.state.tick(0, advance=True)
        original_order, original_entry = list(self.state.order), self.state.entry
        pid = self.state.value['ps']
        restored = State(self.directory, self.state.engine)
        self.assertEqual(restored.order, original_order)
        self.assertEqual(restored.entry, original_entry)
        self.assertEqual(restored.value['ps'], pid)
        self.assertEqual(restored.remaining_ms, pid * 100)

    def test_indefinite_entry_requires_gated_next_and_negative_repeat_shuffles(self):
        self.presets()
        self.controller.post('/json/state', {'playlist': {'ps': [1, 2], 'dur': [0, 1], 'repeat': 1}})
        self.controller.tick(25)
        self.controller.tick(999999)
        self.assertEqual(self.state.value['ps'], 1)
        self.controller.ownership.command('show-start', 'fixture')
        with self.assertRaises(PermissionError):
            self.controller.post('/json/state', {'np': True})
        self.controller.ownership.command('show-end', 'fixture')
        self.idle()
        self.controller.post('/json/state', {'np': True})
        self.assertEqual(self.state.value['ps'], 2)
        self.state.start_playlist({'ps': [1, 2], 'repeat': -1})
        self.assertTrue(self.state.shuffled())
        self.assertEqual(self.state.repeats_left, 0)

    def test_short_duration_array_repeats_last_and_end255_restores_previous_preset(self):
        self.presets()
        self.state.select(4)
        self.state.start_playlist({'ps': [1, 2, 3], 'dur': [1, 2], 'transition': [0], 'repeat': 1, 'end': 255})
        self.state.tick(100)
        self.assertEqual(self.state.remaining_ms, 200)
        self.state.tick(200)
        self.assertEqual(self.state.remaining_ms, 200)
        restored = State(self.directory, self.state.engine)
        restored.tick(200)
        self.assertIsNone(restored.playlist)
        self.assertEqual(restored.value['ps'], 4)

    def test_corrupt_preset_recall_preserves_running_playlist(self):
        self.presets()
        self.state.start_playlist({'ps': [1, 2]})
        self.state.presets['3']['seg'][0]['fx'] = 10000
        with self.assertRaises(ValueError):
            self.state.select(3)
        self.assertIsNotNone(self.state.playlist)

    def test_shuffled_show_resume_does_not_reshuffle(self):
        self.presets()
        self.state.random = random.Random(7)
        self.controller.post('/json/state', {'playlist': {'ps': [1, 2, 3, 4], 'r': True, 'dur': 10}})
        self.controller.tick(25)
        self.controller.tick(1000)
        order, entry, pid = list(self.state.order), self.state.entry, self.state.value['ps']
        self.controller.ownership.command('show-start', 'fixture')
        self.assertFalse(self.controller.tick(10000)[1])
        self.controller.ownership.command('show-end', 'fixture')
        self.idle()
        self.assertTrue(self.controller.tick(25)[1])
        self.assertEqual((self.state.order, self.state.entry, self.state.value['ps']), (order, entry, pid))
        self.assertEqual(self.state.remaining_ms, 1000)

    def test_saved_return_preset_cannot_be_deleted_while_needed(self):
        self.presets()
        self.state.select(4)
        self.state.start_playlist({'ps': [1, 2], 'repeat': 1, 'end': 255})
        with self.assertRaises(ValueError):
            self.state.delete_preset(4)
        self.state.stop_playlist()
        self.state.delete_preset(4)
        self.assertNotIn('4', self.state.presets)
