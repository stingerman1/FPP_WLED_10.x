import unittest
from runtime.layout import compose
from test_layout import CONFIG, model

class VirtualLayoutTests(unittest.TestCase):
    def setUp(self):
        self.sources=[{'id':i,'kind':'string','name':f'Port {i+1}','source':{'pixelCount':6,'startChannel':i*30,'colorOrder':'RGB'}} for i in range(2)]

    def group(self,pieces,columns=0):
        return {'name':'Across ports','columns':columns,'pieces':[{'source':i,'start':start,'count':count,'reverse':reverse} for i,start,count,reverse in pieces]}

    def test_cross_port_order_and_reverse(self):
        config=compose(CONFIG,self.sources,[self.group([(1,1,3,True),(0,0,2,False)])])['config']
        self.assertEqual(config['ledmap'],[4,3,2,0,1])
        self.assertEqual(config['mappings'],[{'pixel':0,'count':2,'channel':1},{'pixel':2,'count':3,'channel':34}])
        self.assertEqual(config['imported_layout']['segments'][0]['n'],'Across ports')

    def test_matrix_source_and_matrix_destination(self):
        source=model();source['id']=0
        config=compose(CONFIG,[source],[self.group([(0,0,6,False)],3)])['config']
        self.assertEqual(config['ledmap'],[0,1,2,5,4,3])
        self.assertEqual(config['pixels']['height'],2)

    def test_reject_duplicate_and_invalid_ranges(self):
        for pieces in [[(0,0,2,False),(0,1,1,False)],[(0,5,2,False)],[(8,0,1,False)]]:
            with self.subTest(pieces=pieces),self.assertRaises(ValueError):compose(CONFIG,self.sources,[self.group(pieces)])

    def test_reject_mixed_channels_and_partial_rows(self):
        self.sources[1]['source']['colorOrder']='RGBW'
        with self.assertRaises(ValueError):compose(CONFIG,self.sources,[self.group([(0,0,1,False),(1,0,1,False)])])
        with self.assertRaises(ValueError):compose(CONFIG,self.sources,[self.group([(0,0,5,False)],3)])

    def test_source_and_config_not_mutated(self):
        import copy
        before=copy.deepcopy(CONFIG)
        config=compose(CONFIG,self.sources,[self.group([(0,0,3,False)])])['config']
        self.assertEqual(CONFIG,before)
        config['virtual_layout']['groups'][0]['name']='changed'
        self.assertEqual(self.sources[0]['name'],'Port 1')
