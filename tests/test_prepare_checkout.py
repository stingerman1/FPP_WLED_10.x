"""Managed renderer caches upgrade safely, including shallow fork history."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.remote = self.root / 'remote'
        self.remote.mkdir()
        self.git(self.remote, 'init', '-b', 'port')
        self.git(self.remote, 'config', 'user.name', 'Fixture')
        self.git(self.remote, 'config', 'user.email', 'fixture@example.invalid')
        (self.remote / 'wled00').mkdir()
        (self.remote / 'wled00/FX.cpp').write_text('original release\n')
        self.base = self.commit('release')
        for index in range(3):
            (self.remote / 'port.txt').write_text(str(index))
            self.target = self.commit('port ' + str(index))
        script = Path(__file__).resolve().parents[1] / 'scripts/prepare_renderer.py'
        spec = importlib.util.spec_from_file_location('palette_prepare_fixture', script)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.ROOT = self.root
        self.module.SRC = self.root / 'cache'
        self.module.PORT_CHECKOUT = False
        self.module.LOCK = {'fork': self.remote.as_uri(), 'repository': self.remote.as_uri(), 'branch': 'port',
                            'port_commit': self.target, 'commit': self.base}

    @staticmethod
    def git(directory, *args):
        return subprocess.check_output(['git', '-C', str(directory), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self, message):
        self.git(self.remote, 'add', '.')
        self.git(self.remote, 'commit', '-m', message)
        return self.git(self.remote, 'rev-parse', 'HEAD')

    def test_shallow_clone_upgrade_and_rollback(self):
        self.module.prepare_checkout()
        cache = self.module.SRC
        self.assertEqual(self.git(cache, 'rev-parse', 'HEAD'), self.target)
        self.assertEqual(self.git(cache, 'rev-parse', self.base + ':wled00'), self.git(cache, 'rev-parse', 'HEAD:wled00'))
        (self.remote / 'port.txt').write_text('upgrade')
        upgrade = self.commit('upgrade')
        self.module.LOCK['port_commit'] = upgrade
        self.module.prepare_checkout()
        self.assertEqual(self.git(cache, 'rev-parse', 'HEAD'), upgrade)
        self.module.LOCK['port_commit'] = self.target
        self.module.prepare_checkout()
        self.assertEqual(self.git(cache, 'rev-parse', 'HEAD'), self.target)

    def test_modified_and_named_checkouts_are_preserved(self):
        self.module.prepare_checkout()
        cache = self.module.SRC
        (self.remote / 'port.txt').write_text('upgrade')
        self.module.LOCK['port_commit'] = self.commit('upgrade')
        (cache / 'port.txt').write_text('local work')
        with self.assertRaisesRegex(SystemExit, 'refusing to replace'):
            self.module.prepare_checkout()
        self.assertEqual((cache / 'port.txt').read_text(), 'local work')
        self.git(cache, 'restore', 'port.txt')
        self.git(cache, 'switch', '-c', 'local-work')
        with self.assertRaisesRegex(SystemExit, 'refusing to replace'):
            self.module.prepare_checkout()
        self.assertEqual(self.git(cache, 'branch', '--show-current'), 'local-work')

    def test_port_cannot_change_original_renderer_tree(self):
        (self.remote / 'wled00/FX.cpp').write_text('changed upstream')
        self.module.LOCK['port_commit'] = self.commit('invalid port')
        with self.assertRaisesRegex(SystemExit, 'altered the pinned upstream'):
            self.module.prepare_checkout()
