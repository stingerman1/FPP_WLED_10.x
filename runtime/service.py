import argparse
from copy import deepcopy
import json
import logging
from pathlib import Path
import signal
import socket
import threading
import time

from .config import validate
from .config import integer
from .devices import Devices
from .engine import Engine
from .ipc import Link
from .ownership import Ownership
from .preset_import import import_presets
from .palettes import Palettes
from .state import State
from .storage import read_json, save_json
from .timers import Timers

ROOT = Path(__file__).resolve().parents[1]


class Controller:
    def __init__(self, config, directory, engine, ownership):
        self.config, self.directory, self.engine, self.ownership = config, directory, engine, ownership
        self.lock = threading.RLock()
        self.palettes = Palettes(directory, engine)
        self.state = State(directory, engine)
        self.devices = Devices(config, ownership, self.lock, directory)
        self.dirty = True
        self.render_ms = 0
        self.was_allowed = False
        self.started = time.monotonic()
        self.latest_frame = bytes(len(engine.buffer))
        self.timers = Timers(config.get('timers', []))
        self.integrations = {}
        self.link = None

    def info(self):
        owned = self.ownership.status()['show_owned']
        p = self.config['pixels']
        return {'ver': '16.0.1-linux-alpha.1', 'vid': 2609070, 'name': 'WLED for FPP',
                'arch': 'linux', 'brand': 'WLED', 'product': 'FPP Linux alpha',
                'live': owned, 'liveseg': -1, 'lm': 'FPP show', 'lip': '',
                'leds': {'count': p['count'], 'rgbw': p['channels'] == 4, 'wv': p['channels'] == 4,
                         'cct': False, 'seglc': [3 if p['channels'] == 4 else 1] * len(self.state.value['seg']),
                         'lc': 3 if p['channels'] == 4 else 1, 'maxseg': 32, 'bootps': -1,
                         **({'matrix': {'w': self.engine.width, 'h': self.engine.height}} if self.engine.height > 1 else {})},
                'str': False, 'sync': {'recv': False, 'send': False}, 'wifi': {'ap': False, 'signal': 100},
                'fs': {'u': 0, 't': 0, 'pmt': 1}, 'ndc': 0, 'ws': 0,
                'fxcount': len(self.engine.effects), 'palcount': len(self.engine.palettes) + self.palettes.count,
                'cpalcount': self.palettes.count, 'umpalcount': 0, 'palrev': self.palettes.revision,
                'uptime': int(time.monotonic() - self.started), 'opt': 0, 'maps': [],
                'fpp': self.status()}

    def status(self):
        return {**self.ownership.status(), 'release': 'alpha.1',
                'unsupported_effect_ids': sorted(self.engine.unsupported),
                'unsupported': ['ESP firmware and provisioning', 'ESP-NOW', 'GPIO', 'audio input',
                                'usermods', 'Philips Hue', 'file-based fonts',
                                'custom transition styles', 'boot preset overrides'],
                'integrations': {name: True for name in self.integrations},
                'devices': self.devices.public()}

    def get(self, path):
        with self.lock:
            if path.startswith('/json/palx'):
                from urllib.parse import urlsplit, parse_qs
                url = urlsplit(path)
                if url.path != '/json/palx':
                    raise KeyError(path)
                query = parse_qs(url.query, keep_blank_values=True)
                if set(query) - {'page'} or len(query.get('page', ['0'])) != 1:
                    raise ValueError('palx accepts one page parameter')
                return self.palettes.page(int(query.get('page', ['0'])[0]))
            if path == '/api/palettes':
                return self.palettes.public()
            if path.startswith('/palette') and path.endswith('.json'):
                slot = path[len('/palette'):-len('.json')]
                if not slot.isdigit() or str(int(slot)) != slot:
                    raise KeyError(path)
                return deepcopy(self.palettes.saved[slot])
            if path in ('/json', '/json/si'):
                return {'state': self.state.public(), 'info': self.info(),
                        'effects': self.effect_names(), 'palettes': self.engine.palettes}
            if path == '/json/state':
                return self.state.public()
            if path == '/json/info':
                return self.info()
            if path == '/json/effects':
                return self.effect_names()
            if path == '/json/fxdata':
                return [m.partition('@')[2] for m in self.engine.metadata]
            if path == '/json/palettes':
                return self.engine.palettes
            if path == '/json/nodes':
                return {'nodes': []}
            if path == '/presets.json':
                return deepcopy(self.state.presets)
            if path == '/api/status':
                return self.status()
            if path == '/api/config':
                return deepcopy(self.config)
            if path == '/api/devices':
                return self.devices.public()
            if path == '/api/discovery':
                return self.integrations['discovery'].public() if 'discovery' in self.integrations else []
            raise KeyError(path)

    def effect_names(self):
        return ['RSVD - unsupported on Linux' if i in self.engine.unsupported else name
                for i, name in enumerate(self.engine.effects)]

    def post(self, path, payload):
        if not isinstance(payload, dict):
            raise ValueError('request must be an object')
        drain = False
        revoked = None
        capture_epoch = None
        with self.lock:
            if path == '/api/command':
                operation = payload.get('operation')
                if operation == 'status':
                    return self.status()
                was_allowed = self.ownership.status()['allowed']
                result = self.ownership.command(operation, payload.get('source'))
                if operation == 'show-start' and was_allowed:
                    capture_epoch = self.ownership.epoch
                drain = operation in ('show-start', 'ambient-disable')
                if drain and self.link:
                    revoked = self.link.send(self.latest_frame, self.config, False)
            elif path == '/api/palettes':
                result = self.palettes.update(payload, self.state, self.ownership.status()['allowed'])
                self.dirty = True
                return result
            elif path == '/api/presets/import':
                return import_presets(self.state, payload)
            elif path == '/api/config':
                validate(payload)
                save_json(self.directory / 'config.json', payload)
                return {'saved': True, 'restart_required': True}
            elif path == '/api/devices/command':
                return self.devices.command(payload.get('target', ''), payload.get('state'))
            elif path in ('/json', '/json/state', '/json/si'):
                if 'rmcpal' in payload:
                    if set(payload) - {'rmcpal', 'v'}:
                        raise ValueError('rmcpal must be a standalone palette deletion')
                    return self.palettes.update({'slot': payload['rmcpal'], 'delete': True}, self.state,
                                                self.ownership.status()['allowed'])
                if 'psave' in payload:
                    patch = {k: v for k, v in payload.items() if k not in ('psave', 'ib', 'sb', 'sc', 'v', 'o')}
                    options = {k: payload[k] for k in ('ib', 'sb', 'sc', 'o') if k in payload}
                    self.state.save_preset(payload['psave'], patch, options)
                    return {'success': True}
                if 'pdel' in payload:
                    self.state.delete_preset(payload['pdel'])
                    return {'success': True}
                if not self.ownership.status()['allowed']:
                    raise PermissionError('ambient changes rejected: show owns targets or ambient is disabled')
                if 'np' in payload:
                    if type(payload['np']) is not bool or set(payload) - {'np', 'v', 'time'}:
                        raise ValueError('np requires a standalone boolean playlist-advance request')
                    if payload['np']:
                        self.state.tick(0, advance=True)
                elif 'pd' in payload:
                    # Upstream UI sends a cached preset body with pd instead of
                    # recalling ps. Validate the body atomically before stopping.
                    pid = integer(payload['pd'], 1, 250, 'preset id')
                    patch = {k: v for k, v in payload.items() if k not in ('pd', 'ps', 'pl')}
                    self.state.set(patch)
                    self.state.stop_playlist()
                    self.state.value['ps'] = pid
                    save_json(self.directory / 'state.json', self.state.value)
                elif 'ps' in payload:
                    if set(payload) - {'ps', 'v', 'time'}:
                        raise ValueError('preset recall supports ps, v and time only; send lighting changes separately')
                    self.state.select(payload['ps'])
                elif 'playlist' in payload:
                    if payload['playlist'] == {}:
                        self.state.stop_playlist()
                    else:
                        self.state.start_playlist(payload['playlist'])
                else:
                    self.state.set(payload)
                    self.state.stop_playlist()
                self.dirty = True
                if 'udp' in self.integrations:
                    self.integrations['udp'].send()
                result = {'state': self.state.public(), 'info': self.info()}
            else:
                raise KeyError(path)
        if drain:
            self.devices.drain()
            if capture_epoch is not None:
                self.devices.recovery.capture_before_show(capture_epoch)
            if self.link:
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    with self.lock:
                        if revoked and revoked <= self.link.acknowledged <= self.link.serial and not self.link.ack_allowed:
                            break
                    time.sleep(0.01)
                else:
                    raise TimeoutError('show lock is stored, but FPP did not acknowledge ambient revocation')
        return result

    def tick(self, step_ms):
        with self.lock:
            allowed = self.ownership.status()['allowed']
            for preset in self.timers.due():
                if allowed:
                    try:
                        self.state.select(preset)
                        self.dirty = True
                    except ValueError as exc:
                        logging.warning('Timer skipped: %s', exc)
            if not allowed:
                self.was_allowed = False
                return self.latest_frame, False
            if not self.was_allowed:
                self.state.restart_entry()
                self.devices.resume()
                self.dirty = True
            elif self.state.tick(step_ms):
                self.dirty = True
            self.devices.recovery.tick()
            if self.dirty:
                self.engine.apply(self.state.value)
                self.dirty = False
            self.render_ms += step_ms
            self.latest_frame = self.engine.render(self.render_ms)
            self.was_allowed = True
            return self.latest_frame, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', type=Path, default=Path('/home/fpp/media/config/plugin.FPP_WLED_10.x'))
    parser.add_argument('--run-dir', type=Path, default=Path('/run/fpp-wled'))
    parser.add_argument('--library', type=Path, default=ROOT / 'build/libwled_linux.so')
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    config = validate(read_json(args.state_dir / 'config.json', None))
    engine = Engine(args.library, config)
    ownership = Ownership(args.state_dir / 'ownership.json', config.get('quiet_ms', 2000), config.get('heartbeat_ms', 500))
    controller = Controller(config, args.state_dir, engine, ownership)
    if args.validate:
        engine.apply(controller.state.value)
        print(json.dumps({'valid': True, 'effects': len(engine.effects), 'supported': len(engine.effects) - len(engine.unsupported)}))
        controller.devices.close()
        return
    from .web import start_servers
    # A flock prevents a second runtime from unlinking the live IPC endpoint.
    import fcntl
    args.run_dir.mkdir(parents=True, exist_ok=True)
    lock = (args.run_dir / 'runtime.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    link = Link(args.run_dir)
    controller.link = link
    servers = start_servers(controller, args.run_dir, args.state_dir)
    from .integrations import MQTT, Discovery
    from .udp import Sync
    if config.get('mqtt', {}).get('enabled', False):
        controller.integrations['mqtt'] = MQTT(controller)
    if config.get('discovery', False):
        controller.integrations['discovery'] = Discovery()
    if config.get('udp', {}).get('enabled', False):
        controller.integrations['udp'] = Sync(controller)
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    interval = 1 / config.get('fps', 40)
    previous = time.monotonic()
    try:
        while not stopping.is_set():
            started = time.monotonic()
            with controller.lock:
                link.poll(ownership)
                data, allowed = controller.tick(min(int((started - previous) * 1000), 100))
                link.send(data, config, allowed)
            if 'mqtt' in controller.integrations:
                controller.integrations['mqtt'].tick()
            if 'udp' in controller.integrations:
                controller.integrations['udp'].tick()
            previous = started
            stopping.wait(max(0, interval - (time.monotonic() - started)))
    finally:
        with controller.lock:
            ownership.enabled = False # in-memory shutdown gate; preserve the user's persisted intent
        link.send(controller.latest_frame, config, False)
        controller.devices.close()
        for integration in controller.integrations.values():
            integration.close()
        for server in servers:
            server.stop_event.set()
            server.shutdown()
            server.server_close()
        link.close()
        lock.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
