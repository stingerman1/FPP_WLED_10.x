"""Local development only: simulated FPP observer for browser verification."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.ipc import FRAME, OBSERVER
from runtime.service import ROOT


class FPPAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/models':
            data = [{'Type': 'Channel', 'Name': 'Porch', 'ChannelCount': 300, 'StartChannel': 1}]
        elif self.path == '/api/channel/output/co-pixelStrings':
            data = {'status': 'OK', 'channelOutputs': []}
        else:
            self.send_error(404)
            return
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass

with tempfile.TemporaryDirectory(prefix='wled-ui-') as directory:
    path = Path(directory)
    api = ThreadingHTTPServer(('127.0.0.1', 0), FPPAPI)
    threading.Thread(target=api.serve_forever, daemon=True).start()
    config = {'version': 1, 'bind': '127.0.0.1', 'port': 18787, 'discovery_http_port': api.server_port,
              'pixels': {'count': 1000, 'channels': 3},
              'mappings': [{'pixel': 0, 'count': 1000, 'channel': 1}], 'devices': []}
    if os.environ.get('WLED_TEST_MATRIX') == '1':
        config['port'] = 18788
        config['pixels'].update(width=40, height=25)
    (path / 'config.json').write_text(json.dumps(config))
    (path / 'ownership.json').write_text(json.dumps({'version': 1, 'enabled': True, 'locks': []}))
    (path / 'auth.json').write_text(json.dumps({'token': 'local-browser-test-token-not-for-deployment'}))
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    listener.bind(str(path / 'frames.sock'))
    listener.settimeout(0.02)
    process = subprocess.Popen([sys.executable, '-m', 'runtime.service', '--state-dir', str(path), '--run-dir', str(path)], cwd=ROOT)
    print(f"Simulated FPP UI fixture: http://localhost:{config['port']}", flush=True)
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
    except KeyboardInterrupt:
        pass
    finally:
        process.terminate()
        process.wait(timeout=10)
        listener.close()
        api.shutdown(); api.server_close()
