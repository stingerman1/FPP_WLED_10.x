"""Versioned setup backups with validation in an isolated renderer process.

Restore is journaled and applied only at startup under the runtime flock. An
interrupted application replays the journal before any ambient frame is sent.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from .config import validate
from .ownership import Ownership
from .storage import read_json, save_json

FILES = {'config.json','state.json','presets.json','playlist.json','custom-palettes.json','layout-applied.json','timers-fired.json'}
LIMIT = 8*1024*1024

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()

def export(controller):
    directory=controller.directory
    files={name:read_json(directory/name,None) for name in FILES if (directory/name).exists()}
    files['config.json']=deepcopy(controller.config)
    files['state.json']=deepcopy(controller.state.value)
    files['presets.json']=deepcopy(controller.state.presets)
    return {'format':'fpp-wled-setup','version':1,'files':files,
            'ownership':{'enabled':controller.ownership.enabled,'locks':sorted(controller.ownership.locks)}}

def inspect(bundle):
    if not isinstance(bundle,dict) or set(bundle)!={'format','version','files','ownership'} or bundle['format']!='fpp-wled-setup' or bundle['version']!=1:
        raise ValueError('Choose a WLED for FPP setup backup, version 1.')
    files=bundle['files']
    if not isinstance(files,dict) or set(files)-FILES or not {'config.json','state.json','presets.json'}<=files.keys():
        raise ValueError('Backup contains missing or unsupported files.')
    if len(json.dumps(bundle,allow_nan=False).encode())>LIMIT-1024:
        raise ValueError('Setup backup exceeds the 8 MiB limit.')
    validate(files['config.json'])
    ownership=bundle['ownership']
    if not isinstance(ownership,dict) or set(ownership)!={'enabled','locks'} or type(ownership['enabled']) is not bool or not isinstance(ownership['locks'],list) or len(ownership['locks'])>128:
        raise ValueError('Invalid backup show locks.')
    for source in ownership['locks']:Ownership.validate_source(source)

def preview(bundle, library):
    inspect(bundle)
    # A second ctypes renderer in this process would replace live global buffers.
    with tempfile.TemporaryDirectory(prefix='wled-restore-') as temp:
        root=Path(temp)
        for name,value in bundle['files'].items():save_json(root/name,value)
        result=subprocess.run([sys.executable,'-m','runtime.service','--validate','--state-dir',str(root),'--library',str(library)],
                              cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=20)
        if result.returncode:
            raise ValueError('Backup is not compatible with this runtime: '+(result.stderr.strip().splitlines() or ['validation failed'])[-1])
    return {'valid':True,'revision':digest(bundle),'pixels':bundle['files']['config.json']['pixels']['count'],
            'presets':len(bundle['files']['presets.json']),'locks':bundle['ownership']['locks'],
            'warnings':['Replaces the active setup, lighting state, presets, palettes and timers after Apply setup.',
                        'Browser access and broker credentials stay on this player; they are not in the backup.',
                        'Current and backed-up explicit show locks are combined. Background lighting stays disabled until you enable it.',
                        'Native-device recovery snapshots are cleared. FPP output configuration is not changed.']}

def stage(controller,bundle,revision):
    inspect(bundle)
    if revision!=digest(bundle):raise ValueError('Backup changed. Preview again.')
    if controller.ownership.status()['show_owned']:raise PermissionError('Wait until shows end and FPP status is healthy before restoring.')
    locks=set(controller.ownership.locks)|set(bundle['ownership']['locks'])
    if len(locks)>128:raise ValueError('Too many combined show locks.')
    save_json(controller.directory/'before-restore.json',export(controller))
    save_json(controller.directory/'restore-pending.json',{'revision':revision,'bundle':bundle})
    return {'saved':True,'restart_required':True}

def apply_pending(directory):
    path=directory/'restore-pending.json'
    pending=read_json(path,None)
    if pending is None:return
    bundle=pending['bundle'];inspect(bundle)
    if pending['revision']!=digest(bundle):raise ValueError('Restore journal checksum mismatch')
    current=read_json(directory/'ownership.json',{'version':1,'enabled':False,'locks':[]})
    locks=sorted(set(current['locks'])|set(bundle['ownership']['locks']))
    if len(locks)>128:raise ValueError('Too many combined show locks')
    for source in locks:Ownership.validate_source(source)
    save_json(directory/'ownership.json',{'version':1,'enabled':False,'locks':locks})
    for name in FILES:
        if name in bundle['files']:save_json(directory/name,bundle['files'][name])
        else:(directory/name).unlink(missing_ok=True)
    save_json(directory/'native-state.json',{})
    save_json(directory/'native-snapshots.json',{'version':1,'devices':{}})
    path.unlink()
    if os.name=='posix':
        fd=os.open(directory,os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
