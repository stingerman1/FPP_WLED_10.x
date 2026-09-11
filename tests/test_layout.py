from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from runtime.layout import translate
from runtime.engine import Engine
from runtime.state import State


CONFIG = {'version':1,'port':8787,'pixels':{'count':16,'channels':3},'mappings':[{'pixel':0,'count':16,'channel':1}],'devices':[]}


def model(name='Matrix', **values):
    return {'kind':'model','name':name,'source':{'Type':'Channel','Name':name,'StartChannel':1,
        'ChannelCount':18,'ChannelCountPerNode':3,'StringCount':1,'StrandsPerString':2,
        'Orientation':'H','StartCorner':'TL',**values}}


class LayoutTests(unittest.TestCase):
    def test_four_named_strings(self):
        rows = [{'kind':'string','name':f'String {i+1}','source':{'pixelCount':4,'startChannel':i*12,'colorOrder':'RGB'}} for i in range(4)]
        result = translate(CONFIG, rows)
        self.assertEqual(result['config']['pixels'], {'count':16,'channels':3,'width':16,'height':1})
        self.assertEqual([s['n'] for s in result['segments']], ['String 1','String 2','String 3','String 4'])
        self.assertEqual([s['start'] for s in result['segments']], [0,4,8,12])
        self.assertEqual([m['channel'] for m in result['config']['mappings']], [1,13,25,37])

    def test_serpentine_matrix_corners(self):
        expected = {'TL':[0,1,2,5,4,3], 'TR':[2,1,0,3,4,5],
                    'BL':[3,4,5,2,1,0], 'BR':[5,4,3,0,1,2]}
        for corner, indices in expected.items():
            with self.subTest(corner=corner):
                report = translate(CONFIG,[model(StartCorner=corner)])
                self.assertEqual(report['config']['ledmap'], indices)
                self.assertEqual(report['config']['pixels']['width'],3)
                self.assertEqual(report['config']['pixels']['height'],2)

    def test_vertical_and_padding(self):
        result=translate(CONFIG,[model(Orientation='V'), model('Small',StartChannel=19,ChannelCount=3,StrandsPerString=1)])
        self.assertEqual(result['config']['pixels']['width'],2)
        self.assertEqual(result['config']['pixels']['height'],4)
        self.assertEqual(result['config']['ledmap'],[0,5,1,4,2,3,6,-1])

    def test_reject_ambiguous_layouts(self):
        for records in [[model(),model()], [model(Orientation='C')],
                        [model(),model('White',StartChannel=19,ChannelCount=4,ChannelCountPerNode=4,StrandsPerString=1)]]:
            with self.subTest(records=records), self.assertRaises(ValueError): translate(CONFIG,records)

    def test_import_applies_once_and_keeps_later_edits(self):
        config=translate(CONFIG,[model()])['config']
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            # Old state has a wider range than the new matrix: import must
            # replace it before validation, rather than break runtime startup.
            (path/'state.json').write_text(json.dumps({'seg':[{'id':0,'start':0,'stop':16}]}))
            engine=Engine(Path('build/libwled_linux.so'), config)
            original = (path/'state.json').read_bytes()
            preview = State(path,engine,persist_import=False)
            self.assertEqual(preview.value['seg'][0]['stop'],3)
            self.assertEqual((path/'state.json').read_bytes(),original)
            self.assertFalse((path/'layout-applied.json').exists())
            state=State(path,engine)
            self.assertEqual(state.value['seg'][0]['n'],'Matrix')
            self.assertEqual(state.value['seg'][0]['stop'],3)
            state.set({'seg':{'id':0,'n':'Custom name','fx':1}})
            restarted=State(path,engine)
            self.assertEqual(restarted.value['seg'][0]['n'],'Custom name')
            self.assertEqual(restarted.value['seg'][0]['fx'],1)

