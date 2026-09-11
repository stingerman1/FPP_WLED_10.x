import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_lifecycle import ROOT, script


class ReleaseTests(unittest.TestCase):
    def test_rollback_activation_failure_restores_original_release(self):
        for fail_health in (False, True):
            with self.subTest(fail_health=fail_health), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); scripts = root / 'scripts'; scripts.mkdir()
                module = script('releases')
                build = root / 'build'; base = build / 'releases'; base.mkdir(parents=True)
                for name in ('old', 'new'):
                    release = base / name
                    for file in ['runtime/service.py', 'web/settings.html', 'web/token-access.js',
                                 'build/libwled_linux.so', 'libFPP_WLED_10.x.so',
                                 *('pages/' + p for p in module.PAGES)]:
                        target = release / file; target.parent.mkdir(parents=True, exist_ok=True); target.touch()
                    (release / 'release.json').write_text('{"format":1}')
                (build / 'current').symlink_to(base / 'new'); (build / 'previous').symlink_to(base / 'old')
                source = (ROOT / 'scripts/rollback.sh').read_text().replace('[[ $EUID -eq 0 ]]', 'true')
                (scripts / 'rollback.sh').write_text(source)
                shutil.copy(ROOT / 'scripts/releases.py', scripts)
                (scripts / 'verify-abi.py').write_text('')
                (scripts / 'check-health.py').write_text('raise SystemExit(' + str(int(fail_health)) + ')')
                (scripts / 'fpp-paths.sh').write_text(f'FPPDIR="{root}"\nPLUGIN_STATE="{root}"\nsetSetting() {{ :; }}\n')
                binaries = root / 'bin'; binaries.mkdir()
                for name, body in [('systemctl', 'exit 0'), ('runuser', 'shift 3\nexec "$@"')]:
                    executable = binaries / name; executable.write_text('#!/bin/sh\n' + body + '\n'); executable.chmod(0o755)
                result = subprocess.run(['bash', str(scripts / 'rollback.sh')], capture_output=True, text=True,
                                        env={**os.environ, 'PATH': str(binaries) + ':' + os.environ['PATH']})
                self.assertEqual(result.returncode, int(fail_health), result.stderr)
                self.assertEqual((build / 'current').resolve(), base / ('new' if fail_health else 'old'))
                self.assertEqual((build / 'previous').resolve(), base / ('old' if fail_health else 'new'))

    def test_prune_protects_selected_and_loaded_and_ignores_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); build = root / 'build'; base = build / 'releases'; base.mkdir(parents=True)
            for name in ('current', 'previous', 'mapped', 'unused'):
                release = base / name; (release / 'runtime').mkdir(parents=True)
                (release / 'runtime/service.py').touch(); (release / 'libFPP_WLED_10.x.so').touch()
            for name in ('current', 'previous'): (build / name).symlink_to(base / name)
            (base / 'unknown').mkdir()
            (base / 'external').symlink_to(root, target_is_directory=True)
            proc = root / 'proc'; process = proc / '42'; (process / 'fd').mkdir(parents=True)
            (process / 'maps').write_text('123 r-x ' + str(base / 'mapped/libFPP_WLED_10.x.so') + '\n')
            script('releases').prune(build, proc)
            self.assertFalse((base / 'unused').exists())
            for name in ('current', 'previous', 'mapped', 'unknown', 'external'): self.assertTrue((base / name).exists())

    def test_preflight_rejects_low_space(self):
        module = script('releases')
        with patch.object(module.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(100, 99, 1)):
            with self.assertRaises(ValueError): module.preflight(ROOT)

    def test_unreadable_process_defers_pruning(self):
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory) / 'build'; release = build / 'releases/keep'
            (release / 'runtime').mkdir(parents=True)
            (release / 'runtime/service.py').touch(); (release / 'libFPP_WLED_10.x.so').touch()
            proc = Path(directory) / 'proc'; (proc / '42').mkdir(parents=True)
            with patch.object(Path, 'read_text', side_effect=PermissionError('fixture')):
                script('releases').prune(build, proc)
            self.assertTrue(release.exists())

    def test_validation_rejects_legacy_and_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory) / 'build'; release = build / 'releases/legacy'; release.mkdir(parents=True)
            module = script('releases')
            with self.assertRaisesRegex(ValueError, 'Legacy'): module.validate(build, release)
            with self.assertRaisesRegex(ValueError, 'direct child'): module.validate(build, Path(directory))

    @unittest.skipUnless(shutil.which('php'), 'PHP required')
    def test_php_dispatch_follows_release_and_rejects_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); releases = root / 'build/releases'; releases.mkdir(parents=True)
            shutil.copy(ROOT / 'page-loader.php', root)
            shutil.copy(ROOT / 'settings.php', root)
            current = root / 'build/current'
            for name in ('old', 'new'):
                release = releases / name; (release / 'pages').mkdir(parents=True)
                (release / 'release.json').write_text(json.dumps({'format': 1}))
                (release / 'pages/settings.php').write_text('<?php echo "' + name + '";')
            def render():
                return subprocess.check_output(['php', str(root / 'settings.php')], text=True)
            for name in ('new', 'old'):
                current.unlink(missing_ok=True); current.symlink_to(releases / name)
                self.assertEqual(render(), name)
            (releases / 'old/pages/settings.php').unlink()
            self.assertIn('Incomplete WLED release', render())
