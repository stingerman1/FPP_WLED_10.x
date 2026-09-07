"""Native WLED commands execute independently per device, away from FPP/rendering."""
from concurrent.futures import ThreadPoolExecutor, wait
from copy import deepcopy
import json
import socket
import threading
from urllib.request import Request, build_opener, ProxyHandler
from .storage import read_json, save_json
from .udp import encode


class Devices:
    def __init__(self, config, ownership, state_lock, directory):
        self.config = {d['id']: d for d in config.get('devices', [])}
        self.ownership, self.state_lock = ownership, state_lock
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix='wled-device')
        self.locks = {key: threading.Lock() for key in self.config}
        self.status = {}
        self.futures = set()
        self.mutex = threading.Lock()
        self.opener = build_opener(ProxyHandler({}))
        self.path = directory / 'native-state.json'
        self.desired = read_json(self.path, {})
        if not isinstance(self.desired, dict):
            raise ValueError('native-state.json must be an object')

    def request(self, address, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        request = Request('http://' + address + path, data=body,
                          headers={'Content-Type': 'application/json'})
        with self.opener.open(request, timeout=0.5) as response:
            data = response.read(262145)
            if len(data) > 262144:
                raise ValueError('device response too large')
            return json.loads(data)

    def targets(self, target):
        if not isinstance(target, str):
            raise ValueError('target must be a device id or group:name')
        if target in self.config:
            return [self.config[target]]
        if target.startswith('group:'):
            devices = [d for d in self.config.values() if target[6:] in d.get('groups', [])]
            if devices:
                return devices
        raise ValueError('unknown device or group')

    def command(self, target, payload, persist=True):
        if not isinstance(payload, dict) or not payload or set(payload) - {'ps', 'on', 'bri', 'transition', 'seg'}:
            raise ValueError('native command permits only ps, on, bri, transition and seg')
        # Realtime override, device configuration and network ownership changes are prohibited.
        if 'seg' in payload:
            segments = payload['seg'] if isinstance(payload['seg'], list) else [payload['seg']]
            if any(not isinstance(s, dict) or set(s) - {'id', 'fx', 'sx', 'ix', 'pal', 'col', 'bri', 'on'} for s in segments):
                raise ValueError('unsupported native segment fields')
        targets = self.targets(target)
        for device in targets:
            if device['mode'] == 'fpp-stream':
                raise ValueError(device['id'] + ' receives FPP-rendered pixels; effect commands are disabled')
            if device['mode'] == 'sync' and 'ps' in payload:
                raise ValueError('preset commands require effect mode; UDP sync has no preset-ID command')
        if not self.ownership.status()['allowed']:
            raise PermissionError('ambient control is suspended')
        with self.mutex:
            self.futures = {future for future in self.futures if not future.done()}
            if len(self.futures) + len(targets) > 64:
                raise ValueError('native command queue is full')
            if persist:
                desired = deepcopy(self.desired)
                for device in targets:
                    desired[device['id']] = deepcopy(payload)
                save_json(self.path, desired)
                self.desired = desired
            for device in targets:
                self.futures.add(self.executor.submit(self._send, device, deepcopy(payload), self.ownership.epoch))
        return {'accepted': [d['id'] for d in targets]}

    def _send(self, device, payload, epoch):
        key = device['id']
        try:
            with self.locks[key]:
                info = self.request(device['address'], '/json/info')
                if info.get('live'):
                    raise PermissionError('device is receiving realtime data')
                with self.state_lock:
                    status = self.ownership.status()
                    if not status['allowed'] or status['epoch'] != epoch:
                        raise PermissionError('show takeover or ambient state changed')
                # Explicit Show Start waits for requests already dispatched here.
                # Automatic detection cannot recall an IP packet already in flight.
                if device['mode'] == 'sync':
                    self._sync(device, payload)
                else:
                    self.request(device['address'], '/json/state', payload)
                result = {'reachable': True, 'last_command': 'sent', 'version': info.get('ver')}
        except Exception as exc:
            result = {'last_command': 'blocked' if isinstance(exc, PermissionError) else 'failed', 'error': str(exc)}
        with self.mutex:
            self.status[key] = result

    def _sync(self, device, payload):
        if 'ps' in payload:
            raise ValueError('UDP notifier has no preset-ID command; use effect mode for preset commands')
        state = self.request(device['address'], '/json/state')
        for key in ('on', 'bri', 'transition'):
            if key in payload:
                state[key] = payload[key]
        if 'seg' in payload:
            updates = payload['seg'] if isinstance(payload['seg'], list) else [payload['seg']]
            for index, update in enumerate(updates):
                state['seg'][update.get('id', index)].update(update)
        packet = encode(state, device.get('sync_groups', 1))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(packet, (device['address'], device.get('sync_port', 21324)))

    def resume(self):
        for key, payload in list(self.desired.items()):
            if key not in self.config or self.config[key]['mode'] == 'fpp-stream':
                continue
            try:
                self.command(key, payload, persist=False)
            except (ValueError, PermissionError):
                pass

    def drain(self):
        with self.mutex:
            futures = list(self.futures)
        _, pending = wait(futures, timeout=3)
        if pending:
            raise TimeoutError('native requests still pending; do not start direct-to-device playback yet')

    def public(self):
        with self.mutex:
            return [{'id': key, 'address': d['address'], 'mode': d['mode'],
                     'groups': d.get('groups', []), **self.status.get(key, {'last_command': 'not probed'})}
                    for key, d in self.config.items()]

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
