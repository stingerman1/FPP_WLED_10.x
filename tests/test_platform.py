import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('check_platform', Path(__file__).resolve().parents[1] / 'scripts/check-platform.py')
platform_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(platform_check)


class PlatformTests(unittest.TestCase):
    def test_64_bit_kernel_does_not_hide_32_bit_userspace(self):
        header = b'\x7fELF\x02\x01' + bytes(12) + (183).to_bytes(2, 'little')
        platform_check.validate_architecture('aarch64', 64, '#define __SIZEOF_POINTER__ 8', header)
        for bits, pointer in ((32, 4), (32, 8), (64, 4)):
            with self.assertRaisesRegex(ValueError, '32-bit userspace'):
                platform_check.validate_architecture('aarch64', bits, f'#define __SIZEOF_POINTER__ {pointer}', header)
        for bad_header in (header[:4] + b'\x01' + header[5:], header[:18] + (62).to_bytes(2, 'little'), b'not ELF'):
            with self.assertRaises(ValueError):
                platform_check.validate_architecture('aarch64', 64, '#define __SIZEOF_POINTER__ 8', bad_header)
