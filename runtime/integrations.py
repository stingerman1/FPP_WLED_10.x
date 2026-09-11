"""Optional network integrations. Commands always pass through Controller.post."""
import json
import logging
import queue
import threading
from .storage import read_json


def ha_command(payload, effects):
    if not isinstance(payload, dict) or set(payload) - {'state', 'brightness', 'color', 'effect', 'transition', 'color_mode'}:
        raise ValueError('unsupported Home Assistant command')
    result = {}
    if 'state' in payload:
        if payload['state'] not in ('ON', 'OFF'):
            raise ValueError('state must be ON or OFF')
        result['on'] = payload['state'] == 'ON'
    if 'brightness' in payload:
        result['bri'] = payload['brightness']
    if 'transition' in payload:
        value = payload['transition']
        if type(value) not in (int, float) or not 0 <= value <= 65.5:
            raise ValueError('transition must be 0..65.5 seconds')
        result['transition'] = round(value * 10)
    seg = {}
    if 'color' in payload:
        color = payload['color']
        if not isinstance(color, dict) or set(color) - {'r', 'g', 'b', 'w'}:
            raise ValueError('RGB or RGBW color is required')
        seg['col'] = [[color.get(key, 0) for key in ('r', 'g', 'b', 'w')]]
    if 'effect' in payload:
        try:
            seg['fx'] = effects.index(payload['effect'])
        except ValueError:
            raise ValueError('unknown effect') from None
    if seg:
        result['seg'] = seg
    return result


class MQTT:
    def __init__(self, controller):
        import paho.mqtt.client as mqtt
        self.controller = controller
        config = controller.config['mqtt']
        self.topic = config.get('topic', 'wled/fpp')
        self.uid = config.get('id', 'fpp_wled')
        self.messages = queue.Queue(maxsize=32)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.uid)
        self.client.max_queued_messages_set(32)
        self.client.reconnect_delay_set(1, 30)
        self.client.will_set(self.topic + '/status', 'offline', retain=True)
        secret = read_json(controller.directory / 'mqtt-secret.json', {})
        if secret.get('username'):
            self.client.username_pw_set(secret['username'], secret.get('password'))
        if config.get('tls', False):
            self.client.tls_set()
        self.client.on_connect = self.connected
        self.client.on_message = self.message
        self.client.connect_async(config['host'], config.get('port', 1883), keepalive=30)
        self.client.loop_start()
        self.last = None

    def connected(self, client, userdata, flags, reason, properties):
        if reason != 0:
            return
        client.subscribe([(self.topic + '/api', 0), (self.topic + '/ha/set', 0), (self.topic, 0)])
        client.publish(self.topic + '/status', 'online', retain=True)
        rgbw = self.controller.config['pixels']['channels'] == 4
        discovery = {'name': 'WLED ambient', 'unique_id': self.uid,
                     'schema': 'json', 'command_topic': self.topic + '/ha/set',
                     'state_topic': self.topic + '/ha/state', 'brightness': True,
                     'supported_color_modes': ['rgbw' if rgbw else 'rgb'],
                     'effect': True, 'effect_list': [name for i, name in enumerate(self.controller.engine.effects)
                                                    if i not in self.controller.engine.unsupported],
                     'availability_topic': self.topic + '/status',
                     'device': {'identifiers': [self.uid], 'name': 'WLED for FPP',
                                'manufacturer': 'WLED / stingerman1', 'model': 'Linux alpha', 'sw_version': '16.0.1-linux-alpha.2'}}
        client.publish('homeassistant/light/' + self.uid + '/config', json.dumps(discovery), retain=True)
        self.last = None

    def message(self, client, userdata, message):
        # Retained commands must not unexpectedly replay after a show or restart.
        if message.retain or len(message.payload) > 65536:
            return
        try:
            self.messages.put_nowait((message.topic, bytes(message.payload)))
        except queue.Full:
            client.publish(self.topic + '/error', 'command queue full')

    def tick(self):
        for _ in range(8):
            try:
                topic, payload = self.messages.get_nowait()
            except queue.Empty:
                break
            try:
                if topic.endswith('/ha/set'):
                    patch = ha_command(json.loads(payload), self.controller.engine.effects)
                elif topic == self.topic:
                    value = payload.decode().strip()
                    patch = {'on': value == 'ON'} if value in ('ON', 'OFF') else {'on': True, 'bri': int(value)}
                else:
                    patch = json.loads(payload)
                self.controller.post('/json/state', patch)
            except (ValueError, KeyError, TypeError, PermissionError) as exc:
                self.client.publish(self.topic + '/error', str(exc))
        with self.controller.lock:
            state = self.controller.state.public()
            gate = self.controller.ownership.status()
            segment = state['seg'][state['mainseg']]
            colors = segment['col'][0] + [0] * (4 - len(segment['col'][0]))
            ha = {'state': 'ON' if state['on'] else 'OFF', 'brightness': state['bri'],
                  'color_mode': 'rgbw' if self.controller.config['pixels']['channels'] == 4 else 'rgb',
                  'color': dict(zip(('r', 'g', 'b', 'w'), colors)),
                  'effect': self.controller.engine.effects[segment['fx']]}
            encoded = json.dumps({'state': state, 'ownership': gate})
        if encoded != self.last:
            self.last = encoded
            self.client.publish(self.topic + '/json', encoded, retain=True)
            self.client.publish(self.topic + '/ha/state', json.dumps(ha), retain=True)
            self.client.publish(self.topic + '/g', state['bri'] if state['on'] else 0, retain=True)

    def close(self):
        self.client.publish(self.topic + '/status', 'offline', retain=True)
        self.client.disconnect()
        self.client.loop_stop()
