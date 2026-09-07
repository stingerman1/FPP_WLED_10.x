"""Exercise the real Paho client against a local MQTT 3.1.1 broker fixture."""
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from runtime.engine import Engine
from runtime.integrations import MQTT
from runtime.ownership import Ownership
from runtime.service import Controller, ROOT


def packet(sock):
    def read(size):
        data = b''
        while len(data) < size:
            piece = sock.recv(size - len(data))
            if not piece:
                raise EOFError()
            data += piece
        return data
    kind = read(1)[0]
    size, multiplier = 0, 1
    for _ in range(4):
        digit = read(1)[0]
        size += (digit & 127) * multiplier
        if not digit & 128:
            return kind, read(size)
        multiplier *= 128
    raise ValueError('invalid packet length')


def publish(sock, topic, payload, retained=False):
    topic = topic.encode()
    body = len(topic).to_bytes(2, 'big') + topic + json.dumps(payload).encode()
    remaining, length = len(body), bytearray()
    while True:
        digit, remaining = remaining % 128, remaining // 128
        length.append(digit | (128 if remaining else 0))
        if not remaining:
            break
    sock.sendall(bytes([0x31 if retained else 0x30]) + length + body)


@unittest.skipUnless(importlib.util.find_spec('paho'), 'optional Paho dependency not installed')
class MQTTWireTests(unittest.TestCase):
    def test_discovery_control_retained_rejection_and_show_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            listener = socket.socket()
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            listener.settimeout(3)
            self.addCleanup(listener.close)
            config = {'pixels': {'count': 12, 'channels': 3}, 'devices': [],
                      'mqtt': {'enabled': True, 'host': '127.0.0.1', 'port': listener.getsockname()[1]}}
            now = [0]
            gate = Ownership(Path(directory) / 'ownership.json', clock=lambda: now[0])
            gate.observe([])
            gate.command('ambient-enable')
            for i in range(23):
                now[0] = i * 100_000_000
                gate.observe([])
            controller = Controller(config, Path(directory), Engine(ROOT / 'build/libwled_linux.so', config), gate)
            self.addCleanup(controller.devices.close)
            client = MQTT(controller)
            self.addCleanup(client.close)
            peer, _ = listener.accept()
            peer.settimeout(3)
            self.addCleanup(peer.close)
            self.assertEqual(packet(peer)[0] >> 4, 1)  # CONNECT
            peer.sendall(b'\x20\x02\x00\x00')
            publications = {}
            for _ in range(5):
                kind, body = packet(peer)
                if kind >> 4 == 8:  # SUBSCRIBE
                    peer.sendall(b'\x90\x05' + body[:2] + b'\x00\x00\x00')
                elif kind >> 4 == 3:
                    length = int.from_bytes(body[:2], 'big')
                    publications[body[2:2 + length].decode()] = body[2 + length:]
                if 'homeassistant/light/fpp_wled/config' in publications:
                    break
            discovery = json.loads(publications['homeassistant/light/fpp_wled/config'])
            self.assertEqual(discovery['command_topic'], 'wled/fpp/ha/set')

            def command(payload, retained=False):
                publish(peer, 'wled/fpp/ha/set', payload, retained)
                deadline = time.monotonic() + .3
                while time.monotonic() < deadline:
                    client.tick()
                    time.sleep(.01)
            command({'brightness': 42})
            self.assertEqual(controller.state.value['bri'], 42)
            command({'brightness': 99}, retained=True)
            self.assertEqual(controller.state.value['bri'], 42)
            gate.command('show-start', 'mqtt-test')
            command({'brightness': 120})
            self.assertEqual(controller.state.value['bri'], 42)
