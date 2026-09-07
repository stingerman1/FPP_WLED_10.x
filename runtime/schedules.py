"""Atomic schedule editing, independent of unrelated pending configuration changes."""
from copy import deepcopy
import hashlib
import json
from .config import validate_schedule
from .storage import read_json, save_json
from .timers import Timers


def disk_config(controller):
    config = read_json(controller.directory / 'config.json', controller.config)
    revision = hashlib.sha256(json.dumps(config, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return deepcopy(config), revision


def public(controller):
    _, revision = disk_config(controller)
    return {'location': deepcopy(controller.timers.location), 'timers': deepcopy(controller.timers.definitions),
            'revision': revision, 'preview': controller.timers.public()}


def update(controller, request):
    if set(request) - {'location', 'timers', 'preview', 'revision'} or 'timers' not in request:
        raise ValueError('schedule request accepts location, timers, preview and revision')
    preview = request.get('preview', True)
    if type(preview) is not bool:
        raise ValueError('preview must be boolean')
    location, definitions = request.get('location'), request['timers']
    validate_schedule(location, definitions)
    for timer in definitions:
        preset = controller.state.presets.get(str(timer['preset']))
        if not isinstance(preset, dict):
            raise ValueError(f'preset {timer["preset"]} does not exist; save or import it first')
        if 'playlist' in preset:
            controller.state.validate_playlist(preset['playlist'])
        else:
            controller.state.merge(preset)
    proposed = Timers(definitions, location, controller.directory / 'timers-fired.json')
    result = proposed.public()
    candidate, revision = disk_config(controller)
    if not preview:
        if request.get('revision') != revision:
            raise ValueError('configuration changed; reload schedules or preview again before saving')
        candidate['timers'] = deepcopy(definitions)
        if location is None:
            candidate.pop('location', None)
        else:
            candidate['location'] = deepcopy(location)
        save_json(controller.directory / 'config.json', candidate)
        controller.config['timers'] = deepcopy(definitions)
        if location is None:
            controller.config.pop('location', None)
        else:
            controller.config['location'] = deepcopy(location)
        controller.timers = proposed
        revision = hashlib.sha256(json.dumps(candidate, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return {'saved': not preview, 'revision': revision, 'preview': result}
