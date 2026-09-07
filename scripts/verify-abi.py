#!/usr/bin/env python3
"""Check installed libfpp and the candidate plugin before activating it."""
import ctypes
import json
from pathlib import Path
import sys

fpp_src = Path(sys.argv[1])
candidate = Path(sys.argv[2]).resolve()
fpp = ctypes.CDLL(str(fpp_src / 'libfpp.so'), mode=ctypes.RTLD_GLOBAL)
fpp.getFPPMajorVersion.restype = ctypes.c_char_p
major = fpp.getFPPMajorVersion().decode()
if major != '10':
    raise SystemExit('Only stock FPP 10 is supported; detected ' + major)
plugin = ctypes.CDLL(str(candidate))
symbols = ['fpp_plugin_api_version', 'fpp_logger_instance_abi_size', 'fpp_logger_abi_span',
           'fpp_command_abi_size', 'fpp_command_arg_abi_size']
verified = {}
for symbol in symbols:
    expected, actual = getattr(fpp, symbol)(), getattr(plugin, symbol)()
    if expected != actual:
        raise SystemExit(f'ABI mismatch for {symbol}: installed={expected}, plugin={actual}')
    verified[symbol] = actual
if verified['fpp_plugin_api_version'] != 6:
    raise SystemExit('Only FPP plugin ABI 6 is validated by this adapter')
print(json.dumps({'fpp_major': major, 'fingerprints': verified}, indent=2))
