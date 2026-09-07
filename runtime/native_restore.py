"""Native effect-mode checkpoints. All network work runs on device workers."""
from copy import deepcopy
from concurrent.futures import wait
import threading
import time

from .config import integer
from .storage import read_json, save_json


def snapshot(document, address):
    """Project the native API onto lighting-only fields; never replay device controls."""
    info, state = document['info'], document['state']
    if type(info.get('live')) is not bool or info['live']:
        raise PermissionError('device realtime state is active or unknown')
    mac = info.get('mac')
    if not isinstance(mac, str) or not mac or len(mac) > 64:
        raise ValueError('device identity unavailable')
    if type(state.get('on')) is not bool:
        raise ValueError('invalid native power state')
    payload = {'on': state['on'], 'bri': integer(state['bri'], 0, 255, 'brightness')}
    for key, maximum in [('transition', 655), ('bs', 31), ('mainseg', 255), ('ledmap', 255)]:
        if key in state:
            payload[key] = integer(state[key], 0, maximum, key)
    segments = state['seg']
    maximum = integer(info.get('leds', {}).get('maxseg', 32), 1, 256, 'maximum segments')
    if not isinstance(segments, list) or not 1 <= len(segments) <= maximum:
        raise ValueError('invalid native segments')
    saved, ids = [], set()
    bools = {'on', 'frz', 'sel', 'rev', 'mi', 'rY', 'mY', 'tp', 'o1', 'o2', 'o3'}
    ints = {'start', 'stop', 'startY', 'stopY', 'grp', 'spc', 'of', 'bri', 'cct', 'set',
            'fx', 'sx', 'ix', 'pal', 'c1', 'c2', 'c3', 'si', 'm12', 'bm'}
    for source in segments:
        sid = integer(source['id'], 0, maximum - 1, 'segment ID')
        if sid in ids:
            raise ValueError('duplicate native segment ID')
        ids.add(sid)
        segment = {'id': sid}
        for key in bools & source.keys():
            if type(source[key]) is not bool:
                raise ValueError('invalid native ' + key)
            segment[key] = source[key]
        for key in ints & source.keys():
            segment[key] = integer(source[key], 0, 65535 if key in {'start', 'stop', 'startY', 'stopY', 'of'} else 255, key)
        if 'n' in source:
            if not isinstance(source['n'], str) or len(source['n'].encode()) > 128:
                raise ValueError('invalid native segment name')
            segment['n'] = source['n']
        colors = source['col']
        if not isinstance(colors, list) or not 1 <= len(colors) <= 3:
            raise ValueError('invalid native colors')
        for color in colors:
            if not isinstance(color, list) or len(color) not in (3, 4):
                raise ValueError('invalid native color')
            for channel in color:
                integer(channel, 0, 255, 'color channel')
        segment['col'] = deepcopy(colors)
        saved.append(segment)
    payload['seg'] = saved + [{'id': i, 'stop': 0} for i in range(maximum) if i not in ids]
    pid = integer(state.get('ps', -1), -1, 250, 'preset')
    playlist = integer(state.get('pl', -1), -1, 250, 'playlist')
    result = {'address': address, 'mac': mac, 'payload': payload,
              'preset': pid, 'playlist': playlist, 'captured_at': time.time()}
    if playlist == 0:
        result['unsupported'] = 'unsaved native playlists cannot be reconstructed from the state API'
    if state.get('nl', {}).get('on'):
        result['unsupported'] = 'active native nightlight recovery is not implemented'
    return result


