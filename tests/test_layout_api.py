import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from runtime import layout


class LayoutAPITests(unittest.TestCase):
    def setUp(self):
        self.responses = {'/api/models': (200, []), '/api/channel/output/co-pixelStrings':
                          (404, {'status': 'ERROR: File not found'})}
        responses = self.responses
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, body = responses[self.path]
                self.send_response(status)
                self.end_headers()
                self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def read(self):
        return layout.sources(self.server.server_port)

    def test_empty_and_named_models_and_strings(self):
        self.assertEqual(self.read()['items'], [])
        self.responses['/api/models'] = (200, [{'Type': 'Channel', 'Name': 'Matrix'}])
        self.responses['/api/channel/output/co-pixelStrings'] = (200, {'status': 'OK', 'channelOutputs': [
            {'enabled': 1, 'outputs': [{'portNumber': 0, 'virtualStrings': [{'pixelCount': 10, 'description': 'Porch'}]}]}]})
        result = self.read()
        self.assertEqual([i['name'] for i in result['items']], ['Matrix', 'Porch'])
        self.assertEqual(result['revision'], self.read()['revision'])

    def test_errors_are_not_empty_layouts(self):
        for response in [(500, {}), (404, {}), (200, b'not json'), (200, {}), (200, b' ' * (2*1024*1024+1))]:
            self.responses['/api/models'] = response
            with self.subTest(response=str(response)[:40]), self.assertRaises(ValueError): self.read()

    def test_malformed_nested_strings(self):
        for ports in [None, ['bad'], [{'virtualStrings': [None]}], [{'virtualStrings': [{'pixelCount': 'oops'}]}]]:
            self.responses['/api/channel/output/co-pixelStrings'] = (200, {'channelOutputs': [{'enabled': 1, 'outputs': ports}]})
            with self.subTest(ports=ports), self.assertRaises(ValueError): self.read()
