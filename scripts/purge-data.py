#!/usr/bin/env python3
"""Explicitly opted-in uninstall cleanup; only this plugin's named data paths."""
from pathlib import Path
import shutil
import sys


def purge(media):
    root = Path(media).resolve()
    for relative in ('plugindata/FPP_WLED_10.x', 'config/plugin.FPP_WLED_10.x'):
        path = root / relative
        if path.is_symlink() or path.resolve() != path:
            raise ValueError('Refusing redirected plugin data path')
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


if __name__ == '__main__':
    purge(sys.argv[1])
