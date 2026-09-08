import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('verify_abi', Path(__file__).resolve().parents[1] / 'scripts/verify-abi.py')
abi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abi)


class ABITests(unittest.TestCase):
    def test_daemon_library_is_inspected_without_loading_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'fppversion_defines.h').write_text('#define FPP_MAJOR_VERSION 10\n')
            source = root / 'fixture.cpp'
            # dlopen would fail on the unresolved daemon global or run abort().
            prefix = 'extern "C" { extern int runMainFPPDLoop; int host(){return runMainFPPDLoop;}\n'
            prefix += '__attribute__((constructor)) void init(){__builtin_trap();}\n'
            def build(target, api):
                source.write_text(prefix + '\n'.join('unsigned ' + name + '(){return ' + str(value) + ';}'
                    for name, value in zip(abi.SYMBOLS, (api, 48, 720, 64, 256))) + '\n}')
                subprocess.run(['g++', '-O2', '-fPIC', '-shared', str(source), '-o', str(target)], check=True)
            build(root / 'libfpp.so', 6)
            build(root / 'plugin.so', 6)
            self.assertEqual(abi.verify(root, root / 'plugin.so')['fingerprints']['fpp_plugin_api_version'], 6)
            build(root / 'plugin.so', 5)
            with self.assertRaisesRegex(ValueError, 'ABI mismatch'):
                abi.verify(root, root / 'plugin.so')

    def test_arm_constants_and_unknown_code_fail_closed(self):
        symbol = 'fpp_plugin_api_version'
        code = '0000000000001230 <' + symbol + '>:\n 1230: mov w0, #0x6 // #6\n 1234: ret\n'
        self.assertEqual(abi.constant_return(code, symbol), 6)
        for bad in (code.replace('mov w0, #0x6', 'ldr w0, [x0]'), code.replace('ret', 'bl 4567'), ''):
            with self.assertRaises(ValueError):
                abi.constant_return(bad, symbol)
