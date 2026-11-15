import unittest
import numpy as np
from set_selection import build_choice,decode,role,shortlist
from retrieval import normalize,merge,LexicalIndex
class AlgorithmTest(unittest.TestCase):
 def test_retrieval_preserves_original_and_has_no_fixed_menu_mapping(self):
  self.assertEqual(merge(['a','b'],['c','a'],['d','b'],4),['a','b','c','d']);self.assertIn('자동차',normalize('자가용을 처분'))
 def test_set_candidates_are_real_unique_and_bounded(self):
  menus={str(i):{'name':'조회'+str(i),'description':'현재 정보','select_when':['확인']} for i in range(10)};payload,mapping=build_choice('현재 상황',list(menus),menus,'policy')
  self.assertEqual(len(mapping),120);self.assertEqual(len(payload['questions']['menu_set']['criteria']),122);self.assertTrue(all(len(x)==3 and len(set(x))==3 for x in mapping.values()))
  selected,status,c=decode({'answers':{'menu_set':{'type':'choice','choice':'set_1','confidence':.1}}},mapping);self.assertEqual(len(selected),3);self.assertEqual(status,'ready')
 def test_unknown_choice_and_nonfinite_confidence_are_rejected(self):
  for choice,conf in [('invented',.9),('none',float('nan'))]:
   with self.assertRaises(ValueError):decode({'answers':{'menu_set':{'type':'choice','choice':choice,'confidence':conf}}},{})
 def test_actual_vector_diversity_and_threshold(self):
  vec=np.array([[1.,0.],[.99,.01],[0.,1.]]);out=shortlist(['a','b','c'],{'a':.9,'b':.89,'c':.8},vec,{'a':0,'b':1,'c':2},2);self.assertEqual(out,['a','c'])
 def test_empty_pool_abstention(self):
  payload,m=build_choice('불명',[],{},'policy');self.assertEqual(m,{});self.assertEqual(decode({'answers':{'menu_set':{'type':'choice','choice':'unsure','confidence':.8}}},m)[1],'needs_clarification')
if __name__=='__main__':unittest.main()
