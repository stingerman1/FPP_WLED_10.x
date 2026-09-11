"""Strict limits protect FPP channel buffers and upstream effect allocations."""
import ipaddress
import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_CHANNELS = 8192 * 1024


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label} must be an integer in {low}..{high}')
    return value


def validate_schedule(location, timers):
    if location is not None:
        if not isinstance(location, dict) or set(location) != {'latitude', 'longitude', 'timezone'}:
            raise ValueError('location requires latitude, longitude and timezone only')
        for key, limit in (('latitude', 90), ('longitude', 180)):
            value = location[key]
            if type(value) not in (float, int) or not -limit <= value <= limit or not math.isfinite(value):
                raise ValueError(f'{key} must be a finite number in {-limit}..{limit}')
        if not isinstance(location['timezone'], str) or not location['timezone']:
            raise ValueError('location timezone must be an IANA name, such as America/Chicago')
        try:
            ZoneInfo(location['timezone'])
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('unknown IANA timezone') from None
    if not isinstance(timers, list) or len(timers) > 64:
        raise ValueError('timers must contain at most 64 entries')
    for timer in timers:
        if not isinstance(timer, dict) or not {'preset', 'days'} <= timer.keys():
            raise ValueError('each timer requires preset and days')
        event = timer.get('event', 'clock')
        if event not in ('clock', 'sunrise', 'sunset'):
            raise ValueError('timer event must be clock, sunrise or sunset')
        fields = {'hour', 'minute'} if event == 'clock' else {'offset'}
        if set(timer) - ({'preset', 'days', 'enabled', 'event'} | fields):
            raise ValueError('unsupported timer fields for ' + event)
        if type(timer.get('enabled', True)) is not bool:
            raise ValueError('timer enabled must be boolean')
        if event == 'clock':
            integer(timer.get('hour'), 0, 23, 'timer hour')
            integer(timer.get('minute'), 0, 59, 'timer minute')
        else:
            if location is None:
                raise ValueError('solar timers require a location and timezone')
            integer(timer.get('offset', 0), -720, 720, 'solar offset minutes')
        integer(timer['preset'], 1, 250, 'timer preset')
        if not isinstance(timer['days'], list) or not timer['days']:
            raise ValueError('timer days must list weekdays (Monday=0)')
        for day in timer['days']:
            integer(day, 0, 6, 'weekday')


