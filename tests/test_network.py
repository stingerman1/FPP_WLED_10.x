from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from runtime.discovery import Discovery, announcement
from runtime.network import Network
from runtime.config import validate
from runtime.state import default_segment
from runtime.udp import Sync, encode


class DiscoverySyncTests(unittest.TestCase):
    def test_udp_listener_requires_explicit_opt_in_and_can_be_closed(self):
        from unittest.mock import MagicMock
        config = {'version': 1, 'pixels': {'count': 100, 'channels': 3},
                  'mappings': [], 'discovery': True, 'discoverable': False}
        with tempfile.TemporaryDirectory() as directory, \
             patch('runtime.discovery.interfaces', return_value=[]), \
             patch('runtime.discovery.socket.socket') as socket_factory, \
             patch('zeroconf.Zeroconf', return_value=MagicMock()), \
             patch('zeroconf.ServiceBrowser'):
            controller = SimpleNamespace(config=config, directory=Path(directory),
                                         lock=threading.RLock(), integrations={})
            network = Network(controller)
            status = network.configure()
            self.assertTrue(status['discovery_active'])
            self.assertFalse(status['udp_discovery_active'])
            socket_factory.assert_not_called()
            controller.integrations['discovery'].tick()
            with self.assertRaises(ValueError): network.configure({'udp_discovery': 'yes'})
            status = network.configure({'udp_discovery': True})
            self.assertTrue(status['udp_discovery_active'])
            socket_factory.return_value.bind.assert_called_once_with(('0.0.0.0', 65506))
            status = network.configure({'udp_discovery': False})
            socket_factory.return_value.close.assert_called_once()
            self.assertFalse(status['udp_discovery_active'])
            self.assertTrue(status['discovery_active'])
            self.assertFalse(json.loads((Path(directory) / 'config.json').read_text())['udp_discovery'])
            network.configure()  # Saved opt-out survives reconfiguration.
            self.assertEqual(socket_factory.call_count, 1)
            network.configure({'discovery': False})

    def discovery(self):
        discovery = Discovery.__new__(Discovery)
        discovery.local = [('192.0.2.1', '192.0.2.255')]
        discovery.found = {}
        discovery.lock = threading.Lock()
        discovery.controller = SimpleNamespace(config={'devices': []})
        return discovery

    def test_native_announcement_roundtrip_self_spoof_expiry_and_mdns_path(self):
        discovery = self.discovery()
        packet = announcement('192.0.2.2', 'Porch', True)
        self.assertEqual(len(packet), 44)
        self.assertEqual(packet[:6], b'\xff\x01\xc0\x00\x02\x02')
        self.assertEqual(packet[38:40], b'\xff\x02')
        self.assertEqual(announcement('192.0.2.2', 'Porch', False)[38], 127)
        discovery.receive(packet, '192.0.2.3')
        discovery.receive(announcement('192.0.2.1', 'Self'), '192.0.2.1')
        for size in range(44):
            discovery.receive(packet[:size], '192.0.2.2')
        self.assertEqual(discovery.public(), [])
        discovery.receive(packet, '192.0.2.2')
        self.assertEqual(discovery.public()[0]['name'], 'Porch')
        info = SimpleNamespace(parsed_addresses=lambda: ['192.0.2.2'], port=8080,
                               properties={b'path': b'/fpp-wled/', b'product': b'FPP'})
        discovery.add_service(SimpleNamespace(get_service_info=lambda *a, **k: info), '_wled._tcp.local.', 'Porch._wled._tcp.local.')
        self.assertEqual(len(discovery.public()), 1)
        self.assertEqual(discovery.public()[0]['url'], 'http://192.0.2.2:8080/fpp-wled/')
        self.assertEqual(discovery.public()[0]['device_type'], 'FPP')
        discovery.remove_service(None, '', 'Porch._wled._tcp.local.')
        with patch('runtime.discovery.time.monotonic', return_value=time.monotonic() + 181):
            self.assertEqual(discovery.public(), [])

    def test_mdns_rejects_loopback_and_non_peer_addresses(self):
        discovery = self.discovery()
        info = SimpleNamespace(parsed_addresses=lambda: ['127.0.0.1', '0.0.0.0', '224.0.0.1', '::1', '192.0.2.1'], port=80, properties={})
        discovery.add_service(SimpleNamespace(get_service_info=lambda *a, **k: info), '_wled._tcp.local.', 'Self._wled._tcp.local.')
        self.assertEqual(discovery.public(), [])

    def test_bidirectional_wire_sync_filters_groups_show_and_control_modes(self):
        state = {'on': True, 'bri': 64, 'transition': 7, 'seg': [default_segment(100, 1)]}
        changes = []
        allowed = [True]
        discovery = self.discovery()
        discovery.record('test', {'name': 'Peer', 'address': '127.0.0.1', 'port': 80,
            'path': '/', 'type': 0, 'vid': 0, 'method': 'mdns'})
        controller = SimpleNamespace(config={'udp': {'enabled': True, 'port': 0, 'groups': 2, 'auto_peers': True}},
            integrations={'discovery': discovery}, lock=threading.RLock(), render_ms=0,
            ownership=SimpleNamespace(status=lambda: {'allowed': allowed[0]}),
            state=SimpleNamespace(value=state, set=changes.append, stop_playlist=lambda: None))
        sync = Sync(controller)
        self.addCleanup(sync.close)
        peer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        peer.bind(('127.0.0.1', 0)); peer.settimeout(0.1)
        self.addCleanup(peer.close)
        sync.config['port'] = peer.getsockname()[1]
        self.assertEqual(sync.peers, {'127.0.0.1'})
        sync.send()
        packet, _ = peer.recvfrom(1472)
        self.assertEqual(packet, encode(state, 2))
        target = ('127.0.0.1', sync.socket.getsockname()[1])
        peer.sendto(packet, target); sync.tick()
        self.assertEqual(len(changes), 1)
        self.assertEqual(sync.received, 1)
        with self.assertRaises(socket.timeout): peer.recvfrom(1472)  # No echo loop.
        allowed[0] = False
        peer.sendto(packet, target); sync.tick(); sync.send()
        self.assertEqual(len(changes), 1)
        with self.assertRaises(socket.timeout): peer.recvfrom(1472)
        allowed[0] = True
        peer.sendto(encode(state, 1), target); sync.tick()
        self.assertEqual(len(changes), 1)
        self.assertIsNotNone(sync.last_error)
        sync.config['receive'] = False
        peer.sendto(packet, target); sync.tick()
        self.assertEqual(len(changes), 1)
        controller.config['devices'] = [{'address': '127.0.0.1', 'mode': 'fpp-stream'}]
        self.assertEqual(sync.peers, set())
        controller.config['devices'] = []
        sync.config['receive'] = True
        def failed_save(_):
            raise OSError('disk unavailable')
        controller.state.set = failed_save
        peer.sendto(packet, target); sync.tick()
        self.assertEqual(controller.ownership.fault, 'persistent storage unavailable')
        from unittest.mock import MagicMock
        actual = sync.socket
        try:
            sync.socket = MagicMock()
            sync.socket.recvfrom.side_effect = OSError('network down')
            sync.tick()
            self.assertIn('network down', sync.last_error)
        finally:
            sync.socket = actual

    def test_live_configuration_validation_persistence_and_listener_failure(self):
        config = {'version': 1, 'pixels': {'count': 100, 'channels': 3}, 'mappings': []}
        with tempfile.TemporaryDirectory() as directory:
            controller = SimpleNamespace(config=deepcopy(config), directory=Path(directory),
                lock=threading.RLock(), integrations={})
            network = Network(controller)
            with self.assertRaises(ValueError):
                network.configure({'udp': {'enabled': True, 'auto_peers': True}})
            self.assertFalse((Path(directory) / 'config.json').exists())
            with patch('runtime.network.Discovery', side_effect=OSError('port busy')):
                status = network.configure({'discovery': True, 'udp': {'enabled': False}})
            self.assertIn('port busy', status['error'])
            self.assertFalse(status['discovery_active'])
            self.assertTrue((Path(directory) / 'config.json').exists())
            self.assertIsNone(network.configure({'discovery': False})['error'])
            for udp in ({'enabled': True, 'port': 65506}, {'enabled': True, 'groups': 0}):
                with self.assertRaises(ValueError): validate({**config, 'discovery': True, 'udp_discovery': True, 'udp': udp})

    def test_mdns_advertisement_matches_fpp_origin_and_cleanup(self):
        from unittest.mock import MagicMock
        zc = MagicMock()
        sock = MagicMock()
        controller = SimpleNamespace(config={'discoverable': True, 'udp_discovery': True, 'discovery_http_port': 8080})
        with patch('runtime.discovery.interfaces', return_value=[('192.0.2.1', '192.0.2.255')]), \
             patch('runtime.discovery.socket.socket', return_value=sock), \
             patch('zeroconf.Zeroconf', return_value=zc), patch('zeroconf.ServiceBrowser') as browser:
            discovery = Discovery(controller)
            discovery.advertiser.join(2)
            zc.register_service.assert_called_once()
            service = zc.register_service.call_args.args[0]
            self.assertEqual(service.port, 8080)
            self.assertEqual(service.properties[b'path'], b'/fpp-wled/')
            self.assertEqual(service.properties[b'product'], b'FPP')
            self.assertEqual(service.properties[b'device_type'], b'FPP')
            self.assertEqual(service.properties[b'arch'], b'linux')
            self.assertEqual(service.parsed_addresses(), ['192.0.2.1'])
            discovery.close()
            browser.return_value.cancel.assert_called_once()
            zc.close.assert_called_once()
            sock.close.assert_called_once()
