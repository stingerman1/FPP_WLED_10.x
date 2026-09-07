"""Batch import must preserve lighting, ownership, and the previous catalog on failure."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime.engine import Engine
from runtime.ownership import Ownership
from runtime.service import Controller, ROOT
from runtime.storage import read_json


class PresetImportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        config = {'pixels': {'count': 12, 'channels': 3}, 'devices': []}
        engine = Engine(ROOT / 'build/libwled_linux.so', config)
        gate = Ownership(self.directory / 'ownership.json')
        self.controller = Controller(config, self.directory, engine, gate)
        self.addCleanup(self.controller.devices.close)
        self.state = self.controller.state

    def preview(self, presets):
        return self.controller.post('/api/presets/import', {'presets': presets})

    def commit(self, presets, report):
        return self.controller.post('/api/presets/import', {
            'presets': presets, 'preview': False, 'revision': report['revision']})

    def test_translation_forward_references_and_show_owned_import(self):
        presets = {'0': {}, '9': {'playlist': {'ps': [1], 'dur': 10}},
                   '1': {'n': 'Warm', 'bs': 0, 'ledmap': 0, 'seg': {'cct': 127, 'col': ['FFA000']}}}
        original = deepcopy(presets)
        self.controller.ownership.command('show-start', 'test:show')
        live = deepcopy(self.state.value)
        report = self.preview(presets)
        self.assertTrue(report['valid'])
        self.assertEqual(self.state.presets, {})
        self.assertFalse((self.directory / 'presets.json').exists())
        self.assertEqual(len(report['entries'][2]['translations']), 3)
        self.assertTrue(self.commit(presets, report)['saved'])
        self.assertEqual(presets, original)
        self.assertNotIn('0', self.state.presets)
        self.assertNotIn('bri', self.state.presets['1'])
        self.assertNotIn('cct', self.state.presets['1']['seg'])
        self.assertEqual(self.state.value, live)
        self.assertTrue(self.controller.ownership.status()['show_owned'])
        with self.assertRaises(PermissionError):
            self.controller.post('/json/state', {'ps': 1})
        self.assertEqual(read_json(self.directory / 'presets.json', {}), self.state.presets)

    def test_incompatible_batch_never_partially_saves(self):
        for bad in ({'seg': {'cct': 200}}, {'seg': {'stop': 99}}, {'win': 'A=255&PS=3'},
                    {'playlist': {'ps': [99]}}, {'n': '<script>'}, {'ps': 1}):
            with self.subTest(bad=bad):
                presets = {'1': {'bri': 30}, '2': bad}
                report = self.preview(presets)
                self.assertFalse(report['valid'])
                with self.assertRaises(ValueError):
                    self.commit(presets, report)
                self.assertEqual(self.state.presets, {})

    def test_revision_binds_both_catalog_and_input(self):
        presets = {'1': {'bri': 30}}
        report = self.preview(presets)
        with self.assertRaisesRegex(ValueError, 'preview again'):
            self.commit({'1': {'bri': 31}}, report)
        self.state.save_preset(2, {'bri': 60})
        with self.assertRaisesRegex(ValueError, 'preview again'):
            self.commit(presets, report)
        report = self.preview(presets)
        self.commit(presets, report)
        self.assertIn('2', self.state.presets)
        self.assertEqual(self.preview(presets)['overwritten'], ['1'])

    def test_existing_and_active_playlist_references_protected(self):
        self.state.save_preset(1, {'bri': 40})
        self.state.start_playlist({'ps': [1], 'dur': 10})
        live, cursor = deepcopy(self.state.value), self.state.remaining_ms
        presets = {'1': {'playlist': {'ps': [2]}}, '2': {'bri': 20}}
        report = self.preview(presets)
        self.assertFalse(report['valid'])
        self.assertIn('Active playlist', str(report['errors']))
        self.assertEqual(self.state.value, live)
        self.assertEqual(self.state.remaining_ms, cursor)
        self.state.stop_playlist()
        self.state.save_preset(3, {'playlist': {'ps': [1]}})
        self.assertFalse(self.preview(presets)['valid'])

    def test_storage_failure_preserves_catalog(self):
        self.state.save_preset(1, {'bri': 40})
        before = deepcopy(self.state.presets)
        presets = {'2': {'bri': 10}}
        report = self.preview(presets)
        with patch('runtime.preset_import.save_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.commit(presets, report)
        self.assertEqual(self.state.presets, before)
        self.assertEqual(read_json(self.directory / 'presets.json', {}), before)

    def test_invalid_ids_metadata_and_options(self):
        for presets in ({'01': {}}, {'0': {'bri': 1}}, {'251': {}}, {'1': []},
                        {'1': {'playlist': {'ps': [2]}, 'on': False}, '2': {}},
                        {'1': {'ql': 'label-too-long'}}):
            self.assertFalse(self.preview(presets)['valid'])
        with self.assertRaises(ValueError):
            self.controller.post('/api/presets/import', {'presets': {'1': {}}, 'preview': 1})
