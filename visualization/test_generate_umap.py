import unittest
from generate_umap import validate_trace

class TraceTests(unittest.TestCase):
    def setUp(self):
        self.e={'mode':'e5_jev','catalog_sha256':'hash'}
        self.r={'candidate_ids':['a','b'],'selected':['b'],'status':'selected','jev_calls':1}
    def test_actual_selection(self):
        self.assertEqual(validate_trace(self.e,self.r,'hash',['a','b','c'],2),['b'])
    def test_catalog_mismatch(self):
        with self.assertRaises(ValueError):validate_trace(self.e,self.r,'other',['a','b'],2)
    def test_ranking_mismatch(self):
        with self.assertRaises(ValueError):validate_trace(self.e,self.r,'hash',['b','a'],2)
    def test_selection_outside_candidates(self):
        self.r['selected']=['c']
        with self.assertRaises(ValueError):validate_trace(self.e,self.r,'hash',['a','b'],2)
    def test_unmeasured_selection_rejected(self):
        self.r['jev_calls']=0
        with self.assertRaises(ValueError):validate_trace(self.e,self.r,'hash',['a','b'],2)

if __name__=='__main__':unittest.main()
