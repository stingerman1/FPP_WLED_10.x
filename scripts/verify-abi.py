#!/usr/bin/env python3
"""Compare compiled ABI constants without loading daemon-dependent libraries.

FPP's loader performs the final symbol resolution and ABI gate in fppd. Loading
libfpp in Python is invalid: it requires globals supplied by the fppd executable.
These five fingerprint functions are constant returns on supported optimized
AArch64/x86-64 builds. Unknown instruction sequences fail closed.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

SYMBOLS = ['fpp_plugin_api_version', 'fpp_logger_instance_abi_size', 'fpp_logger_abi_span',
           'fpp_command_abi_size', 'fpp_command_arg_abi_size']


def constant_return(disassembly, symbol):
    match = re.search(r'^[0-9a-f]+ <' + re.escape(symbol) + r'>:\n(.*?)(?=\n\n|\Z)', disassembly, re.M | re.S)
    if not match:
        raise ValueError('Missing compiled ABI fingerprint: ' + symbol)
    instructions = []
    for line in match[1].splitlines():
        instruction = re.fullmatch(r'\s*[0-9a-f]+:\s+(.+)', line)
        if not instruction:
            raise ValueError('Unrecognized disassembly for ' + symbol)
        text = instruction[1].split('//', 1)[0].strip()
        if text in ('endbr64', 'bti c', 'nop'):
            continue
        instructions.append(text)
    if len(instructions) != 2 or instructions[1] not in ('ret', 'retq'):
        raise ValueError('Nonconstant ABI fingerprint: ' + symbol)
    value = re.fullmatch(r'mov\s+\$(0x[0-9a-f]+|[0-9]+),%eax', instructions[0])
    if value is None:
        value = re.fullmatch(r'mov(?:z)?\s+w0,\s*#(0x[0-9a-f]+|[0-9]+)', instructions[0])
    if value is None:
        raise ValueError('Unsupported ABI constant encoding: ' + symbol)
    return int(value[1], 0)


def fingerprints(library):
    values = {}
    for symbol in SYMBOLS:
        output = subprocess.check_output(['objdump', '-d', '--no-show-raw-insn',
                                          '--disassemble=' + symbol, str(library)], text=True)
        values[symbol] = constant_return(output, symbol)
    return values


def verify(fpp_src, candidate):
    definitions = (fpp_src / 'fppversion_defines.h').read_text()
    major = re.search(r'^#define FPP_MAJOR_VERSION (\d+)\s*$', definitions, re.M)
    if major is None or major[1] != '10':
        raise ValueError('Only installed FPP 10 headers are supported')
    expected, actual = fingerprints(fpp_src / 'libfpp.so'), fingerprints(candidate)
    for symbol in SYMBOLS:
        if expected[symbol] != actual[symbol]:
            raise ValueError(f'ABI mismatch for {symbol}: installed={expected[symbol]}, plugin={actual[symbol]}')
    if actual['fpp_plugin_api_version'] != 6:
        raise ValueError('Only FPP plugin ABI 6 is validated by this adapter')
    return {'fpp_major': major[1], 'fingerprints': actual,
            'method': 'compiled constants; final load validation is performed by FPP'}


if __name__ == '__main__':
    try:
        print(json.dumps(verify(Path(sys.argv[1]), Path(sys.argv[2]).resolve()), indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit('ABI verification failed: ' + str(exc))
