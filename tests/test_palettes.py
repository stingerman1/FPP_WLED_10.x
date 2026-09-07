"""Custom palette IDs, native gradients, rendering, ownership and persistence."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime.engine import Engine
from runtime.ownership import Ownership
from runtime.palettes import normalize
from runtime.service import Controller, ROOT
from runtime.storage import read_json


class PaletteTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.now = 0
        self.config = {'pixels': {'count': 12, 'channels': 3}, 'devices': []}
        self.engine = Engine(ROOT / 'build/libwled_linux.so', self.config)
        self.gate = Ownership(self.directory / 'ownership.json', clock=lambda: self.now)
        self.control = Controller(self.config, self.directory, self.engine, self.gate)
        self.addCleanup(self.control.devices.close)

    def save(self, slot=0, colors=None):
        return self.control.post('/api/palettes', {'slot': slot, 'palette': colors or [0, 'FF0000', 255, 'FF0000']})

    def enable(self):
        self.gate.observe([])
        self.gate.command('ambient-enable')
        for _ in range(23):
            self.now += 100_000_000
            self.gate.observe([])

    def test_native_formats_and_strict_gradient_boundaries(self):
        numeric = {'palette': [0, 255, 0, 0, 255, 0, 0, 255]}
        self.assertEqual(normalize({'palette': [0, 'AAFF0000', 255, '0000ff']}), numeric)
        self.assertEqual(normalize(numeric), numeric)
        for stops in ([1, 'FF0000', 255, '000000'], [0, 'FF0000', 254, '000000'],
                      [0, 'FF0000', 200, '000000', 100, '000000', 255, '000000'],
                      [0, 'FF0000', 255, '000000', 255, 'FFFFFF'],
                      [False, 'FF0000', 255, '000000'], [0, '#FF0000', 255, '000000'],
                      [0, 256, 0, 0, 255, 0, 0, 0], [0, 'FFFFFF']):
            with self.subTest(stops=stops), self.assertRaises(ValueError):
                normalize({'palette': stops})

    def test_fixed_previews_and_pagination_match_upstream_shape(self):
        previews = {}
        first = self.control.get('/json/palx')
        for page in range(first['m'] + 1):
            previews.update(self.control.get('/json/palx?page=' + str(page))['p'])
        self.assertEqual(set(previews), {str(i) for i in range(len(self.engine.palettes))})
        self.assertEqual(previews['1'], ['r'] * 4)
        self.assertEqual(previews['2'], ['c1'])
        self.assertEqual(len(previews['0']), 16)
        self.assertEqual(previews['13'][0][0], 0)
        self.assertEqual(previews['13'][-1][0], 255)
        self.assertEqual(self.control.get('/json/palx?page=99999')['m'], first['m'])
        for query in ('page=-1', 'page=no', 'page=1&page=2', 'other=1'):
            with self.assertRaises(ValueError):
                self.control.get('/json/palx?' + query)

    def test_custom_ids_gaps_and_native_export(self):
        self.save(2)
        self.assertEqual(self.control.info()['cpalcount'], 3)
        self.assertEqual(self.control.info()['palcount'], len(self.engine.palettes) + 3)
        self.assertIn(198, self.engine.palette_ids)
        self.assertNotIn(199, self.engine.palette_ids)
        self.assertEqual(self.control.get('/palette2.json'), {'palette': [0, 255, 0, 0, 255, 255, 0, 0]})
        self.assertEqual(self.control.palettes.previews['199'], [[i * 16, 128, 128, 128] for i in range(16)])
        with self.assertRaises(ValueError):
            self.control.state.merge({'seg': {'pal': 199}})
        self.assertEqual(self.control.state.merge({'seg': {'pal': 198}})['seg'][0]['pal'], 198)
        self.save(self.control.palettes.max_slot)
        self.assertIn(len(self.engine.palettes), self.engine.palette_ids)

    def test_uniform_custom_palette_renders_and_updates_without_id_change(self):
        self.save()
        self.enable()
        self.control.post('/json/state', {'bri': 255, 'transition': 0, 'seg': {'fx': 65, 'pal': 200}})
        for _ in range(40):
            self.now += 25_000_000
            self.gate.observe([])
            frame, allowed = self.control.tick(25)
        self.assertTrue(allowed)
        self.assertTrue(any(frame[::3]))
        self.assertFalse(any(frame[1::3]) or any(frame[2::3]))
        before = self.control.info()['palrev']
        self.save(colors=[0, '0000FF', 255, '0000FF'])
        self.assertNotEqual(before, self.control.info()['palrev'])
        for _ in range(40):
            self.now += 25_000_000
            self.gate.observe([])
            frame, _ = self.control.tick(25)
        self.assertTrue(any(frame[2::3]))
        self.assertFalse(any(frame[::3]) or any(frame[1::3]))

    def test_palette_previews_do_not_mutate_render_clock_or_state(self):
        before = deepcopy(self.control.state.value)
        clock = self.control.render_ms
        self.save(colors=[0, 'FF0000', 128, '00FF00', 255, '0000FF'])
        previews = self.control.get('/api/palettes')['previews']['200']
        self.assertEqual(previews[0], [0, 255, 0, 0])
        self.assertEqual(previews[-1], [240, 0, 0, 255])
        self.assertEqual(self.control.state.value, before)
        self.assertEqual(self.control.render_ms, clock)

    def test_palette_lifecycle_protects_show_and_preset_references(self):
        self.save()
        self.control.state.set({'seg': {'pal': 200}})
        self.gate.command('show-start', 'show')
        before = deepcopy(self.control.palettes.saved)
        with self.assertRaises(PermissionError):
            self.save(colors=[0, '00FF00', 255, '00FF00'])
        self.assertEqual(before, self.control.palettes.saved)
        self.save(1)  # editing an inactive saved palette is allowed during shows
        with self.assertRaises(ValueError):
            self.control.post('/json/state', {'rmcpal': 0})
        self.control.state.save_preset(1, {'seg': {'pal': 199}})
        with self.assertRaises(ValueError):
            self.control.post('/api/palettes', {'slot': 1, 'delete': True})
        self.control.state.delete_preset(1)
        self.control.post('/json/state', {'rmcpal': 1})
        self.assertNotIn(199, self.engine.palette_ids)

    def test_persistence_failure_leaves_runtime_palette_table_unchanged(self):
        self.save()
        before = self.control.get('/api/palettes')
        with patch('runtime.palettes.save_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.save(colors=[0, '00FF00', 255, '00FF00'])
        self.assertEqual(self.control.get('/api/palettes'), before)
        self.assertEqual(read_json(self.control.palettes.path, {})['palettes'], before['palettes'])

    def test_custom_palette_loads_before_saved_state_and_preset_import(self):
        self.save()
        self.control.state.set({'seg': {'pal': 200}})
        engine = Engine(ROOT / 'build/libwled_linux.so', self.config)
        control = Controller(self.config, self.directory, engine, self.gate)
        self.addCleanup(control.devices.close)
        self.assertEqual(control.state.value['seg'][0]['pal'], 200)
        report = control.post('/api/presets/import', {'presets': {'1': {'seg': {'pal': 200}}}})
        self.assertTrue(report['valid'])
        report = control.post('/api/presets/import', {'presets': {'1': {'seg': {'pal': 199}}}})
        self.assertFalse(report['valid'])
