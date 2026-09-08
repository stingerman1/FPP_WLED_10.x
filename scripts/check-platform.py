#!/usr/bin/env python3
"""Reject mixed 64-bit-kernel/32-bit-userspace installs before building."""
from pathlib import Path
import platform
import struct
import subprocess
import sys


def validate_architecture(kernel, python_bits, compiler_macros, library_header):
    if kernel != 'aarch64':
        raise ValueError('The plugin requires a Raspberry Pi with a 64-bit ARM kernel.')
    macros = dict(line.removeprefix('#define ').split(maxsplit=1)
                  for line in compiler_macros.splitlines()
                  if line.startswith('#define ') and len(line.removeprefix('#define ').split(maxsplit=1)) == 2)
    if python_bits != 64 or macros.get('__SIZEOF_POINTER__') != '8':
        raise ValueError('32-bit userspace/toolchain detected. This plugin requires 64-bit FPP userspace, Python and compiler; a 64-bit kernel alone is not sufficient. Reinstalling the plugin cannot convert the OS.')
    if len(library_header) < 20 or library_header[:4] != b'\x7fELF':
        raise ValueError('Installed libfpp.so is not a valid ELF library.')
    if library_header[4] != 2 or library_header[5] != 1 or int.from_bytes(library_header[18:20], 'little') != 183:
        raise ValueError('Installed libfpp.so must be 64-bit ARM (AArch64). The plugin cannot load into 32-bit FPP.')


def main():
    try:
        macros = subprocess.check_output(['g++', '-dM', '-E', '-x', 'c++', '/dev/null'], text=True)
        with (Path(sys.argv[1]) / 'libfpp.so').open('rb') as library:
            header = library.read(20)
        validate_architecture(platform.machine(), struct.calcsize('P') * 8, macros, header)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit('Platform check failed: ' + str(exc))


if __name__ == '__main__':
    main()
