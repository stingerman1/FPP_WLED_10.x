import json
from pathlib import Path
import unittest
import subprocess
import sys
from runtime.engine import Engine

ROOT = Path(__file__).resolve().parents[1]


class RenderingTests(unittest.TestCase):
    def test_repeatable_fresh_process_effect_frames(self):
        script = '''
import hashlib
from runtime.engine import Engine
e = Engine('build/libwled_linux.so', {'pixels': {'count': 100, 'channels': 3}})
e.apply({'on': True, 'bri': 255, 'transition': 0, 'seg': [{'start': 0, 'stop': 100,
    'fx': 9, 'sx': 128, 'ix': 128, 'pal': 11, 'col': [[255, 0, 0]]}]})
print(hashlib.sha256(b''.join(e.render(ms) for ms in range(25, 5025, 25))).hexdigest())
'''
        first = subprocess.check_output([sys.executable, '-c', script], cwd=ROOT)
        second = subprocess.check_output([sys.executable, '-c', script], cwd=ROOT)
        self.assertEqual(first, second)

    def test_mapping_reverses_distinct_segment_colors(self):
        cfg = {'pixels': {'count': 4, 'channels': 3}, 'ledmap': [3, 2, 1, 0]}
        engine = Engine(ROOT / 'build/libwled_linux.so', cfg)
        engine.apply({'on': True, 'bri': 255, 'transition': 0, 'seg': [
            {'start': 0, 'stop': 2, 'fx': 0, 'sx': 128, 'ix': 128, 'pal': 0, 'col': [[255, 0, 0]]},
            {'start': 2, 'stop': 4, 'fx': 0, 'sx': 128, 'ix': 128, 'pal': 0, 'col': [[0, 0, 255]]}]})
        for ms in range(25, 200, 25):
            frame = engine.render(ms)
        self.assertEqual(frame, bytes([0, 0, 255]) * 2 + bytes([255, 0, 0]) * 2)

    def test_solid_rgbw_and_mapping(self):
        cfg = {'pixels': {'count': 12, 'channels': 4}, 'ledmap': list(reversed(range(12)))}
        engine = Engine(ROOT / 'build/libwled_linux.so', cfg)
        engine.apply({'on': True, 'bri': 255, 'transition': 0, 'seg': [
            {'start': 0, 'stop': 12, 'fx': 0, 'sx': 128, 'ix': 128, 'pal': 0, 'col': [[10, 20, 30, 40]]}]})
        for ms in range(25, 200, 25):
            frame = engine.render(ms)
        self.assertEqual(frame, bytes([10, 20, 30, 40]) * 12)

    def test_all_supported_effects_1d_and_2d(self):
        for width, height in [(64, 1), (16, 16)]:
            engine = Engine(ROOT / 'build/libwled_linux.so', {'pixels': {
                'count': width * height, 'channels': 3, 'width': width, 'height': height}})
            for effect in range(len(engine.effects)):
                if effect in engine.unsupported:
                    continue
                with self.subTest(effect=effect, width=width):
                    engine.apply({'on': True, 'bri': 255, 'transition': 0, 'seg': [
                        {'start': 0, 'stop': width, 'startY': 0, 'stopY': height,
                         'fx': effect, 'sx': 128, 'ix': 128, 'pal': 11,
                         'col': [[255, 80, 10], [0, 0, 0], [0, 0, 255]]}]})
                    for ms in range(25, 525, 25):
                        self.assertEqual(len(engine.render(effect * 1000 + ms)), width * height * 3)
            print('Engine:', len(engine.effects), 'IDs;', len(engine.unsupported), 'unsupported')


if __name__ == '__main__':
    unittest.main()
