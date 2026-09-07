"""Preview and atomically merge portable WLED preset catalogs."""
from copy import deepcopy
import hashlib
import json

from .storage import save_json


def import_presets(state, request):
    if set(request) - {'presets', 'preview', 'revision'}:
        raise ValueError('import accepts presets, preview and revision only')
    preview = request.get('preview', True)
    if type(preview) is not bool:
        raise ValueError('preview must be boolean')
    incoming = request.get('presets')
    if not isinstance(incoming, dict) or not 1 <= len(incoming) <= 251:
        raise ValueError('presets must be an object containing 1..250 preset IDs, plus optional 0 placeholder')
    revision = hashlib.sha256(json.dumps([state.presets, incoming], sort_keys=True,
                                        allow_nan=False).encode()).hexdigest()
    if not preview and request.get('revision') != revision:
        raise ValueError('preset catalog or import changed; preview again before saving')
    candidate = deepcopy(state.presets)
    report = {'valid': True, 'saved': False, 'revision': revision, 'entries': [],
              'added': [], 'overwritten': [], 'errors': []}
    for key, original in incoming.items():
        entry = {'id': key, 'translations': [], 'errors': []}
        report['entries'].append(entry)
        if key == '0' and original == {}:
            entry['translations'].append('Ignored WLED empty slot 0')
            continue
        try:
            if not isinstance(key, str) or not key.isascii() or not key.isdigit() or not 1 <= int(key) <= 250 or str(int(key)) != key:
                raise ValueError('preset ID must be a canonical decimal string from 1 to 250')
            if not isinstance(original, dict):
                raise ValueError('preset must be an object')
            preset = deepcopy(original)
            name = preset.setdefault('n', 'Preset ' + key)
            if not isinstance(name, str) or len(name) > 128 or any(c in name for c in '<>&'):
                raise ValueError('preset name must be at most 128 characters without HTML markup')
            label = preset.get('ql', '')
            if not isinstance(label, str) or len(label.encode()) > 8 or any(c in label for c in '<>&'):
                raise ValueError('quick-load label must be at most 8 UTF-8 bytes without HTML markup')
            if 'playlist' in preset:
                if set(preset) - {'playlist', 'n', 'ql'}:
                    raise ValueError('playlist preset supports playlist, n and ql only')
            else:
                if {'ps', 'pl', 'v', 'time', 'tt'} & set(preset):
                    raise ValueError('preset references and transient API fields cannot be imported')
                state.merge(preset)  # validate before dropping only neutral defaults
                for field in ('bs', 'ledmap'):
                    if field in preset:
                        del preset[field]
                        entry['translations'].append('Removed neutral ' + field)
                segments = preset.get('seg', [])
                segments = [segments] if isinstance(segments, dict) else segments
                for index, segment in enumerate(segments):
                    for field in ('cct', 'set', 'si', 'bm'):
                        if field in segment:
                            del segment[field]
                            entry['translations'].append(f'Removed neutral seg[{index}].{field}')
            candidate[key] = preset
            report['overwritten' if key in state.presets else 'added'].append(key)
        except (ValueError, TypeError) as exc:
            entry['errors'].append(str(exc))
    # Resolve references after loading the complete batch, regardless of file order.
    for key, preset in candidate.items():
        if isinstance(preset, dict) and 'playlist' in preset:
            try:
                state.validate_playlist(preset['playlist'], candidate)
            except (ValueError, TypeError) as exc:
                report['errors'].append(f'Playlist {key}: {exc}')
    if state.playlist:
        try:
            state.validate_playlist(state.playlist, candidate)
            if state.return_preset:
                target = candidate[str(state.return_preset)]
                if 'playlist' in target:
                    raise ValueError('return preset must remain a lighting preset')
                state.merge(target)
        except (ValueError, TypeError, KeyError) as exc:
            report['errors'].append(f'Active playlist: {exc}')
    report['valid'] = not report['errors'] and not any(e['errors'] for e in report['entries'])
    if not preview:
        if not report['valid']:
            raise ValueError('import contains incompatible presets; preview for details; nothing saved')
        save_json(state.directory / 'presets.json', candidate)
        state.presets = candidate
        report['saved'] = True
    return report
