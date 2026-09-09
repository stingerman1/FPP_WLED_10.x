"""WLED's 44-byte node announcements plus mDNS browsing/advertising.

The node wire format has no HTTP port or path field. Advertise the FPP origin
through mDNS with a path TXT record; native Nodes links still open FPP's root.
"""
import ipaddress
import socket
import struct
import threading
import time
import uuid


def interfaces():
    """Return Linux IPv4 addresses and directed broadcasts, without DNS/network I/O."""
    import fcntl
    result = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for _, name in socket.if_nameindex():
            try:
                query = struct.pack('256s', name.encode()[:15])
                address = socket.inet_ntoa(fcntl.ioctl(sock, 0x8915, query)[20:24])
                broadcast = socket.inet_ntoa(fcntl.ioctl(sock, 0x8919, query)[20:24])
                if not ipaddress.ip_address(address).is_loopback and broadcast != '0.0.0.0':
                    result.append((address, broadcast))
            except OSError:
                continue
    return result


def announcement(address, name, on=False):
    data = bytearray(44)
    data[:2] = b'\xff\x01'
    data[2:6] = socket.inet_aton(address)
    name = name.encode('utf-8')[:32]
    data[6:6 + len(name)] = name
    data[38] = 128 if on else 0  # Undefined hardware type, never impersonate ESP.
    data[39] = data[5]
    struct.pack_into('<I', data, 40, 2609080)
    return bytes(data)


class Discovery:
    def __init__(self, controller):
        from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo, IPVersion
        self.controller = controller
        self.found = {}
        self.lock = threading.Lock()
        self.local = interfaces()
        self.last_send = 0
        self.last_interfaces = time.monotonic()
        self.last_error = None
        self.registered = False
        self.stopped = threading.Event()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.socket.bind(('0.0.0.0', 65506))
            self.socket.setblocking(False)
        except Exception:
            self.socket.close()
            raise
        self.zc = Zeroconf(ip_version=IPVersion.V4Only)
        self.browser = ServiceBrowser(self.zc, '_wled._tcp.local.', self)
        uid = f'{uuid.getnode():012x}'
        self.service = ServiceInfo('_wled._tcp.local.', f'FPP-WLED-{uid}._wled._tcp.local.',
            addresses=[socket.inet_aton(a) for a, _ in self.local],
            port=controller.config.get('discovery_http_port', 80),
            properties={'mac': uid, 'path': '/fpp-wled/', 'product': 'FPP-WLED'},
            server=f'fpp-wled-{uid}.local.')
        # mDNS probing is asynchronous so FPP observation does not stall.
        self.advertiser = threading.Thread(target=self.advertise, daemon=True)
        self.advertiser.start()

    def advertise(self):
        try:
            if self.local and not self.stopped.is_set() and self.controller.config.get('discoverable', True):
                self.service.addresses = [socket.inet_aton(a) for a, _ in self.local]
                if self.registered:
                    self.zc.update_service(self.service)
                else:
                    self.zc.register_service(self.service)
                    self.registered = True
                self.last_error = None
        except Exception as exc:
            self.last_error = 'mDNS advertisement: ' + str(exc)

    def record(self, key, node):
        with self.lock:
            if key in self.found or len(self.found) < 128:
                self.found[key] = {**node, '_seen': time.monotonic()}

    def add_service(self, zeroconf, service_type, name):
        info = zeroconf.get_service_info(service_type, name, timeout=500)
        if not info:
            return
        for address in info.parsed_addresses():
            ip = ipaddress.ip_address(address)
            if ip.version != 4 or ip.is_loopback or ip.is_multicast or ip.is_unspecified or address in {a for a, _ in self.local}:
                continue
            path = info.properties.get(b'path', b'/').decode('utf-8', 'replace')
            if path not in ('/', '/fpp-wled/'):
                path = '/'
            self.record('mdns:' + name + ':' + address, {'name': name.removesuffix('._wled._tcp.local.'),
                'address': address, 'port': info.port, 'path': path, 'type': 0, 'vid': 0, 'method': 'mdns'})

    def update_service(self, zeroconf, service_type, name):
        self.add_service(zeroconf, service_type, name)

    def remove_service(self, zeroconf, service_type, name):
        with self.lock:
            for key in list(self.found):
                if key.startswith('mdns:' + name + ':'):
                    del self.found[key]

    def receive(self, data, sender):
        if len(data) < 44 or data[:2] != b'\xff\x01':
            return
        address = socket.inet_ntoa(data[2:6])
        if address != sender or address in {a for a, _ in self.local}:
            return
        ip = ipaddress.ip_address(address)
        if ip.is_multicast or ip.is_unspecified or ip.is_loopback:
            return
        self.record('udp:' + address, {'name': data[6:38].split(b'\0')[0].decode('utf-8', 'replace'),
            'address': address, 'port': 80, 'path': '/', 'type': data[38],
            'vid': struct.unpack_from('<I', data, 40)[0], 'method': 'udp'})

    def tick(self):
        now = time.monotonic()
        if now - self.last_interfaces > 30:
            previous = self.local
            self.local = interfaces()
            self.last_interfaces = now
            if (self.local != previous or not self.registered) and not self.advertiser.is_alive():
                self.advertiser = threading.Thread(target=self.advertise, daemon=True)
                self.advertiser.start()
        for _ in range(32):
            try:
                data, sender = self.socket.recvfrom(512)
                self.receive(data, sender[0])
            except BlockingIOError:
                break
            except OSError as exc:
                self.last_error = str(exc)
                break
        if now - self.last_send >= 30 and self.controller.config.get('discoverable', True):
            self.last_send = now
            for address, broadcast in self.local:
                try:
                    self.socket.sendto(announcement(address, self.controller.config.get('name', 'WLED for FPP'),
                        self.controller.state.value['on']), (broadcast, 65506))
                except OSError as exc:
                    self.last_error = str(exc)

    def public(self):
        now = time.monotonic()
        with self.lock:
            self.found = {k: v for k, v in self.found.items() if v['method'] == 'mdns' or now - v['_seen'] < 180}
            nodes = {}
            # mDNS supplies the accurate HTTP port/path; UDP supplies live node data.
            for node in sorted(self.found.values(), key=lambda n: n['method'] == 'mdns'):
                nodes[node['address']] = dict(node)
        devices = {d['address']: d['mode'] for d in self.controller.config.get('devices', [])}
        for node in nodes.values():
            node.pop('_seen', None)
            node['addresses'] = [node['address']]
            node['enrolled'] = node['address'] in devices
            node['mode'] = devices.get(node['address'])
            node['url'] = f"http://{node['address']}:{node['port']}{node['path']}"
        return list(nodes.values())

    def close(self):
        self.stopped.set()
        self.socket.close()
        self.browser.cancel()
        self.advertiser.join(3)
        self.zc.close()
