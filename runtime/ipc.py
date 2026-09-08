"""Version 1 local protocol. Integers are little-endian; clocks are CLOCK_MONOTONIC."""
import socket
import struct
import time
import secrets
from pathlib import Path

FRAME = struct.Struct('<4sHHQQQII')
RANGE = struct.Struct('<III')
OBSERVER = struct.Struct('<4sHHQQQ')
NAMES = {1: 'fpp:playlist', 2: 'fpp:sequence', 4: 'fpp:live', 8: 'fpp:uncertain'}


class Link:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'observer.sock'
        self.path.unlink(missing_ok=True)
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.socket.bind(str(self.path))
        self.socket.setblocking(False)
        self.nonce = 0
        self.serial = secrets.randbits(31) << 32
        self.acknowledged = 0
        self.ack_allowed = False
        self.last_observation = 0
        self.fault = None

    def poll(self, ownership):
        ownership.transport_fault = self.fault
        # Drain bounded work; timestamp on the sender prevents queued heartbeats
        # from manufacturing freshness after either process was suspended.
        for _ in range(64):
            try:
                packet = self.socket.recv(128)
            except BlockingIOError:
                break
            if len(packet) != OBSERVER.size:
                continue
            magic, version, flags, created, nonce, acknowledged = OBSERVER.unpack(packet)
            now = time.monotonic_ns()
            if magic != b'FPO1' or version != 1 or flags & ~31 or not 0 <= now - created <= 500_000_000:
                continue
            if created <= self.last_observation:
                continue
            if self.nonce != nonce:
                ownership.clear_since = None
                ownership.seen_ns = None
            self.nonce, self.last_observation = nonce, created
            self.acknowledged, self.ack_allowed = acknowledged, bool(flags & 16)
            ownership.observe([name for bit, name in NAMES.items() if flags & bit])
            ownership.seen_ns = created

    def send(self, data, config, allowed):
        self.serial += 1
        ranges = b''.join(RANGE.pack(m['channel'] - 1, m['pixel'] * config['pixels']['channels'],
                                    m['count'] * config['pixels']['channels']) for m in config['mappings'])
        packet = FRAME.pack(b'WLF1', 1, int(allowed), self.serial, time.monotonic_ns(), self.nonce,
                            len(config['mappings']), len(data)) + ranges + data
        try:
            self.socket.sendto(packet, str(self.directory / 'frames.sock'))
            self.fault = None
            return self.serial
        except OSError as exc:
            self.fault = 'FPP frame socket unavailable: ' + (exc.strerror or str(exc))
            return False

    def close(self):
        self.socket.close()
        self.path.unlink(missing_ok=True)
