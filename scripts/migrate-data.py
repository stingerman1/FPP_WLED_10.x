#!/usr/bin/env python3
"""Move legacy plugin data within FPP media without changing any JSON contents."""
import os
from pathlib import Path
import sys


def migrate(media):
    media = Path(media).resolve()
    old = media / 'config/plugin.FPP_WLED_10.x'
    new = media / 'plugindata/FPP_WLED_10.x'
    if old.is_symlink() or new.is_symlink():
        raise ValueError('Refusing ambiguous symlinked plugin data')
    new.parent.mkdir(parents=True, exist_ok=True)
    if old.is_dir():
        if new.exists():
            raise ValueError('Both legacy and new data exist; refusing to overwrite either')
        os.rename(old, new)  # Same media volume; rename preserves modes and contents.
    else:
        new.mkdir(exist_ok=True)
    return new


if __name__ == '__main__':
    print(migrate(sys.argv[1]))
