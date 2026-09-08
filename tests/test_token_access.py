import http.client
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = 'test-only-runtime-token-0123456789abcdef'


@unittest.skipUnless(shutil.which('php'), 'php-cli required')
class TokenAccessTests(unittest.TestCase):
    def test_explicit_retrieval_only_and_missing_token(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            auth = path / 'auth.json'
            auth.write_text(json.dumps({'token': TOKEN}))
            source = (ROOT / 'runtime-token.php').read_text().replace(
                '/home/fpp/media/config/plugin.FPP_WLED_10.x/auth.json', str(auth))
            (path / 'token.php').write_text(source)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            process = subprocess.Popen(['php', '-S', f'127.0.0.1:{port}', '-t', str(path)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            def request(method, headers=None, query='?nopage=1'):
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                conn.request(method, '/token.php' + query, headers=headers or {})
                response = conn.getresponse()
                result = response.status, dict(response.getheaders()), json.loads(response.read())
                conn.close()
                return result
            try:
                for _ in range(100):
                    try:
                        status, _, body = request('GET')
                        break
                    except OSError:
                        time.sleep(.02)
                else:
                    self.fail('PHP fixture failed to start')
                self.assertEqual(status, 405)
                self.assertNotIn('token', body)
                self.assertEqual(request('POST')[0], 403)
                headers = {'X-FPP-WLED-Action': 'retrieve-token'}
                self.assertEqual(request('POST', headers, '')[0], 403)
                self.assertEqual(request('POST', {**headers, 'Sec-Fetch-Site': 'cross-site'})[0], 403)
                status, response_headers, body = request('POST', headers)
                self.assertEqual(status, 200)
                self.assertEqual(response_headers['Cache-Control'], 'no-store')
                self.assertNotIn('Access-Control-Allow-Origin', response_headers)
                self.assertEqual(body['token'], TOKEN)
                self.assertEqual(json.loads(auth.read_text())['token'], TOKEN)
                auth.unlink()
                self.assertEqual(request('POST', headers)[0], 503)
                self.assertFalse(auth.exists())
            finally:
                process.terminate()
                process.wait(timeout=5)
