"""WLED notifier v12 (udp.cpp at the locked commit), no realtime-input protocols."""
import socket
import struct


def encode(state, groups=1, elapsed_ms=0):
    segments = state['seg']
    if not 1 <= len(segments) <= 32:
        raise ValueError('UDP synchronization supports 1..32 segments')
    packet = bytearray(41 + len(segments) * 36)
    main = segments[min(state.get('mainseg', 0), len(segments) - 1)]
    colors = main['col'] + [[0, 0, 0, 0]] * (3 - len(main['col']))
    colors = [c + [0] * (4 - len(c)) for c in colors]
    packet[0:3] = bytes([0, 1, state['bri'] if state['on'] else 0])
    packet[3:6] = bytes(colors[0][:3])
    packet[8:12] = bytes([main['fx'], main['sx'], colors[0][3], 12])
    packet[12:16] = bytes(colors[1])
    packet[16] = main['ix']
    struct.pack_into('<H', packet, 17, min(state.get('transition', 7) * 100, 65535))
    packet[19] = main['pal']
    packet[20:24] = bytes(colors[2])
    struct.pack_into('!I', packet, 25, elapsed_ms & 0xffffffff)
    packet[36:41] = bytes([groups, 255, 127, len(segments), 36])
    for index, seg in enumerate(segments):
        offset = 41 + index * 36
        packet[offset] = index
        struct.pack_into('!HHBBH', packet, offset + 1, seg['start'], seg['stop'],
                         seg.get('grp', 1), seg.get('spc', 0), seg.get('of', 0))
        flags = int(seg.get('sel', True)) | int(seg.get('rev', False)) << 1 | int(seg.get('on', True)) << 2 | int(seg.get('mi', False)) << 3 | int(seg.get('rY', False)) << 6
        packet[offset + 9:offset + 15] = bytes([flags, seg.get('bri', 255), seg['fx'], seg['sx'], seg['ix'], seg['pal']])
        colors = seg['col'] + [[0, 0, 0, 0]] * (3 - len(seg['col']))
        packet[offset + 15:offset + 27] = bytes(v for c in colors for v in c + [0] * (4 - len(c)))
        packet[offset + 27:offset + 32] = bytes([127, int(seg.get('mY', False)) | int(seg.get('tp', False)) << 1 | seg.get('m12', 0) << 2,
                                               seg.get('c1', 128), seg.get('c2', 128), seg.get('c3', 16) | int(seg.get('o1', False)) << 5 | int(seg.get('o2', False)) << 6 | int(seg.get('o3', False)) << 7])
        struct.pack_into('!HH', packet, offset + 32, seg.get('startY', 0), seg.get('stopY', 1))
    return bytes(packet)


def decode(packet, groups=1):
    if len(packet) < 41 or packet[0] != 0 or packet[11] != 12 or not packet[36] & groups:
        raise ValueError('not an accepted WLED v12 synchronization packet')
    count, stride = packet[39:41]
    if not 1 <= count <= 32 or stride != 36 or len(packet) < 41 + count * stride:
        raise ValueError('invalid WLED segment packet length')
    segments = []
    for index in range(count):
        offset = 41 + index * stride
        p = packet[offset:offset + stride]
        # Geometry stays local. A device's strip/matrix wiring need not match.
        segments.append({'id': p[0], 'bri': p[10], 'fx': p[11], 'sx': p[12], 'ix': p[13], 'pal': p[14],
                         'col': [list(p[15:19]), list(p[19:23]), list(p[23:27])],
                         'on': bool(p[9] & 4), 'rev': bool(p[9] & 2), 'mi': bool(p[9] & 8),
                         'c1': p[29], 'c2': p[30], 'c3': p[31] & 31,
                         'o1': bool(p[31] & 32), 'o2': bool(p[31] & 64), 'o3': bool(p[31] & 128)})
    return {'on': packet[2] != 0, 'bri': packet[2], 'transition': struct.unpack_from('<H', packet, 17)[0] // 100,
            'seg': segments}


class Sync:
    def __init__(self, controller):
        self.controller = controller
        self.config = controller.config['udp']
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(('0.0.0.0', self.config.get('port', 21324)))
            self.socket.setblocking(False)
        except Exception:
            self.socket.close()
            raise
        self.last_error = None
        self.received = 0
        self.sent = 0

    @property
    def peers(self):
        peers = set(self.config.get('peers', []))
        discovery = self.controller.integrations.get('discovery')
        if self.config.get('auto_peers', False) and discovery:
            peers.update(n['address'] for n in discovery.public() if not n['enrolled'])
        excluded = {d['address'] for d in self.controller.config.get('devices', [])}
        if discovery:
            excluded.update(a for a, _ in discovery.local)
        return peers - excluded

    def tick(self):
        for _ in range(16):
            try:
                packet, sender = self.socket.recvfrom(1473)
            except BlockingIOError:
                return
            except OSError as exc:
                self.last_error = str(exc)
                return
            if not self.config.get('receive', True) or sender[0] not in self.peers or len(packet) > 1472:
                continue
            try:
                patch = decode(packet, self.config.get('groups', 1))
                with self.controller.lock:
                    if not self.controller.ownership.status()['allowed']:
                        continue
                    local_ids = {s.get('id', i) for i, s in enumerate(self.controller.state.value['seg'])}
                    patch['seg'] = [s for s in patch['seg'] if s['id'] in local_ids]
                    # Received notifications must not generate a notification loop.
                    self.controller.state.set(patch)
                    self.controller.state.stop_playlist()
                    self.controller.render_ms = struct.unpack_from('!I', packet, 25)[0]
                    self.controller.dirty = True
                    self.received += 1
                    self.last_error = None
            except (ValueError, TypeError, KeyError) as exc:
                self.last_error = str(exc)
            except OSError as exc:
                self.last_error = str(exc)
                with self.controller.lock:
                    self.controller.ownership.fault = 'persistent storage unavailable'

    def send(self):
        if not self.config.get('send', True) or not self.controller.ownership.status()['allowed']:
            return
        packet = encode(self.controller.state.value, self.config.get('groups', 1), self.controller.render_ms)
        for peer in self.peers:
            try:
                self.socket.sendto(packet, (peer, self.config.get('port', 21324)))
                self.sent += 1
            except OSError as exc:
                self.last_error = str(exc)

    def close(self):
        self.socket.close()
