#!/usr/bin/env python3
"""Validate complete releases and prune only unused, confined snapshots."""
import argparse
import json
import re
from pathlib import Path
import shutil

PAGES = ('plugin.php', 'settings.php', 'lights.php', 'credits.php', 'navigation.php', 'runtime-token.php')


def validate(build, target):
    release = target.resolve(strict=True)
    if release.parent != (build / 'releases').resolve(strict=True):
        raise ValueError('Release must be a direct child of build/releases.')
    if not (release / 'release.json').is_file():
        raise ValueError('Legacy release has no versioned PHP pages. Complete another plugin update before using rollback.')
    manifest = json.loads((release / 'release.json').read_text())
    if not isinstance(manifest, dict) or type(manifest.get('format')) is not int or manifest['format'] != 1:
        raise ValueError('Unsupported release format.')
    for name in ['runtime/service.py', 'web/settings.html', 'web/token-access.js',
                 'build/libwled_linux.so', 'libFPP_WLED_10.x.so',
                 *('pages/' + p for p in PAGES)]:
        if not (release / name).is_file():
            raise ValueError('Incomplete release: ' + name)
    return release


def prune(build, proc=Path('/proc')):
    releases = build / 'releases'
    if releases.is_symlink():
        print('Release cleanup deferred: build/releases must not be a symlink.')
        return
    if not releases.exists():
        return
    base = releases.resolve()
    protected = {(build / name).resolve() for name in ('current', 'previous')}
    # An old adapter can remain mapped into FPP until its next restart. Protect
    # mapped libraries as well as process cwd/exe/open descriptors.
    try:
        for process in proc.iterdir():
            if not process.name.isdecimal():
                continue
            try:
                references = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)),
                                    (process / 'maps').read_text())
                links = [process / 'cwd', process / 'exe', *(process / 'fd').iterdir()]
                for link in links:
                    try:
                        references += '\n' + str(link.readlink())
                    except FileNotFoundError:
                        pass
                for release in base.iterdir():
                    if str(release) + '/' in references or str(release) + '\n' in references + '\n':
                        protected.add(release)
            except (FileNotFoundError, ProcessLookupError):
                continue
    except OSError as error:
        print('Release cleanup deferred: cannot inspect live processes:', error)
        return
    for release in base.iterdir():
        if release.is_symlink() or not release.is_dir() or release.resolve().parent != base:
            continue
        if release in protected:
            continue
        # Only known snapshots, never arbitrary build directories.
        if (release / 'runtime/service.py').is_file() and (release / 'libFPP_WLED_10.x.so').is_file():
            shutil.rmtree(release)
            print('Removed unused release:', release.name)


def preflight(root):
    size = sum(p.stat().st_size for name in ('runtime', 'web', 'pages', 'licenses', 'build/ui')
               for p in (root / name).rglob('*') if p.is_file())
    # Allow room for binaries, compilation and the immutable copy.
    if shutil.disk_usage(root).free < size * 2 + 256 * 1024 * 1024:
        raise ValueError('Not enough free disk space for a safe WLED update (256 MiB plus two asset copies required).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prune', 'preflight', 'validate'))
    parser.add_argument('target', nargs='?')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.action == 'validate':
            print(validate(root / 'build', Path(args.target)))
        elif args.action == 'prune':
            prune(root / 'build')
        else:
            preflight(root)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
