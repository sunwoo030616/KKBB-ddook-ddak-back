import unittest
from selection import select
class SelectionTest(unittest.TestCase):
 def test_threshold_budget_and_e5_tie_order(self):
  chosen,p=select(['a','b','c','d'],{k:{'type':'noul','noul':v} for k,v in [('a',.8),('b',.9),('c',.8),('d',.69)]},max_menus=2);self.assertEqual(chosen,['b','a'])
 def test_missing_or_invalid_probability_is_not_silently_selected(self):
  for value in [None,float('nan'),True,1.1]:
   with self.assertRaises(ValueError):select(['a'],{'a':{'type':'noul','noul':value}})
 def test_all_uncertain_returns_no_menu(self):
  self.assertEqual(select(['a'],{'a':{'type':'noul','noul':.6}})[0],[])
if __name__=='__main__':unittest.main()
