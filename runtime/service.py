import argparse
from copy import deepcopy
import json
import logging
import os
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
from . import schedules, layout, backup

ROOT = Path(__file__).resolve().parents[1]


class Controller:
    def __init__(self, config, directory, engine, ownership, persist_import=True):
        self.config, self.directory, self.engine, self.ownership = config, directory, engine, ownership
        self.lock = threading.RLock()
        self.palettes = Palettes(directory, engine)
        self.state = State(directory, engine, persist_import=persist_import)
        self.devices = Devices(config, ownership, self.lock, directory)
        self.dirty = True
        self.render_ms = 0
        self.frames_rendered = 0
        self.render_wall_ms = 0.0
        self.render_peak_ms = 0.0
        self.was_allowed = False
        self.rendered_nightlight = None
        self.started = time.monotonic()
        self.latest_frame = bytes(len(engine.buffer))
        self.timers = Timers(config.get('timers', []), config.get('location'), directory / 'timers-fired.json')
        self.integrations = {}
        from .network import Network
        self.network = Network(self)
        self.link = None
        self.restart_requested_at = None
        self.configuration_dirty = False
        self.supervised = False

    def info(self):
        owned = self.ownership.status()['show_owned']
        p = self.config['pixels']
        sync = self.sync_state()
        discovery = self.integrations.get('discovery')
        return {'ver': '16.0.1-linux-alpha.2', 'vid': 2609110, 'name': self.config.get('name', 'WLED for FPP'),
                'arch': 'linux', 'brand': 'WLED', 'product': 'FPP Linux alpha',
                'live': owned, 'liveseg': -1, 'lm': 'FPP show', 'lip': '',
                'leds': {'count': p['count'], 'rgbw': p['channels'] == 4, 'wv': p['channels'] == 4,
                         'cct': False, 'seglc': [3 if p['channels'] == 4 else 1] * len(self.state.value['seg']),
                         'lc': 3 if p['channels'] == 4 else 1, 'maxseg': 32, 'bootps': -1,
                         **({'matrix': {'w': self.engine.width, 'h': self.engine.height}} if self.engine.height > 1 else {})},
                'str': False, 'sync': {'recv': sync['recv'], 'send': sync['send']}, 'wifi': {'ap': False, 'signal': 100},
                'fs': {'u': 0, 't': 0, 'pmt': 1}, 'ndc': len(discovery.public()) if discovery else -1, 'ws': 0,
                'fxcount': len(self.engine.effects), 'palcount': len(self.engine.palettes) + self.palettes.count,
                'cpalcount': self.palettes.count, 'umpalcount': 0, 'palrev': self.palettes.revision,
                'uptime': int(time.monotonic() - self.started), 'opt': 0, 'maps': [],
                'fpp': self.status()}

    def status(self):
        return {**self.ownership.status(), 'release': 'alpha.2',
                'unsupported_effect_ids': sorted(self.engine.unsupported),
                'unsupported': ['ESP firmware and provisioning', 'ESP-NOW', 'GPIO', 'audio input',
                                'usermods', 'Philips Hue', 'file-based fonts',
                                'custom transition styles', 'boot preset overrides'],
                'integrations': {name: True for name in self.integrations},
                'devices': self.devices.public()}

    def get(self, path):
        path = {'/json/eff':'/json/effects', '/json/pal':'/json/palettes'}.get(path, path)
        with self.lock:
            if path == '/api/backup':
                return backup.export(self)
            if path == '/api/backup/previous':
                previous=read_json(self.directory/'before-restore.json',None)
                if previous is None: raise KeyError('No previous setup backup exists')
                return previous
            if path == '/api/mqtt':
                integration = self.integrations.get('mqtt')
                return {'config':read_json(self.directory / 'config.json', self.config).get('mqtt', {}),
                        'credentials_saved':bool(read_json(self.directory / 'mqtt-secret.json', {})),
                        'connected':bool(integration and integration.client.is_connected())}
            if path == '/api/diagnostics':
                return {'sample_time':time.monotonic(),'frames_rendered':self.frames_rendered,
                        'render_total_ms':self.render_wall_ms,'render_peak_ms':self.render_peak_ms,
                        'configured_fps':self.config.get('fps',40),'pixels':self.config['pixels'],
                        'observer_healthy':self.ownership.status()['observer_healthy'],
                        'acknowledged_frame':str(self.link.acknowledged) if self.link else None,
                        'scope':'Runtime render timing and FPP acknowledgement; does not verify physical lights.'}
            if path == '/api/layout':
                return layout.sources()
            if path == '/api/network':
                return self.network.public()
            if path == '/api/schedules':
                return schedules.public(self)
            if path == '/api/preview':
                allowed = self.ownership.status()['allowed']
                count = self.config['pixels']['count']
                channels = self.config['pixels']['channels']
                stride = max(1, (count + 4095) // 4096)
                return {'allowed': allowed, 'width': self.engine.width, 'height': self.engine.height,
                        'count': count, 'stride': stride, 'channels': channels,
                        'pixels': [[i, *self.latest_frame[i * channels:(i + 1) * channels]]
                                   for i in range(0, count, stride)] if allowed else []}
            if path == '/json/live':
                count = self.config['pixels']['count']
                channels = self.config['pixels']['channels']
                stride = max(1, (count + 255) // 256)
                allowed = self.ownership.status()['allowed']
                colors = []
                for index in range(0, count, stride):
                    pixel = self.latest_frame[index*channels:(index+1)*channels] if allowed else bytes(channels)
                    white = pixel[3] if channels == 4 else 0
                    colors.append(''.join(f'{min(255,value+white):02X}' for value in pixel[:3]))
                return {'leds':colors,'n':stride}
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
                return {'state': self.public_state(), 'info': self.info(),
                        'effects': self.effect_names(), 'palettes': self.engine.palettes}
            if path == '/json/state':
                return self.public_state()
            if path == '/json/info':
                return self.info()
            if path == '/json/effects':
                return self.effect_names()
            if path == '/json/fxdata':
                return [m.partition('@')[2] for m in self.engine.metadata]
            if path == '/json/palettes':
                return self.engine.palettes
            if path == '/json/nodes':
                discovery = self.integrations.get('discovery')
                return {'nodes': [{**n, 'ip': n['address']} for n in discovery.public()] if discovery else []}
            if path == '/presets.json':
                return deepcopy(self.state.presets)
            if path == '/api/status':
                return self.status()
            if path == '/api/config/status':
                saved = read_json(self.directory / 'config.json', self.config)
                return {'saved': saved, 'restart_required': saved != self.config or self.configuration_dirty or (self.directory/'restore-pending.json').exists(),
                        'restore_pending':(self.directory/'restore-pending.json').exists(),
                        'restart_available': self.supervised, 'started': self.started}
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

    def sync_state(self):
        udp = self.integrations.get('udp')
        cfg = udp.config if udp else {}
        return {'send': bool(udp and cfg.get('send', True)), 'recv': bool(udp and cfg.get('receive', True)),
                'sgrp': cfg.get('groups', 1), 'rgrp': cfg.get('groups', 1)}

    def public_state(self):
        return {**self.state.public(), 'udpn': self.sync_state()}

    def post(self, path, payload):
        if not isinstance(payload, dict):
            raise ValueError('request must be an object')
        if path == '/api/network':
            return self.network.configure(payload)
        if path == '/api/restore':
            report=backup.preview(payload.get('backup'), self.engine.lib._name)
            if payload.get('preview', True):return report
            with self.lock:
                return backup.stage(self,payload['backup'],payload.get('revision'))
        if path == '/api/restore/cancel':
            if payload != {}:raise ValueError('Cancel restore accepts an empty object.')
            with self.lock:
                (self.directory/'restore-pending.json').unlink(missing_ok=True)
                return {'cancelled':True}
        drain = False
        revoked = None
        capture_epoch = None
        with self.lock:
            if path == '/api/mqtt':
                candidate = deepcopy(read_json(self.directory / 'config.json', self.config))
                mqtt = payload.get('config')
                if not isinstance(mqtt, dict) or set(mqtt)-{'enabled','host','port','topic','id','tls'}:
                    raise ValueError('Unsupported MQTT settings.')
                for key in ('enabled','tls'):
                    if type(mqtt.get(key, False)) is not bool: raise ValueError(key+' must be on or off.')
                candidate['mqtt'] = mqtt
                validate(candidate)
                action = payload.get('credentials', 'keep')
                if action not in ('keep','replace','clear'): raise ValueError('Unknown credentials action.')
                if action != 'keep':
                    secret = {} if action == 'clear' else {'username':payload.get('username'),'password':payload.get('password')}
                    if secret and (not all(isinstance(v,str) and len(v)<=1024 for v in secret.values()) or not secret['username']):
                        raise ValueError('Enter a username and password of at most 1024 characters.')
                    save_json(self.directory / 'mqtt-secret.json', secret)
                    (self.directory / 'mqtt-secret.json').chmod(0o600)
                    self.configuration_dirty = True
                save_json(self.directory / 'config.json', candidate)
                return {'saved':True,'restart_required':True}
            elif path == '/api/layout':
                source = layout.sources()
                ids = payload.get('items', [])
                if not isinstance(ids, list) or any(type(i) is not int for i in ids) or len(ids) != len(set(ids)):
                    raise ValueError('Choose distinct FPP items from the list.')
                selected = [item for item in source['items'] if item['id'] in ids]
                if len(selected) != len(ids):
                    raise ValueError('FPP layout changed; refresh the item list.')
                saved_config = read_json(self.directory / 'config.json', self.config)
                if 'groups' in payload:
                    if payload.get('source_revision') != source['revision']:
                        raise ValueError('FPP sources changed. Read FPP lights again before previewing or saving.')
                    report = layout.compose(saved_config, source['items'], payload['groups'])
                else:
                    report = layout.translate(saved_config, selected)
                if payload.get('preview', True):
                    return report
                if self.ownership.status()['show_owned']:
                    raise PermissionError('Wait until shows end and FPP status is healthy before importing a layout.')
                if payload.get('revision') != report['config']['imported_layout']['revision']:
                    raise ValueError('FPP layout changed since preview. Preview it again.')
                save_json(self.directory / 'layout-backup.json', {'config':self.config,'state':self.state.public(),
                    'playlist':read_json(self.directory / 'playlist.json', None)})
                save_json(self.directory / 'config.json', report['config'])
                return {'saved':True,'restart_required':True}
            elif path == '/api/command':
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
            elif path == '/api/schedules':
                return schedules.update(self, payload)
            elif path == '/api/runtime/restart':
                if payload != {}:
                    raise ValueError('restart accepts an empty object')
                if not self.supervised:
                    raise ValueError('Runtime restart requires the FPP supervised service')
                if self.ownership.status()['show_owned']:
                    raise PermissionError('Cannot restart during a show or while FPP ownership is uncertain')
                validate(read_json(self.directory / 'config.json', self.config))
                self.restart_requested_at = time.monotonic()
                return {'restarting': True}
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
                result = {'state': self.public_state(), 'info': self.info()}
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
            notify = False
            for preset in self.timers.due():
                if allowed:
                    try:
                        self.state.select(preset)
                        self.dirty = True
                        notify = True
                    except ValueError as exc:
                        logging.warning('Timer skipped: %s', exc)
            if not allowed:
                self.was_allowed = False
                return self.latest_frame, False
            if not self.was_allowed:
                self.state.restart_entry()
                self.devices.resume()
                self.dirty = True
                notify = True
            elif self.state.tick(step_ms):
                self.dirty = True
                notify = True
            if self.state.tick_nightlight(step_ms):
                self.dirty = True
            self.devices.recovery.tick()
            if self.dirty:
                render_state = self.state.value
                if self.state.nightlight:
                    render_state = self.state.nightlight.render_state(render_state)
                    if self.state.nightlight.mode == 3 and self.rendered_nightlight is not self.state.nightlight:
                        # Reset effect 104 even when restarting the same direction/duration.
                        # Two mode assignments mark upstream segment runtime for reset;
                        # no intermediate frame is rendered or transmitted.
                        reset = deepcopy(render_state)
                        for segment in reset['seg']:
                            if segment['id'] in self.state.nightlight.colors:
                                segment['fx'] = 0
                        self.engine.apply(reset)
                self.engine.apply(render_state)
                self.rendered_nightlight = self.state.nightlight
                self.dirty = False
            self.render_ms += step_ms
            if notify and 'udp' in self.integrations:
                self.integrations['udp'].send()
            started = time.perf_counter()
            self.latest_frame = self.engine.render(self.render_ms)
            elapsed = (time.perf_counter()-started)*1000
            self.frames_rendered += 1
            self.render_wall_ms += elapsed
            self.render_peak_ms = max(self.render_peak_ms, elapsed)
            self.was_allowed = True
            return self.latest_frame, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', type=Path, default=Path(os.environ.get('MEDIADIR', '/home/fpp/media')) / 'plugindata/FPP_WLED_10.x')
    parser.add_argument('--run-dir', type=Path, default=Path('/run/fpp-wled'))
    parser.add_argument('--library', type=Path, default=ROOT / 'build/libwled_linux.so')
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    # Acquire the runtime lock before startup can apply a staged layout.
    if not args.validate:
        import fcntl
        args.run_dir.mkdir(parents=True, exist_ok=True)
        lock = (args.run_dir / 'runtime.lock').open('w')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        backup.apply_pending(args.state_dir)
    config = validate(read_json(args.state_dir / 'config.json', None))
    engine = Engine(args.library, config)
    ownership = Ownership(args.state_dir / 'ownership.json', config.get('quiet_ms', 2000), config.get('heartbeat_ms', 500))
    controller = Controller(config, args.state_dir, engine, ownership, persist_import=not args.validate)
    if args.validate:
        engine.apply(controller.state.value)
        print(json.dumps({'valid': True, 'effects': len(engine.effects), 'supported': len(engine.effects) - len(engine.unsupported)}))
        controller.devices.close()
        return
    from .web import start_servers
    # A flock prevents a second runtime from unlinking the live IPC endpoint.
    link = Link(args.run_dir)
    controller.link = link
    controller.supervised = os.environ.get('FPP_WLED_SUPERVISED') == '1'
    servers = start_servers(controller, args.run_dir, args.state_dir)
    from .integrations import MQTT
    if config.get('mqtt', {}).get('enabled', False):
        controller.integrations['mqtt'] = MQTT(controller)
    controller.network.configure()
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    interval = 1 / config.get('fps', 40)
    previous = time.monotonic()
    try:
        while not stopping.is_set():
            if controller.restart_requested_at is not None and time.monotonic() - controller.restart_requested_at >= 0.5:
                break
            started = time.monotonic()
            with controller.lock:
                link.poll(ownership)
                data, allowed = controller.tick(min(int((started - previous) * 1000), 100))
                link.send(data, config, allowed)
            if 'mqtt' in controller.integrations:
                controller.integrations['mqtt'].tick()
            controller.network.tick()
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
    if controller.restart_requested_at is not None:
        raise SystemExit(75) # systemd Restart=on-failure starts the saved configuration


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    main()
