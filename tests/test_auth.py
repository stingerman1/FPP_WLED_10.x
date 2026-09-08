import http.cookiejar
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
import urllib.request
from runtime.web import start_servers, LOGIN_MAX_AGE


class PersistentAccessTests(unittest.TestCase):
    def test_cookie_survives_browser_and_runtime_restart_and_logout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = SimpleNamespace(config={'bind': '127.0.0.1', 'port': 0})
            servers = start_servers(controller, root, root)
            def stop():
                for server in servers:
                    server.stop_event.set(); server.shutdown(); server.server_close()
            def request(client, route, body=None, headers=None):
                url = f'http://127.0.0.1:{servers[0].server_address[1]}/fpp-wled' + route
                req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers or {})
                with client.open(req, timeout=2) as response:
                    return json.load(response), response.headers
            jar = http.cookiejar.MozillaCookieJar(str(root / 'browser.cookies'))
            client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            try:
                self.assertFalse(request(client, '/api/auth')[0]['authenticated'])
                # A stale cookie must not override a newly supplied valid token.
                _, headers = request(client, '/api/login', {}, {
                    'Authorization': 'Bearer ' + servers[0].token, 'Cookie': 'fpp_wled=obsolete'})
                self.assertIn('Max-Age=' + str(LOGIN_MAX_AGE), headers['Set-Cookie'])
                self.assertTrue(all(not c.discard and c.expires > time.time() + 300 * 86400 for c in jar))
                jar.save()
                stop()
                servers = start_servers(controller, root, root)
                restored = http.cookiejar.MozillaCookieJar(str(root / 'browser.cookies'))
                restored.load()
                client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(restored))
                auth, headers = request(client, '/api/auth')
                self.assertTrue(auth['authenticated'] and auth['persistent'])
                self.assertNotIn('token', auth)
                self.assertIn('Max-Age=', headers['Set-Cookie'])
                # Old direct-port logins used a root cookie. Forget must clear both paths.
                legacy = next(iter(restored))
                import copy
                legacy = copy.copy(legacy)
                legacy.path = '/'
                restored.set_cookie(legacy)
                request(client, '/api/logout', {})
                self.assertFalse(request(client, '/api/auth')[0]['authenticated'])
                self.assertEqual(len(restored), 0)
            finally:
                stop()
