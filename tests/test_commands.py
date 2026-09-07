"""Compatibility examples from pinned util.cpp and lighting-only set.cpp."""
from copy import deepcopy
import unittest
from runtime.commands import number
from runtime.preset_import import import_presets
import test_compatibility as fixtures


class CommandTests(unittest.TestCase):
    setUp = fixtures.CompatibilityTests.setUp
    idle = fixtures.CompatibilityTests.idle
    save = fixtures.CompatibilityTests.save
    presets = fixtures.CompatibilityTests.presets
    def test_numeric_examples(self):
        for expr, current, expected in [('~', 255, 0), ('~-', 0, 255),
                                        ('~10', 250, 255), ('w~10', 255, 0),
                                        ('w~-10', 0, 255), ('~0', 42, 42),
                                        ('2~4~', 4, 2), ('2~4~-', 2, 4)]:
            self.assertEqual(number(expr, current, 0, 255, 'test'), expected)
        for expr in ('r', '~garbage', '4~2~', '256', True, '~+'):
            with self.assertRaises(ValueError):
                number(expr, 0, 0, 255, 'test')

    def test_relative_json_and_command_recall(self):
        self.save(1, o=True, n='Step', win='A=~10&SX=~-&R=23&W=45')
        self.assertIn('win', self.state.presets['1'])
        self.state.select(1)
        self.assertEqual(self.state.value['bri'], 138)
        self.assertEqual(self.state.value['seg'][0]['sx'], 127)
        self.assertEqual(self.state.value['seg'][0]['col'][0][::3], [23, 45])
        self.state.select(1)
        self.assertEqual(self.state.value['bri'], 148)
        self.controller.post('/json/state', {'bri': 'w~10', 'seg': {'sx': '~2'}})
        self.assertEqual(self.state.value['seg'][0]['sx'], 128)

    def test_command_target_selection(self):
        self.state.set({'seg': [{'id': 0, 'stop': 6}, {'id': 1, 'start': 6, 'stop': 12}]})
        self.state.set({'win': '/win&SX=42&RV=1'})
        self.assertEqual([s['sx'] for s in self.state.value['seg']], [42, 42])
        self.assertEqual([s['rev'] for s in self.state.value['seg']], [True, False])
        self.state.set({'win': 'win?SS=1&SX=77'})
        self.assertEqual([s['sx'] for s in self.state.value['seg']], [42, 77])

    def test_command_rejection_is_atomic(self):
        self.presets()
        self.state.start_playlist({'ps': [1, 2]})
        before = deepcopy(self.state.value)
        for cmd in ('A=42&PS=3', 'A=42&A=43', 'A=42&FP=200', 'A=42&SX=no', 'SS=31&A=42'):
            with self.assertRaises(ValueError):
                self.controller.post('/json/state', {'win': cmd})
            self.assertEqual(self.state.value, before)
            self.assertIsNotNone(self.state.playlist)

    def test_command_import_playlist_and_show_gate(self):
        incoming = {'1': {'n': 'Dim', 'win': 'A=42&SX=12'},
                    '2': {'playlist': {'ps': [1], 'dur': 0}}}
        preview = import_presets(self.state, {'presets': incoming})
        self.assertTrue(preview['valid'], preview)
        import_presets(self.state, {'presets': incoming, 'preview': False, 'revision': preview['revision']})
        self.state.select(2)
        self.assertEqual(self.state.value['bri'], 42)
        self.controller.ownership.command('show-start', 'test')
        before = deepcopy(self.state.value)
        with self.assertRaises(PermissionError):
            self.controller.post('/json/state', {'win': 'T=2'})
        self.save(3, o=True, win='A=~10')
        self.assertEqual(self.state.value, before)

    def test_preset_cycle_and_missing_target(self):
        self.presets()
        self.state.select(4)
        self.controller.post('/json/state', {'ps': '1~4~'})
        self.assertEqual(self.state.value['ps'], 1)
        before = deepcopy(self.state.value)
        with self.assertRaises(ValueError):
            self.state.select('5~6~')
        self.assertEqual(self.state.value, before)
        with self.assertRaises(ValueError):
            self.controller.post('/json/state', {'ps': 2, 'win': 'A=42&PS=3'})
        self.assertEqual(self.state.value, before)
