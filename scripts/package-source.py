#!/usr/bin/env python3
"""Package committed plugin and corresponding pinned WLED source, with checksums."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
lock = json.loads((ROOT / 'upstream.lock.json').read_text())
if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip():
    raise SystemExit('Commit the plugin changes before creating release source')
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
wled = ROOT / '.upstream/WLED-linux'
revision = lock['wled']['port_commit']
actual = subprocess.check_output(['git', '-C', str(wled), 'rev-parse', 'HEAD'], text=True).strip()
if actual != revision:
    raise SystemExit('Build the pinned Linux port before packaging')
output = ROOT / 'build/release'
output.mkdir(parents=True, exist_ok=True)
archives = []
for name, repository, ref in [('FPP_WLED_10.x', ROOT, commit), ('WLED-linux', wled, revision)]:
    path = output / (name + '-alpha.1-source.tar.gz')
    subprocess.run(['git', '-C', str(repository), 'archive', '--format=tar.gz',
                    '--prefix=' + name + '/', '--output=' + str(path), ref], check=True)
    with tarfile.open(path) as archive:
        if not archive.getmembers():
            raise SystemExit('Empty source archive')
    archives.append(path)
manifest = output / 'source-manifest.json'
manifest.write_text(json.dumps({'release': 'alpha.1', 'plugin_commit': commit,
                               'upstream': lock, 'type': 'source-only; no hardware certification'}, indent=2) + '\n')
archives.append(manifest)
checksums = output / 'SHA256SUMS'
checksums.write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n' for path in archives))
print(output)
