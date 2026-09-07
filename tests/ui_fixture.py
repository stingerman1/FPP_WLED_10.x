"""Local development only: simulated FPP observer for browser verification."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.ipc import FRAME, OBSERVER
from runtime.service import ROOT

with tempfile.TemporaryDirectory(prefix='wled-ui-') as directory:
    path = Path(directory)
    config = {'version': 1, 'bind': '127.0.0.1', 'port': 18787,
              'pixels': {'count': 1000, 'channels': 3},
              'mappings': [{'pixel': 0, 'count': 1000, 'channel': 1}], 'devices': []}
    (path / 'config.json').write_text(json.dumps(config))
    (path / 'ownership.json').write_text(json.dumps({'version': 1, 'enabled': True, 'locks': []}))
    (path / 'auth.json').write_text(json.dumps({'token': 'local-browser-test-token-not-for-deployment'}))
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    listener.bind(str(path / 'frames.sock'))
    listener.settimeout(0.02)
    process = subprocess.Popen([sys.executable, '-m', 'runtime.service', '--state-dir', str(path), '--run-dir', str(path)], cwd=ROOT)
    print('Simulated FPP UI fixture: http://localhost:18787', flush=True)
    serial, allowed = 0, False
    try:
        while process.poll() is None:
            try:
                packet = listener.recv(70000)
                frame = FRAME.unpack_from(packet)
                serial, allowed = frame[3], bool(frame[2])
            except socket.timeout:
                pass
            try:
                listener.sendto(OBSERVER.pack(b'FPO1', 1, 16 if allowed else 0, time.monotonic_ns(), 444, serial), str(path / 'observer.sock'))
            except (FileNotFoundError, ConnectionRefusedError):
                pass
    finally:
        process.terminate()
        process.wait(timeout=10)
        listener.close()
