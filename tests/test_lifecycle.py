import importlib.util
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LifecycleTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('php'), 'PHP required for FPP menu rendering')
    def test_menu_renders_links_for_fpp_sections(self):
        for section, page in [('status', 'plugin.php'), ('output', 'settings.php'), ('content', None), ('help', None)]:
            code = "$plugin = 'FPP_WLED_10.x'; $menu = '" + section + "'; include 'menu.inc';"
            result = subprocess.run(['php', '-r', code], cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertEqual(result.stderr, '')
            if page:
                self.assertEqual(result.stdout.count('<a '), 1)
                self.assertIn('plugin=FPP_WLED_10.x&amp;page=' + page, result.stdout)
            else:
                self.assertEqual(result.stdout.strip(), '')

    def test_uninstall_twice_with_isolated_service_manager_and_system_paths(self):
        self.uninstall_fixture(0)

    def test_apache_failure_does_not_skip_other_cleanup(self):
        self.uninstall_fixture(1)

    def uninstall_fixture(self, apache_exit):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / 'scripts'; scripts.mkdir()
            media = root / 'media'; (media / 'logs').mkdir(parents=True)
            data = media / 'plugindata/FPP_WLED_10.x'; data.mkdir(parents=True)
            (data / 'presets.json').write_text('{}')
            run = root / 'run/fpp-wled'; run.mkdir(parents=True)
            (run / 'runtime.lock').touch()
            etc = root / 'etc'
            for relative in ('systemd/system/fpp-wled.service', 'tmpfiles.d/fpp-wled.conf'):
                item = etc / relative; item.parent.mkdir(parents=True, exist_ok=True); item.touch()
            # Only privilege check/system path literals change in the fixture;
            # execute the production cleanup control flow and real file removal.
            source = (ROOT / 'scripts/fpp_uninstall.sh').read_text().replace('[[ $EUID -eq 0 ]]', 'true')
            source = source.replace('/etc/', str(etc) + '/').replace('/run/fpp-wled', str(run))
            (scripts / 'fpp_uninstall.sh').write_text(source)
            shutil.copy(ROOT / 'scripts/fpp-paths.sh', scripts)
            (scripts / 'configure-web.sh').write_text(f'#!/bin/bash\nexit {apache_exit}\n')
            fpp = root / 'fpp'; (fpp / 'scripts').mkdir(parents=True)
            (fpp / 'scripts/common').write_text(f'MEDIADIR="{media}"\nLOGDIR="$MEDIADIR/logs"\nsetSetting() {{ :; }}\n')
            binaries = root / 'bin'; binaries.mkdir()
            for name, body in [('systemctl', 'exit 0'), ('php', 'echo 0')]:
                item = binaries / name; item.write_text('#!/bin/sh\n' + body + '\n'); item.chmod(0o755)
            env = {**os.environ, 'FPPDIR': str(fpp), 'PATH': str(binaries) + ':' + os.environ['PATH']}
            for _ in range(2):
                result = subprocess.run(['bash', str(scripts / 'fpp_uninstall.sh')], env=env, capture_output=True)
                self.assertEqual(result.returncode, apache_exit)
            self.assertFalse(run.exists())
            self.assertFalse((etc / 'systemd/system/fpp-wled.service').exists())
            self.assertFalse((etc / 'tmpfiles.d/fpp-wled.conf').exists())
            self.assertTrue((data / 'presets.json').exists())

    def test_opted_in_data_removal_is_repeatable_and_confined(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory)
            ours = media / 'plugindata/FPP_WLED_10.x'; ours.mkdir(parents=True)
            (ours / 'presets.json').write_text('{}')
            other = media / 'plugindata/another-plugin'; other.mkdir()
            (media / 'config').mkdir()
            config = media / 'config/plugin.FPP_WLED_10.x'; config.write_text('deleteDataOnUninstall = "1"')
            purge = script('purge-data').purge
            purge(media); purge(media)
            self.assertFalse(ours.exists()); self.assertFalse(config.exists()); self.assertTrue(other.exists())

    def test_migration_preserves_bytes_permissions_and_repeated_install(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory)
            old = media / 'config/plugin.FPP_WLED_10.x'
            old.mkdir(parents=True)
            files = {'auth.json': b'{"token":"synthetic-only"}', 'ownership.json': b'{"locks":["show"]}',
                     'presets.json': b'{"1":{"bri":90}}', 'config.json': b'{"version":1}'}
            for name, data in files.items():
                (old / name).write_bytes(data); (old / name).chmod(0o600)
            migrate = script('migrate-data').migrate
            new = migrate(media)
            self.assertFalse(old.exists())
            self.assertEqual(migrate(media), new)
            for name, data in files.items():
                self.assertEqual((new / name).read_bytes(), data)
                self.assertEqual((new / name).stat().st_mode & 0o777, 0o600)
            old.mkdir()
            with self.assertRaises(ValueError): migrate(media)
            self.assertEqual((new / 'auth.json').read_bytes(), files['auth.json'])

    def test_service_paths_and_append_only_shared_runtime_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'relocated media'
            logs = media / 'logs'; logs.mkdir(parents=True)
            plugin = media / 'plugins/FPP_WLED_10.x'
            (plugin / 'build/current').mkdir(parents=True)
            fpp = root / 'fpp'; (fpp / 'scripts').mkdir(parents=True)
            binaries = root / 'bin'; binaries.mkdir()
            (fpp / 'scripts/common').write_text(f'MEDIADIR="{media}"\nLOGDIR="$MEDIADIR/logs"\nPLUGINDIR="$MEDIADIR/plugins"\n')
            python = binaries / 'python3'
            python.write_text('#!/bin/sh\necho "runtime started"\necho "native diagnostic" >&2\n')
            python.chmod(0o755)
            env = {**os.environ, 'FPPDIR': str(fpp), 'PATH': str(binaries) + ':' + os.environ['PATH']}
            for _ in range(2):
                subprocess.run(['bash', str(ROOT / 'scripts/run-runtime.sh')], env=env, check=True)
            log = logs / 'plugin-FPP_WLED_10.x.log'
            self.assertEqual(log.read_text().count('runtime started'), 2)
            self.assertEqual(log.read_text().count('native diagnostic'), 2)
            self.assertEqual(list(logs.iterdir()), [log])
            unit = script('render-service').render(str(plugin), str(media / 'plugindata/FPP_WLED_10.x'), str(logs), str(log))
            self.assertNotIn('@PLUGIN_DIR@', unit)
            self.assertNotIn('.venv', unit)
            self.assertIn('StandardOutput=append:' + str(log), unit)
            with self.assertRaises(ValueError): script('render-service').render('/bad\npath', '/data', '/logs', '/log')
