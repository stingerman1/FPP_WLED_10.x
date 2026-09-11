"""Exercise the real Apache route, authenticated Unix socket and browser URLs."""
import http.client
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from types import SimpleNamespace

from runtime.web import start_servers

ROOT = Path(__file__).resolve().parents[1]


class WebProxyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('apache2'), 'apache2-bin required')
    def test_apache_http_assets_auth_and_websocket(self):
        with tempfile.TemporaryDirectory(prefix='wled-proxy-') as directory:
            path = Path(directory)
            controller = SimpleNamespace(config={'bind': '127.0.0.1', 'port': 0},
                                         get=lambda route: {'route': route},
                                         post=lambda route, body: {'route': route, 'body': body})
            servers = start_servers(controller, path, path)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            modules = ('mpm_event', 'authz_core', 'alias', 'proxy', 'proxy_http', 'proxy_wstunnel')
            config = f'ServerRoot "{path}"\nServerName localhost\nListen 127.0.0.1:{port}\n'
            config += f'PidFile "{path}/apache.pid"\nErrorLog "{path}/error.log"\n'
            config += ''.join(f'LoadModule {m}_module /usr/lib/apache2/modules/mod_{m}.so\n' for m in modules)
            config += (ROOT / 'apache/fpp-wled.conf').read_text().replace('/run/fpp-wled/web.sock', str(path / 'web.sock'))
            # FPP serves its own /wled/ UI from a virtual host. The plugin's
            # global Location must inherit without taking over that namespace.
            native = path / 'www/wled'
            native.mkdir(parents=True)
            (native / 'index.html').write_text('Native FPP WLED interface')
            config += f'<VirtualHost *:{port}>\nDocumentRoot "{path}/www"\n'
            config += f'<Directory "{path}/www">\nRequire all granted\n</Directory>\n</VirtualHost>\n'
            config_path = path / 'apache.conf'
            config_path.write_text(config)
            process = subprocess.Popen(['apache2', '-f', str(config_path), '-DFOREGROUND'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            def request(method, route, body=None, headers=None):
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                conn.request(method, route, json.dumps(body) if body is not None else None, headers or {})
                response = conn.getresponse()
                data = response.read() if response.status != 101 else b''
                result = response.status, dict(response.getheaders()), data
                conn.close()
                return result
            try:
                for _ in range(100):
                    try:
                        status, _, _ = request('GET', '/fpp-wled/api/status')
                        break
                    except OSError:
                        if process.poll() is not None:
                            self.fail(process.stderr.read().decode())
                        time.sleep(.02)
                else:
                    self.fail('Apache did not start')
                self.assertEqual(status, 200)
                status, _, body = request('GET', '/wled/index.html')
                self.assertEqual(status, 200)
                self.assertEqual(body, b'Native FPP WLED interface')
                self.assertEqual(request('GET', '/fpp-wled')[0], 302)
                for route in ('/', '/index.js', '/index.css', '/base.js', '/linux-ui.js', '/settings', '/schedules.js', '/virtual-layout.js', '/guided-tools.js', '/backup.js'):
                    self.assertEqual(request('GET', '/fpp-wled' + route)[0], 200, route)
                status, _, body = request('GET', '/fpp-wled/json/palx?page=2')
                self.assertEqual(json.loads(body)['route'], '/json/palx?page=2')
                self.assertEqual(request('POST', '/fpp-wled/json/state', {'on': True})[0], 401)
                status, headers, _ = request('POST', '/fpp-wled/api/login', {}, {'Authorization': 'Bearer ' + servers[2].token})
                self.assertEqual(status, 200)
                self.assertIn('Path=/fpp-wled/', headers['Set-Cookie'])
                status, _, body = request('POST', '/fpp-wled/json/state', {'on': True}, {'Cookie': headers['Set-Cookie'].split(';')[0]})
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)['body'], {'on': True})
                status, _, _ = request('GET', '/fpp-wled/ws', headers={
                    'Connection': 'Upgrade', 'Upgrade': 'websocket',
                    'Sec-WebSocket-Version': '13', 'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ=='})
                self.assertEqual(status, 101)
                self.assertFalse(servers[2].local)
            finally:
                process.terminate()
                process.communicate(timeout=5)
                for server in servers:
                    server.stop_event.set()
                    server.shutdown()
                    server.server_close()

    @unittest.skipUnless(shutil.which('node'), 'node required')
    def test_browser_urls_preserve_origin_and_direct_access(self):
        source = (ROOT / 'web/base.js').read_text()
        script = "const assert = require('node:assert/strict'); global.window = {}; window.parent = window; global.document = {getElementById: () => null, querySelector: () => null, addEventListener: () => {}};\n" + source + """
for (const origin of ['http://fpp:8080', 'https://fpp:8443']) {
  global.window = {location: new URL(origin + '/fpp-wled/settings'), fetch: (path) => new URL(path, origin).href};
  assert.equal(wledFetch('/json/si'), origin + '/fpp-wled/json/si');
  assert.equal(wledURL('/settings#ambient-lighting'), '/fpp-wled/settings#ambient-lighting');
}
global.window = {location: new URL('http://fpp:8787/settings')};
assert.equal(wledURL('/api/status'), '/api/status');
global.document.getElementById = () => ({});
assert.equal(wledURL('/api/status'), '/fpp-wled/api/status');
"""
        subprocess.run(['node', '-e', script], check=True)
