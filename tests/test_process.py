"""Real daemon + Unix IPC + HTTP; the FPP observer is a protocol simulator."""
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from runtime.ipc import FRAME, OBSERVER
from runtime.service import ROOT


class ProcessTest(unittest.TestCase):
    def test_daemon_handoff_staleness_and_restart(self):
        with tempfile.TemporaryDirectory(prefix='wled-') as directory:
            state = Path(directory) / 'state'
            run = Path(directory) / 'run'
            state.mkdir(); run.mkdir()
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            listener.bind(str(run / 'frames.sock'))
            listener.settimeout(0.01)
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1', 0))
                port = reserve.getsockname()[1]
            config = {'version': 1, 'bind': '127.0.0.1', 'port': port,
                      'pixels': {'count': 12, 'channels': 3},
                      'mappings': [{'pixel': 0, 'channel': 1, 'count': 12}], 'devices': []}
            (state / 'config.json').write_text(json.dumps(config))
            flags, observed, stop, ack, allowed = [0], [True], threading.Event(), [0], [False]
            frames = []
            def observer():
                while not stop.is_set():
                    try:
                        packet = listener.recv(70000)
                        header = FRAME.unpack_from(packet)
                        ack[0], allowed[0] = header[3], bool(header[2])
                        frames.append((time.monotonic(), allowed[0]))
                    except socket.timeout:
                        pass
                    if observed[0]:
                        packet = OBSERVER.pack(b'FPO1', 1, flags[0] | (16 if allowed[0] else 0), time.monotonic_ns(), 42, ack[0])
                        try:
                            listener.sendto(packet, str(run / 'observer.sock'))
                        except (FileNotFoundError, ConnectionRefusedError):
                            pass
            thread = threading.Thread(target=observer)
            thread.start()
            log = (Path(directory) / 'daemon.log').open('w+')
            process = subprocess.Popen([sys.executable, '-m', 'runtime.service', '--state-dir', str(state),
                                        '--run-dir', str(run)], cwd=ROOT, stdout=log, stderr=log)
            def request(path, body=None):
                token = json.loads((state / 'auth.json').read_text())['token']
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                conn.request('POST' if body is not None else 'GET', path,
                             json.dumps(body) if body is not None else None,
                             {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
                response = conn.getresponse()
                data = json.loads(response.read())
                conn.close()
                return response.status, data
            def until(predicate, timeout=5):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        log.seek(0)
                        self.fail('runtime exited: ' + log.read())
                    try:
                        if predicate():
                            return
                    except (OSError, ValueError):
                        pass
                    time.sleep(0.025)
                self.fail('condition did not become true')
            try:
                until(lambda: request('/api/status')[1]['observer_healthy'])
                self.assertEqual(request('/api/command', {'operation': 'ambient-enable'})[0], 200)
                until(lambda: frames and frames[-1][1])
                self.assertEqual(request('/api/command', {'operation': 'show-start', 'source': 'xschedule:main'})[0], 200)
                self.assertFalse(frames[-1][1])
                self.assertEqual(request('/json/state', {'bri': 1})[0], 409)
                self.assertEqual(request('/json/state', {'psave': 1, 'n': 'Night', 'bri': 20})[0], 200)
                live = request('/json/state')[1]
                imported = {'presets': {'2': {'n': 'Imported', 'bs': 0, 'bri': 42}}}
                code, preview = request('/api/presets/import', imported)
                self.assertEqual(code, 200)
                self.assertTrue(preview['valid'])
                self.assertNotIn('2', request('/presets.json')[1])
                imported.update(preview=False, revision=preview['revision'])
                self.assertTrue(request('/api/presets/import', imported)[1]['saved'])
                self.assertEqual(request('/presets.json')[1]['2']['bri'], 42)
                self.assertEqual(request('/json/state')[1], live)
                self.assertFalse(frames[-1][1])
                self.assertEqual(request('/api/presets/import', imported)[0], 422)
                request('/api/command', {'operation': 'show-end', 'source': 'xschedule:main'})
                until(lambda: frames[-1][1])
                observed[0] = False
                until(lambda: not request('/api/status')[1]['observer_healthy'])
                until(lambda: not frames[-1][1])
                request('/api/command', {'operation': 'show-start', 'source': 'persisted'})
            finally:
                process.terminate()
                process.wait(timeout=10)
                stop.set(); thread.join(timeout=2); listener.close(); log.close()
            persisted = json.loads((state / 'ownership.json').read_text())
            self.assertEqual(persisted['locks'], ['persisted'])
            self.assertTrue(persisted['enabled'])
