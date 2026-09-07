#!/usr/bin/env python3
"""Measure Linux rendering only; this is not a Pi/FPP output acceptance test."""
import argparse
import json
import platform
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.engine import Engine

parser = argparse.ArgumentParser()
parser.add_argument('--frames', type=int, default=400)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
if args.frames < 100:
    parser.error('at least 100 frames required')
results = []
for width, height, effect in [(1000, 1, 9), (32, 32, 118)]:
    engine = Engine(ROOT / 'build/libwled_linux.so', {'pixels': {
        'count': width * height, 'channels': 3, 'width': width, 'height': height}})
    if effect in engine.unsupported:
        raise SystemExit('benchmark effect unavailable')
    engine.apply({'on': True, 'bri': 255, 'transition': 0, 'seg': [{
        'start': 0, 'stop': width, 'startY': 0, 'stopY': height, 'fx': effect,
        'sx': 128, 'ix': 128, 'pal': 11, 'col': [[255, 80, 10], [0, 0, 0], [0, 0, 255]]}]})
    samples = []
    for i in range(args.frames + 100):
        started = time.perf_counter_ns()
        engine.render((i + 1) * 25)
        if i >= 100:
            samples.append((time.perf_counter_ns() - started) / 1e6)
    ordered = sorted(samples)
    results.append({'width': width, 'height': height, 'pixels': width * height,
                    'effect_id': effect, 'effect': engine.effects[effect],
                    'frames': args.frames, 'simulated_fps': 40,
                    'mean_ms': statistics.mean(samples), 'p95_ms': ordered[int(len(ordered) * .95)],
                    'max_ms': max(samples)})
report = {'scope': 'renderer only; excludes FPP, networking, physical output and thermal soak',
          'platform': platform.platform(), 'machine': platform.machine(), 'results': results}
encoded = json.dumps(report, indent=2) + '\n'
print(encoded, end='')
if args.output:
    args.output.write_text(encoded)