def validate(config):
    if not isinstance(config, dict) or config.get('version') != 1:
        raise ValueError('configuration version must be 1')
    p = config.get('pixels')
    if not isinstance(p, dict) or not {'count', 'channels'} <= p.keys():
        raise ValueError('pixels must contain count and channels')
    count = integer(p['count'], 1, 16000, 'pixel count')
    channels = integer(p['channels'], 3, 4, 'channels per pixel')
    width = integer(p.get('width', count), 1, count, 'width')
    height = integer(p.get('height', 1), 1, 255, 'height')
    if width * height != count or (height > 1 and width > 255):
        raise ValueError('matrix dimensions must match count, with each 2D dimension <=255')
    imported = config.get('imported_layout')
    if imported is not None:
        if not isinstance(imported, dict) or not isinstance(imported.get('revision'), str) or len(imported['revision']) != 64:
            raise ValueError('invalid imported layout revision')
        segments = imported.get('segments')
        if not isinstance(segments, list) or not 1 <= len(segments) <= 32:
            raise ValueError('imported layout needs 1 to 32 segments')
        for index, segment in enumerate(segments):
            if not isinstance(segment, dict) or set(segment) != {'id','n','start','stop','startY','stopY','sel'} or segment['id'] != index:
                raise ValueError('invalid imported segment fields')
            if not isinstance(segment['n'], str) or len(segment['n'].encode()) > 128 or any(c in segment['n'] for c in '<>&'):
                raise ValueError('invalid imported segment name')
            if segment['sel'] is not True:
                raise ValueError('imported segments must be selected')
            for first, last, limit in [('start','stop',width),('startY','stopY',height)]:
                integer(segment[first],0,limit-1,first)
                integer(segment[last],1,limit,last)
                if segment[first] >= segment[last]:
                    raise ValueError('imported segment range is empty')
    integer(config.get('fps', 40), 1, 60, 'fps')
    integer(config.get('port', 8787), 1024, 65535, 'port')
    integer(config.get('quiet_ms', 2000), 2000, 60000, 'quiet period')
    integer(config.get('heartbeat_ms', 500), 50, 500, 'heartbeat timeout')
    if not isinstance(config.get('mappings'), list) or len(config['mappings']) > 256:
        raise ValueError('mappings must be a list of at most 256 channel ranges')
    ranges = []
    for m in config['mappings']:
        if not isinstance(m, dict) or not {'channel', 'pixel', 'count'} <= m.keys():
            raise ValueError('each mapping requires channel, pixel and count')
        start = integer(m['channel'], 1, MAX_CHANNELS, 'FPP start channel') - 1
        offset = integer(m['pixel'], 0, count - 1, 'virtual pixel') * channels
        length = integer(m['count'], 1, count, 'mapped pixel count') * channels
        if offset + length > count * channels or start + length > MAX_CHANNELS:
            raise ValueError('mapping is outside the source or FPP channel buffer')
        if any(start < end and start + length > begin for begin, end in ranges):
            raise ValueError('FPP channel mappings overlap')
        ranges.append((start, start + length))
    mapping = config.get('ledmap', list(range(count)))
    if not isinstance(mapping, list) or len(mapping) != count:
        raise ValueError('ledmap must contain one index per virtual pixel')
    for index in mapping:
        integer(index, -1, count - 1, 'ledmap index')
    devices, addresses = config.get('devices', []), set()
    if not isinstance(devices, list) or len(devices) > 64:
        raise ValueError('at most 64 devices are supported')
    ids = set()
    for d in devices:
        if not isinstance(d, dict) or not {'address', 'id', 'mode'} <= d.keys():
            raise ValueError('each device requires address, id and mode')
        if not isinstance(d['id'], str):
            raise ValueError('device id must be a string')
        address = str(ipaddress.IPv4Address(d['address']))
        if address in addresses or d['id'] in ids:
            raise ValueError('duplicate device address or id; only one control mode per device')
        addresses.add(address)
        ids.add(d['id'])
        if d['mode'] not in ('effect', 'sync', 'fpp-stream'):
            raise ValueError('device mode must be effect, sync or fpp-stream')
        integer(d.get('sync_port', 21324), 1024, 65535, 'device sync port')
        integer(d.get('sync_groups', 1), 1, 255, 'device sync groups')
        if not isinstance(d['id'], str) or not 1 <= len(d['id']) <= 64:
            raise ValueError('device id must contain 1..64 characters')
        if not isinstance(d.get('groups', []), list) or not all(isinstance(g, str) for g in d.get('groups', [])):
            raise ValueError('device groups must be strings')
    validate_schedule(config.get('location'), config.get('timers', []))
    mqtt = config.get('mqtt', {})
    if not isinstance(mqtt, dict):
        raise ValueError('mqtt must be an object')
    if 'password' in mqtt or 'username' in mqtt:
        raise ValueError('store MQTT credentials in mqtt-secret.json, not public config')
    if mqtt.get('enabled', False):
        if not isinstance(mqtt.get('host'), str) or not mqtt['host']:
            raise ValueError('MQTT host required')
        integer(mqtt.get('port', 1883), 1, 65535, 'MQTT port')
        for key, default in [('topic', 'wled/fpp'), ('id', 'fpp_wled')]:
            value = mqtt.get(key, default)
            if not isinstance(value, str) or not 1 <= len(value) <= 128 or any(c in value for c in '#+\x00'):
                raise ValueError('invalid MQTT ' + key)
    for key in ('discovery', 'discoverable'):
        if key in config and type(config[key]) is not bool:
            raise ValueError(key + ' must be boolean')
    if not isinstance(config.get('name', 'WLED for FPP'), str) or not 1 <= len(config.get('name', 'WLED for FPP')) <= 32:
        raise ValueError('name must contain 1..32 characters')
    integer(config.get('discovery_http_port', 80), 1, 65535, 'FPP HTTP port')
    udp = config.get('udp', {})
    if not isinstance(udp, dict):
        raise ValueError('udp must be an object')
    if udp.get('enabled', False):
        integer(udp.get('port', 21324), 1024, 65535, 'UDP port')
        integer(udp.get('groups', 1), 1, 255, 'UDP sync group mask')
        for key in ('enabled', 'send', 'receive', 'auto_peers'):
            if key in udp and type(udp[key]) is not bool:
                raise ValueError('udp ' + key + ' must be boolean')
        if udp.get('auto_peers', False) and not config.get('discovery', False):
            raise ValueError('automatic sync peers require discovery')
        if udp.get('port', 21324) == 65506 and config.get('discovery', False):
            raise ValueError('sync port conflicts with WLED discovery port 65506')
        if not isinstance(udp.get('peers', []), list) or len(udp.get('peers', [])) > 64:
            raise ValueError('UDP sync supports at most 64 explicit peer addresses')
        for peer in udp.get('peers', []):
            ipaddress.IPv4Address(peer)
            if peer in addresses:
                raise ValueError('a device cannot use both global UDP sync and an enrolled control mode')
    return config
