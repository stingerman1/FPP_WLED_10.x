"""Translate FPP channel models / strings to a WLED canvas without changing FPP.

Horizontal/vertical model wiring follows PixelOverlayModel.cpp. Custom/3D models
are rejected explicitly until their layouts can be represented without guessing.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from .config import validate, integer
from .storage import read_json


def sources():
    root = Path(os.environ.get('MEDIADIR', '/home/fpp/media')) / 'config'
    models = read_json(root / 'model-overlays.json', {}).get('models', [])
    strings = read_json(root / 'co-pixelStrings.json', {}).get('channelOutputs', [])
    records, warnings = [], []
    for model in models:
        if model.get('Type') != 'Channel':
            continue
        records.append({'kind':'model', 'name':model.get('Name', 'Unnamed model'), 'source':model})
    for output in strings:
        if not output.get('enabled', False):
            continue
        for port in output.get('outputs', []):
            for key, values in port.items():
                if not key.startswith('virtualStrings') or not isinstance(values, list):
                    continue
                for value in values:
                    if value.get('pixelCount', 0) > 0:
                        records.append({'kind':'string', 'name':value.get('description') or f"Port {port.get('portNumber', '?')}", 'source':value})
    for index, record in enumerate(records):
        record['id'] = index
    if not records:
        warnings.append('No saved channel models or pixel strings were found in FPP. Set up outputs/models in FPP first.')
    return {'items':records, 'warnings':warnings}


def translate(config, records):
    if not records or len(records) > 32:
        raise ValueError('Choose 1 to 32 models or strings.')
    parts = []
    for record in records:
        value, name = record['source'], record['name']
        if not isinstance(name, str) or not name or len(name.encode()) > 128 or any(c in name for c in '<>&'):
            raise ValueError('Rename the FPP item without HTML characters and within 128 UTF-8 bytes: ' + str(name))
        if record['kind'] == 'model':
            channels = integer(value.get('ChannelCountPerNode', 3), 3, 4, 'model channels per pixel')
            length = integer(value.get('ChannelCount'), 3, 64000, 'model channel count')
            if length % channels:
                raise ValueError(name + ': channel count is not a whole number of pixels')
            count = length // channels
            strands = integer(value.get('StrandsPerString') or 1, 1, 255, 'strands per string')
            rows = integer(value.get('StringCount') or 1, 1, 255, 'string count') * strands
            if count % rows:
                raise ValueError(name + ': matrix dimensions do not divide evenly')
            width, height = count // rows, rows
            orientation = value.get('Orientation', 'H')
            if orientation not in ('H','V','horizontal','vertical'):
                raise ValueError(name + ': custom/3D models are not supported by this importer yet')
            vertical = orientation in ('V','vertical')
            if vertical:
                width, height = height, width
            corner = value.get('StartCorner', 'TL')
            if corner not in ('TL','TR','BL','BR'):
                raise ValueError(name + ': unknown start corner')
            pixel_map = []
            for y in range(height):
                for x in range(width):
                    if vertical:
                        out_x = x if corner[1] == 'L' else width-x-1
                        out_y = height-y-1 if (corner[0] == 'T') == bool((x % strands) % 2) else y
                        pixel_map.append(out_x*height+out_y)
                    else:
                        out_x = width-x-1 if (corner[1] == 'L') == bool((y % strands) % 2) else x
                        out_y = y if corner[0] == 'T' else height-y-1
                        pixel_map.append(out_y*width+out_x)
            channel = integer(value.get('StartChannel'), 1, 8388608, 'FPP start channel')
        else:
            order = value.get('colorOrder', 'RGB')
            channels = 4 if 'W' in str(order).upper() else 3
            count = integer(value.get('pixelCount'), 1, 16000, 'string pixel count')
            width, height = count, 1
            # FPP applies grouping, zigzag, reverse and hardware color order.
            channel = integer(value.get('startChannel'), 0, 8388607, 'string start channel') + 1
            if value.get('groupCount', 1) not in (0,1):
                raise ValueError(name + ': grouped hardware strings need a channel model for import')
            pixel_map = list(range(count))
        parts.append(dict(name=name,channels=channels,count=count,width=width,height=height,channel=channel,map=pixel_map))
    if len({p['channels'] for p in parts}) != 1:
        raise ValueError('Mixed RGB and RGBW items need separate canvases; choose one pixel type for this import.')
    strips = all(p['height'] == 1 for p in parts)
    width = sum(p['count'] for p in parts) if strips else max(p['width'] for p in parts)
    height = 1 if strips else sum(p['height'] for p in parts)
    count, physical, x, y = width*height, 0, 0, 0
    if count > 16000 or (height > 1 and (width > 255 or height > 255)):
        raise ValueError('This layout exceeds the current canvas limits (16000 pixels; matrix axes at most 255). Import a smaller selection.')
    mapping, segments, ranges = [-1]*count, [], []
    for part in parts:
        for row in range(part['height']):
            for col in range(part['width']):
                mapping[(y+row)*width+x+col] = physical+part['map'][row*part['width']+col]
        segments.append({'id':len(segments),'n':part['name'],'start':x,'stop':x+part['width'],'startY':y,'stopY':y+part['height'],'sel':True})
        ranges.append({'pixel':physical,'count':part['count'],'channel':part['channel']})
        physical += part['count']
        if strips: x += part['width']
        else: y += part['height']
    result = deepcopy(config)
    result.update(pixels={'count':count,'channels':parts[0]['channels'],'width':width,'height':height},mappings=ranges,ledmap=mapping)
    revision = hashlib.sha256(json.dumps([result['pixels'],ranges,mapping,segments],sort_keys=True).encode()).hexdigest()
    result['imported_layout'] = {'revision':revision,'segments':segments}
    validate(result)
    return {'config':result,'segments':segments,'warnings':['Applying replaces the current segment layout and stops the ambient playlist. Saved presets stay, but presets using the old geometry may need editing. FPP output settings are unchanged.']}
