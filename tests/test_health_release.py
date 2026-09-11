import importlib.util
from pathlib import Path
import sys
import unittest

class HealthReleaseTests(unittest.TestCase):
    def test_release_names_do_not_break_upgrade_or_rollback(self):
        root=Path(__file__).resolve().parents[1]/'scripts'
        sys.path.insert(0,str(root))
        try:
            spec=importlib.util.spec_from_file_location('check_health',root/'check-health.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        finally:sys.path.pop(0)
        for release in ['alpha.1','alpha.2','beta.1']:
            self.assertTrue(module.healthy(200,{'version':1,'release':release,'observer_healthy':False}))
        for status,data in [(503,{}),(200,{}),(200,{'version':2,'release':'alpha.2','observer_healthy':True})]:
            self.assertFalse(module.healthy(status,data))
