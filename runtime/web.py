"""Bounded HTTP/WebSocket API plus a filesystem-protected local command socket."""
import base64
import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import mimetypes
import secrets
import socket
import socketserver
import struct
import threading
import time
from urllib.parse import urlsplit
from .storage import read_json, save_json

MAX_BODY = 262144
LOGIN_MAX_AGE = 365 * 24 * 60 * 60
ASSETS = {'index.htm', 'index.js', 'index.css', 'common.js', 'iro.js', 'rangetouch.js', 'favicon.ico', 'icon.png'}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, fmt, *args):
        # Request URLs may contain user data; omit HTTP access logs.
        pass

    def authenticated(self):
        if self.server.local:
            return True
        supplied = self.headers.get('Authorization', '').removeprefix('Bearer ')
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            if not supplied and 'fpp_wled' in cookie:
                supplied = cookie['fpp_wled'].value
        except Exception:
            return False
        return bool(supplied) and hmac.compare_digest(supplied, self.server.token)

    def login_cookie(self, proxied, clear=False):
        return ('fpp_wled=' + ('' if clear else self.server.token)
                + '; HttpOnly; SameSite=Strict; Path=' + ('/fpp-wled/' if proxied else '/')
                + '; Max-Age=' + str(0 if clear else LOGIN_MAX_AGE))

    def reply(self, code, body, content_type='application/json', headers=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for key, value in (headers or {}).items():
            for item in value if isinstance(value, list) else [value]:
                self.send_header(key, item)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        if self.headers.get('Transfer-Encoding'):
            raise ValueError('chunked requests are not supported')
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= MAX_BODY:
            raise ValueError('body must be 1..262144 bytes')
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError('truncated body')
        return json.loads(body)

    def do_POST(self):
        proxied = self.path.startswith('/fpp-wled/')
        if proxied:
            self.path = self.path[len('/fpp-wled'):]
        try:
            if urlsplit(self.path).path == '/api/logout':
                self.body()
                return self.reply(200, {'authenticated': False}, headers={
                    'Set-Cookie': [self.login_cookie(proxied, clear=True), self.login_cookie(False, clear=True)]
                    if proxied else self.login_cookie(False, clear=True)})
            if not self.authenticated():
                self.close_connection = True
                return self.reply(401, {'error': 'bearer token required'})
            path = urlsplit(self.path).path
            payload = self.body()
            if path == '/api/login':
                return self.reply(200, {'success': True}, headers={
                    'Set-Cookie': self.login_cookie(proxied)})
            self.reply(200, self.server.controller.post(path, payload))
        except PermissionError as exc:
            self.reply(409, {'error': str(exc), 'status': self.server.controller.ownership.status()})
        except (ValueError, TypeError, AttributeError) as exc:
            self.reply(422, {'error': str(exc)})
        except KeyError as exc:
            self.reply(404, {'error': 'unknown resource or missing field: ' + str(exc)})
        except TimeoutError as exc:
            self.reply(503, {'error': str(exc)})
        except OSError as exc:
            with self.server.controller.lock:
                self.server.controller.ownership.fault = 'persistent storage unavailable'
            self.reply(503, {'error': str(exc)})

    def do_GET(self):
        proxied = self.path.startswith('/fpp-wled/')
        if proxied:
            self.path = self.path[len('/fpp-wled'):]
        path = urlsplit(self.path).path
        try:
            destinations = {'/liveview':'ambient-lighting','/settings/led':'configuration',
                            '/settings/sync':'network','/settings/time':'schedules',
                            '/settings/ui':'runtime-access','/settings/sec':'runtime-access'}
            if path in destinations:
                destination = '/plugin.php?plugin=FPP_WLED_10.x&page=settings.php' if proxied else '/settings'
                return self.reply(302, {'location':destination}, headers={'Location':destination+'#'+destinations[path]})
            if path == '/api/auth':
                authenticated = self.authenticated()
                return self.reply(200, {'authenticated': authenticated, 'persistent': authenticated,
                                       'remember_days': LOGIN_MAX_AGE // 86400}, headers={
                    'Set-Cookie': self.login_cookie(proxied)} if authenticated else None)
            if path == '/ws':
                return self.websocket()
            if path == '/skin.css':
                return self.reply(200, b'/* Linux alpha uses upstream default skin. */', 'text/css')
            if path.startswith('/json') or path.startswith('/api') or path == '/presets.json' or (path.startswith('/palette') and path.endswith('.json')):
                return self.reply(200, self.server.controller.get(self.path if path == '/json/palx' else path))
            asset = 'index.htm' if path == '/' else path.lstrip('/')
            if asset in ASSETS:
                data = (self.server.assets / asset).read_bytes()
                if asset == 'index.htm':
                    data = data.replace(b'</body>', b'<link rel="stylesheet" href="wled-theme.css"><script src="theme.js"></script><script src="base.js"></script><script src="linux-ui.js"></script></body>')
                return self.reply(200, data, mimetypes.guess_type(asset)[0] or 'application/octet-stream')
            if path in ('/settings', '/login', '/config-editor.js', '/linux-ui.js', '/schedules.js', '/base.js', '/summary.js', '/access.js', '/network.js', '/device-controls.js', '/settings.css', '/theme.js', '/wled-theme.css'):
                from .service import ROOT
                filename = path[1:] if path.endswith(('.js', '.css')) else 'settings.html'
                return self.reply(200, (ROOT / 'web' / filename).read_bytes(),
                                  'text/javascript' if filename.endswith('.js') else 'text/css' if filename.endswith('.css') else 'text/html; charset=utf-8')
            self.reply(404, {'error': 'unsupported endpoint', 'compatibility': '/api/status'})
        except (KeyError, FileNotFoundError):
            self.reply(404, {'error': 'resource not available'})
        except (ValueError, TypeError):
            self.reply(422, {'error': 'invalid resource parameters'})

    def websocket(self):
        key = self.headers.get('Sec-WebSocket-Key', '')
        try:
            if len(base64.b64decode(key, validate=True)) != 16:
                raise ValueError()
        except Exception:
            return self.reply(400, {'error': 'invalid WebSocket key'})
        if self.headers.get('Sec-WebSocket-Version') != '13':
            return self.reply(400, {'error': 'WebSocket version 13 required'})
        self.send_response(101)
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', base64.b64encode(hashlib.sha1(
            (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode())
        self.end_headers()
        self.connection.settimeout(0.5)
        self.close_connection = True

        def send(value, opcode=1):
            payload = json.dumps(value).encode() if opcode == 1 else value
            size = len(payload)
            header = bytes([0x80 | opcode, size]) if size < 126 else bytes([0x80 | opcode, 126]) + struct.pack('!H', size)
            self.connection.sendall(header + payload)

        # Raw reads with a retained buffer handle fragmented TCP delivery. WebSocket
        # continuation frames are rejected explicitly (1003), not misparsed as JSON.
        pending = bytearray()
        last = None
        try:
            while not self.server.stop_event.is_set():
                value = self.server.controller.get('/json/si')
                fingerprint = json.dumps(value)
                if fingerprint != last:
                    send(value)
                    last = fingerprint
                try:
                    data = self.connection.recv(65536)
                    if not data:
                        break
                    pending.extend(data)
                except socket.timeout:
                    continue
                while len(pending) >= 2:
                    first, second = pending[:2]
                    opcode, size, offset = first & 15, second & 127, 2
                    if first & 0x70 or not first & 0x80 or not second & 0x80 or opcode not in (1, 8, 9, 10):
                        send(struct.pack('!H', 1003), 8)
                        return
                    if size == 126:
                        if len(pending) < 4:
                            break
                        size, offset = struct.unpack('!H', pending[2:4])[0], 4
                    elif size == 127:
                        send(struct.pack('!H', 1009), 8)
                        return
                    if opcode >= 8 and size > 125:
                        return
                    if len(pending) < offset + 4 + size:
                        break
                    mask = pending[offset:offset + 4]
                    body = bytes(v ^ mask[i % 4] for i, v in enumerate(pending[offset + 4:offset + 4 + size]))
                    del pending[:offset + 4 + size]
                    if opcode == 8:
                        send(b'', 8)
                        return
                    if opcode == 9:
                        send(body, 10)
                    elif opcode == 1:
                        try:
                            payload = json.loads(body)
                            if payload not in ({'v': True}, {}):
                                if not self.authenticated():
                                    send({'error': 1, 'message': 'Login through Linux setup to change ambient lighting'})
                                    continue
                                self.server.controller.post('/json/state', payload)
                        except (ValueError, PermissionError, KeyError) as exc:
                            send({'error': 409 if isinstance(exc, PermissionError) else 422, 'message': str(exc)})
        except (OSError, ValueError):
            pass


class BoundedThreads:
    daemon_threads = True
    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class HTTPServer(BoundedThreads, ThreadingHTTPServer):
    pass


class UnixServer(BoundedThreads, socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    pass


def start_servers(controller, run_dir, state_dir):
    from .service import ROOT
    auth = read_json(state_dir / 'auth.json', None)
    if auth is None:
        auth = {'token': secrets.token_urlsafe(32)}
        save_json(state_dir / 'auth.json', auth)
    if not isinstance(auth, dict) or not isinstance(auth.get('token'), str) or len(auth['token']) < 32:
        raise ValueError('invalid auth.json')
    local_path = run_dir / 'control.sock'
    local_path.unlink(missing_ok=True)
    http = HTTPServer((controller.config.get('bind', '127.0.0.1'), controller.config.get('port', 8787)), Handler)
    local = UnixServer(str(local_path), Handler)
    web_path = run_dir / 'web.sock'
    web_path.unlink(missing_ok=True)
    web = UnixServer(str(web_path), Handler)
    for server, is_local in ((http, False), (local, True), (web, False)):
        server.controller, server.local, server.token = controller, is_local, auth['token']
        server.assets = ROOT / 'build/ui'
        server.slots = threading.BoundedSemaphore(16)
        server.stop_event = threading.Event()
        threading.Thread(target=server.serve_forever, daemon=True).start()
    return http, local, web
