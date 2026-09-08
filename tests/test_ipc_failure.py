import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from runtime.ipc import OBSERVER


class IPCFailureTests(unittest.TestCase):
    @unittest.skipIf(os.geteuid() == 0, 'Requires unprivileged runtime to exercise EACCES')
    def test_permission_failure_keeps_http_alive_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            frames.bind(str(root / 'frames.sock'))
            frames.setblocking(False)
            (root / 'frames.sock').chmod(0)
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1', 0)); port = reserve.getsockname()[1]
            config = {'version': 1, 'bind': '127.0.0.1', 'port': port, 'pixels': {'count': 1, 'channels': 3},
                      'mappings': [{'pixel': 0, 'channel': 1, 'count': 1}], 'devices': []}
            (root / 'config.json').write_text(json.dumps(config))
            (root / 'ownership.json').write_text(json.dumps({'version': 1, 'enabled': True, 'locks': []}))
            process = subprocess.Popen([sys.executable, '-m', 'runtime.service', '--state-dir', directory, '--run-dir', directory],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            def sample():
                while True:
                    try: frames.recv(70000)
                    except BlockingIOError: break
                try: frames.sendto(OBSERVER.pack(b'FPO1', 1, 0, time.monotonic_ns(), 42, 0), str(root / 'observer.sock'))
                except FileNotFoundError: pass
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                try:
                    conn.request('GET', '/api/status')
                    return json.loads(conn.getresponse().read())
                except OSError: return None
                finally: conn.close()
            try:
                deadline = time.monotonic() + 5
                found = 0
                while time.monotonic() < deadline:
                    state = sample()
                    if state and state['fault'] and 'Permission denied' in state['fault']:
                        self.assertFalse(state['allowed']); found += 1
                        if found == 10: break
                    time.sleep(.04)
                self.assertEqual(found, 10)
                self.assertIsNone(process.poll())
                (root / 'frames.sock').chmod(0o660)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    state = sample()
                    if state and state['allowed']: break
                    time.sleep(.04)
                self.assertTrue(state['allowed'])
                self.assertIsNone(state['fault'])
            finally:
                process.terminate()
                _, errors = process.communicate(timeout=5)
                frames.close()
            self.assertEqual(process.returncode, 0, errors.decode())