class NativeRecovery:
    def __init__(self, devices, directory, clock=time.monotonic):
        self.devices, self.clock = devices, clock
        self.lock = threading.RLock()
        self.path = directory / 'native-snapshots.json'
        stored = read_json(self.path, {'version': 1, 'devices': {}})
        if not isinstance(stored, dict) or stored.get('version') != 1 or not isinstance(stored.get('devices'), dict):
            raise ValueError('invalid native-snapshots.json')
        self.saved = stored['devices']
        self.pending, self.busy, self.next_poll, self.generation = set(), set(), {}, {}
        self.status = {}
        self.capture_token = None

    def cancel(self, key):
        with self.lock:
            self.generation[key] = self.generation.get(key, 0) + 1
            self.pending.discard(key)

    def command_sent(self, key):
        # A newer command supersedes the cached state. Until the device has
        # applied it and been polled again, resume may use the desired command.
        with self.lock:
            if key in self.saved:
                candidate = dict(self.saved)
                del candidate[key]
                save_json(self.path, {'version': 1, 'devices': candidate})
                self.saved = candidate
            self.next_poll[key] = self.clock() + 0.25
            self.status[key] = {'recovery': 'awaiting checkpoint',
                                'recovery_detail': 'new ambient command sent; waiting for a device poll'}

    def resume(self):
        with self.lock:
            keys = {key for key, device in self.devices.config.items()
                    if device['mode'] == 'effect' and isinstance(self.saved.get(key), dict)
                    and self.saved[key].get('command') == self.devices.desired.get(key)}
            for key in keys:
                self.generation[key] = self.generation.get(key, 0) + 1
                self.next_poll[key] = 0
            self.pending.update(keys)
            return keys

    def _guard(self, epoch):
        with self.devices.state_lock:
            status = self.devices.ownership.status()
            if not status['allowed'] or status['epoch'] != epoch:
                raise PermissionError('show takeover or ambient state changed')

    def _check_generation(self, key, generation):
        with self.lock:
            if self.generation.get(key, 0) != generation:
                raise PermissionError('newer ambient command superseded recovery')

    def _write(self, device, payload, epoch, generation, mac):
        info = self.devices.request(device['address'], '/json/info')
        if info.get('mac') != mac:
            raise ValueError('device identity changed; snapshot will not be restored')
        if info.get('live') is not False:
            raise PermissionError('device is receiving realtime data or its state is unknown')
        self._guard(epoch)
        self._check_generation(device['id'], generation)
        # nn suppresses notification for this request without changing sync settings.
        result = self.devices.request(device['address'], '/json/state', {**payload, 'udpn': {'nn': True}})
        if not isinstance(result, dict) or result.get('error') or result.get('success') is False:
            raise ValueError('native device rejected restoration')
        return result

    def _restore(self, device, epoch, generation):
        key = device['id']
        with self.lock:
            saved = deepcopy(self.saved[key])
        if saved.get('address') != device['address']:
            raise ValueError('device address changed; snapshot will not be restored')
        if saved.get('unsupported'):
            raise ValueError(saved['unsupported'])
        # Re-validate persisted snapshots before sending anything to a device.
        payload = saved['payload']
        active = [s for s in payload['seg'] if s.get('stop', 1) != 0]
        checked = snapshot({'info': {'live': False, 'mac': saved['mac'], 'leds': {'maxseg': len(payload['seg'])}},
                            'state': {**payload, 'seg': active, 'ps': saved['preset'], 'pl': saved['playlist']}}, device['address'])
        if checked.get('unsupported'):
            raise ValueError(checked['unsupported'])
        playlist = saved['playlist']
        if playlist > 0:
            self._write(device, {'playlist': {}}, epoch, generation, saved['mac'])
            self._write(device, {'ps': playlist}, epoch, generation, saved['mac'])
            # Preset selection is asynchronous on native WLED. Wait for it before
            # restoring power/brightness; never send segment patches into a playlist.
            deadline = time.monotonic() + 1
            started = False
            while time.monotonic() < deadline:
                self._guard(epoch)
                current = self.devices.request(device['address'], '/json/state')
                if current.get('pl') == playlist:
                    started = True
                    break
                time.sleep(0.05)
            if not started:
                raise ValueError('native playlist did not start; check that its preset still exists')
            self._write(device, {k: payload[k] for k in ('on', 'bri')}, epoch, generation, saved['mac'])
            detail = 'saved playlist restarted from beginning; native cursor is not exposed'
        else:
            restore = checked['payload']
            restore.update(playlist={}, nl={'on': False})
            if saved['preset'] > 0:
                restore['pd'] = saved['preset']
            self._write(device, restore, epoch, generation, saved['mac'])
            detail = 'lighting snapshot restored'
        with self.lock:
            if self.generation.get(key, 0) == generation:
                self.pending.discard(key)
                self.status[key] = {'recovery': 'restored', 'recovery_detail': detail}

    def _capture(self, device, epoch, token, generation):
        if token is None:
            self._guard(epoch)
        else:
            with self.lock:
                if token is not self.capture_token:
                    return
        saved = snapshot(self.devices.request(device['address'], '/json'), device['address'])
        # Serialize with ownership transitions so an automatic takeover cannot
        # publish a snapshot observed after the ambient epoch ended.
        with self.devices.state_lock:
            self._check_generation(device['id'], generation)
            if token is None:
                self._guard(epoch)
            elif self.devices.ownership.epoch != epoch:
                return
            with self.devices.mutex:
                saved['command'] = deepcopy(self.devices.desired.get(device['id']))
            with self.lock:
                if token is not None and token is not self.capture_token:
                    return
                key = device['id']
                previous = self.saved.get(key, {})
                changed = {k: v for k, v in saved.items() if k != 'captured_at'} != {k: v for k, v in previous.items() if k != 'captured_at'}
                if changed:
                    candidate = {**self.saved, key: saved}
                    save_json(self.path, {'version': 1, 'devices': candidate})
                    self.saved = candidate
                self.status[key] = {'recovery': 'snapshot ready' if not saved.get('unsupported') else 'unsupported',
                                    'recovery_detail': saved.get('unsupported', 'ambient state captured')}

    def _work(self, device, epoch, generation, restore=False, token=None):
        key = device['id']
        try:
            with self.devices.locks[key]:
                self._check_generation(key, generation)
                if restore:
                    self._restore(device, epoch, generation)
                else:
                    self._capture(device, epoch, token, generation)
        except Exception as exc:
            with self.lock:
                if self.generation.get(key, 0) == generation:
                    self.status[key] = {'recovery': 'waiting' if restore else 'capture failed', 'recovery_detail': str(exc)}
        finally:
            with self.lock:
                self.busy.discard(key)

    def tick(self):
        """Schedule bounded polling/retries; called with the controller state lock."""
        status = self.devices.ownership.status()
        if not status['allowed']:
            return
        now = self.clock()
        with self.devices.mutex, self.lock:
            self.devices.futures = {f for f in self.devices.futures if not f.done()}
            for key, device in self.devices.config.items():
                if (device['mode'] != 'effect' or key in self.busy or now < self.next_poll.get(key, 0)
                        or len(self.devices.futures) >= 64):
                    continue
                self.busy.add(key)
                self.next_poll[key] = now + 2
                self.devices.futures.add(self.devices.executor.submit(self._work, device, status['epoch'],
                    self.generation.get(key, 0), key in self.pending))

    def capture_before_show(self, epoch):
        """Best effort, read-only capture after draining commands, before hook returns."""
        token = object()
        jobs = {}
        with self.devices.mutex, self.lock:
            self.capture_token = token
            for key, device in self.devices.config.items():
                if device['mode'] == 'effect':
                    self.busy.add(key)
                    job = self.devices.executor.submit(self._work, device, epoch, self.generation.get(key, 0), False, token)
                    jobs[key] = job
                    self.devices.futures.add(job)
        wait(jobs.values(), timeout=2)
        with self.lock:
            if self.capture_token is token:
                self.capture_token = None  # late responses must not replace pre-show state
                for key, job in jobs.items():
                    if not job.done():
                        self.status[key] = {'recovery': 'capture timeout',
                                            'recovery_detail': 'pre-show capture timed out; last checkpoint retained'}

    def public(self, key):
        with self.lock:
            saved = self.saved.get(key)
            return {**self.status.get(key, {}), 'snapshot_available': bool(saved),
                    'snapshot_time': saved.get('captured_at') if isinstance(saved, dict) else None,
                    'restore_pending': key in self.pending}
