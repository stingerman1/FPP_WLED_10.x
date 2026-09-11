from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import test_runtime
from runtime import backup
from runtime.storage import read_json, save_json

class BackupTests(unittest.TestCase):
    setUp=test_runtime.RuntimeTests.setUp
    enable=test_runtime.RuntimeTests.enable
    idle=test_runtime.RuntimeTests.idle

    def test_roundtrip_and_locks_credentials(self):
        self.enable()
        save_json(self.directory/'auth.json',{'token':'test-secret'})
        save_json(self.directory/'mqtt-secret.json',{'username':'qa','password':'test-secret'})
        self.control.post('/json/state',{'psave':1,'n':'Round trip'})
        bundle=self.control.get('/api/backup')
        self.assertNotIn('test-secret',json.dumps(bundle))
        bundle['ownership']['locks']=['backup:show']
        report=self.control.post('/api/restore',{'backup':bundle,'preview':True})
        self.assertTrue(report['valid'])
        self.control.post('/api/restore',{'backup':bundle,'preview':False,'revision':report['revision']})
        self.assertTrue(self.control.get('/api/config/status')['restart_required'])
        save_json(self.directory/'ownership.json',{'version':1,'enabled':True,'locks':['new:show']})
        backup.apply_pending(self.directory)
        ownership=read_json(self.directory/'ownership.json',{})
        self.assertFalse(ownership['enabled'])
        self.assertEqual(ownership['locks'],['backup:show','new:show'])
        self.assertEqual(read_json(self.directory/'presets.json',{})['1']['n'],'Round trip')
        self.assertEqual(read_json(self.directory/'auth.json',{})['token'],'test-secret')
        self.assertFalse((self.directory/'restore-pending.json').exists())

    def test_interrupted_restore_replays(self):
        self.enable();bundle=backup.export(self.control)
        backup.stage(self.control,bundle,backup.digest(bundle))
        actual=backup.save_json
        def fail(path,value):
            if path.name=='native-state.json':raise OSError('simulated interruption')
            actual(path,value)
        with patch('runtime.backup.save_json',side_effect=fail),self.assertRaises(OSError):backup.apply_pending(self.directory)
        self.assertTrue((self.directory/'restore-pending.json').exists())
        backup.apply_pending(self.directory)
        self.assertFalse((self.directory/'restore-pending.json').exists())

    def test_reject_path_injection_invalid_geometry_and_show(self):
        self.enable();bundle=backup.export(self.control)
        invalid=deepcopy(bundle);invalid['files']['../auth.json']={}
        with self.assertRaises(ValueError):backup.inspect(invalid)
        invalid=deepcopy(bundle);invalid['files']['config.json']['pixels']['count']=0
        with self.assertRaises(ValueError):backup.preview(invalid,self.control.engine.lib._name)
        self.control.post('/api/command',{'operation':'show-start','source':'qa:show'})
        with self.assertRaises(PermissionError):backup.stage(self.control,bundle,backup.digest(bundle))

    def test_mqtt_credentials_not_public_and_unrelated_config_preserved(self):
        self.enable()
        config={'enabled':True,'host':'localhost','port':1883,'id':'qa','topic':'wled/qa','tls':False}
        self.control.post('/api/mqtt',{'config':config,'credentials':'replace','username':'qa','password':'secret-qa'})
        self.assertNotIn('secret-qa',json.dumps(self.control.get('/api/mqtt')))
        saved=self.control.get('/api/config/status')['saved']
        self.assertEqual(saved['pixels'],self.control.config['pixels'])
        self.assertEqual(saved['mqtt'],config)
        self.assertTrue(self.control.configuration_dirty)
