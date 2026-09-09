#!/usr/bin/env python3
"""Render only plugin-owned systemd paths; reject unit-file metacharacters."""
from pathlib import Path
import sys


def render(plugin, state, logs, log_file):
    text = (Path(__file__).resolve().parents[1] / 'systemd/fpp-wled.service').read_text()
    for key, value in zip(('PLUGIN_DIR', 'STATE_DIR', 'LOG_DIR', 'LOG_FILE'), (plugin, state, logs, log_file)):
        if not Path(value).is_absolute() or any(c in value for c in '\n\r"\\%'):
            raise ValueError('unsupported systemd path: ' + key)
        text = text.replace('@' + key + '@', value)
    return text


if __name__ == '__main__':
    Path(sys.argv[5]).write_text(render(*sys.argv[1:5]))
