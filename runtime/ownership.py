"""Fail-closed ownership state machine, independent of pixel values and wall clock."""
import re
import time
from .storage import save_json, read_json


class Ownership:
    def __init__(self, path, quiet_ms=2000, timeout_ms=500, clock=time.monotonic_ns):
        self.path, self.clock = path, clock
        self.quiet_ns, self.timeout_ns = quiet_ms * 1_000_000, timeout_ms * 1_000_000
        self.enabled = False
        self.locks = set()
        self.fault = None
        self.transport_fault = None
        self.observed = None
        self.seen_ns = None
        self.clear_since = None
        self.epoch = 0
        try:
            saved = read_json(path, {'version': 1, 'enabled': False, 'locks': []})
            if saved.get('version') != 1 or type(saved.get('enabled')) is not bool or not isinstance(saved.get('locks'), list):
                raise ValueError('invalid ownership state')
            for source in saved['locks']:
                self.validate_source(source)
            self.enabled, self.locks = saved['enabled'], set(saved['locks'])
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            self.fault = 'ownership storage: ' + str(exc)

    @staticmethod
    def validate_source(source):
        if not isinstance(source, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}', source):
            raise ValueError('source must be a stable 1-128 character identifier')
        if source.startswith('fpp:'):
            raise ValueError('fpp: is reserved for automatic ownership')

    def persist(self):
        try:
            save_json(self.path, {'version': 1, 'enabled': self.enabled, 'locks': sorted(self.locks)})
        except OSError as exc:
            self.fault = 'ownership storage: ' + str(exc)
            raise

    def command(self, operation, source=None):
        if self.fault:
            raise ValueError(self.fault)
        if operation in ('show-start', 'show-end'):
            self.validate_source(source)
            if operation == 'show-start':
                if len(self.locks) >= 128 and source not in self.locks:
                    raise ValueError('too many show sources')
                self.locks.add(source)
            else:
                self.locks.discard(source)
        elif operation in ('ambient-enable', 'ambient-disable'):
            if operation == 'ambient-enable' and self.status()['show_owned']:
                raise PermissionError('show owns managed targets')
            self.enabled = operation == 'ambient-enable'
        else:
            raise ValueError('unknown ownership operation')
        self.epoch += 1
        self.clear_since = None
        self.persist()
        return self.status()

    def observe(self, sources):
        now = self.clock()
        # A lost observer invalidates a quiet period even if its next state is idle.
        if self.seen_ns is None or now - self.seen_ns > self.timeout_ns:
            self.clear_since = None
        sources = frozenset(sources)
        if sources != self.observed:
            self.clear_since = None
            self.epoch += 1
        self.observed, self.seen_ns = sources, now
        if sources or self.locks:
            self.clear_since = None
        elif self.clear_since is None:
            self.clear_since = now

    def status(self):
        now = self.clock()
        healthy = self.seen_ns is not None and 0 <= now - self.seen_ns <= self.timeout_ns
        sources = sorted(self.locks | set(self.observed or ()))
        fault = self.fault or self.transport_fault
        uncertain = not healthy or fault is not None
        if uncertain:
            self.clear_since = None
        quiet = healthy and self.clear_since is not None and now - self.clear_since >= self.quiet_ns
        allowed = self.enabled and not sources and not uncertain and quiet
        return {'version': 1, 'enabled': self.enabled, 'allowed': allowed,
                'show_owned': bool(sources) or uncertain, 'sources': sources,
                'observer_healthy': healthy, 'quiet': quiet, 'fault': fault,
                'epoch': self.epoch}
