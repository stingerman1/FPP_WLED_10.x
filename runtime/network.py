"""Live network setup; listener changes do not require restarting the renderer."""
from copy import deepcopy
import threading
from .config import validate
from .storage import save_json, read_json
from .discovery import Discovery
from .udp import Sync

FIELDS = {'discovery', 'discoverable', 'discovery_http_port', 'name', 'udp'}


class Network:
    def __init__(self, controller):
        self.controller = controller
        self.lock = threading.Lock()
        self.error = None

    def public(self):
        c = self.controller
        udp = c.integrations.get('udp')
        discovery = c.integrations.get('discovery')
        return {'config': {k: deepcopy(v) for k, v in c.config.items() if k in FIELDS},
            'discovery_active': discovery is not None, 'sync_active': udp is not None,
            'peers': sorted(udp.peers) if udp else [],
            'sent': udp.sent if udp else 0, 'received': udp.received if udp else 0,
            'error': self.error or (udp.last_error if udp else None) or (discovery.last_error if discovery else None)}

    def configure(self, payload=None):
        c = self.controller
        with self.lock:
            if payload is not None:
                if not isinstance(payload, dict) or set(payload) - FIELDS:
                    raise ValueError('unsupported network setting')
                with c.lock:
                    candidate = deepcopy(c.config)
                    candidate.update(payload)
                    validate(candidate)
                    # Preserve separately saved configuration waiting for restart.
                    saved = read_json(c.directory / 'config.json', candidate)
                    saved.update(payload)
                    validate(saved)
                    save_json(c.directory / 'config.json', saved)
                    c.config = candidate
            for name in ('udp', 'discovery'):
                with c.lock:
                    old = c.integrations.pop(name, None)
                if old:
                    old.close()
            self.error = None
            for name, cls, enabled in (('discovery', Discovery, c.config.get('discovery', False)),
                                       ('udp', Sync, c.config.get('udp', {}).get('enabled', False))):
                if enabled:
                    try:
                        instance = cls(c)
                        with c.lock:
                            c.integrations[name] = instance
                    except Exception as exc:
                        self.error = f'{name}: {exc}'
            return self.public()

    def tick(self):
        # Serialize close/reconfigure with nonblocking network work. Never delay
        # FPP observation while an HTTP request waits for mDNS shutdown.
        if not self.lock.acquire(blocking=False):
            return
        try:
            for name in ('discovery', 'udp'):
                integration = self.controller.integrations.get(name)
                if integration:
                    integration.tick()
        finally:
            self.lock.release()
