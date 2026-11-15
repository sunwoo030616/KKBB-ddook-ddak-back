import unittest
from metrics import case_metrics,summary
class MultiMenuTests(unittest.TestCase):
 def row(self,gold,pred,status='ready',**kw):return dict(expected_ids=gold,selected_ids=pred,expected_status='ready',status=status,http_ms=1,**kw)
 def test_missing_one_of_three_is_not_exact(self):
  s=case_metrics(self.row(['a','b','c'],['a','b']))
  self.assertFalse(s['menu_exact']);self.assertEqual(s['precision'],1);self.assertEqual(s['recall'],2/3)
 def test_extra_menu_lowers_precision(self):
  s=case_metrics(self.row(['a'],['a','b']))
  self.assertEqual(s['precision'],.5);self.assertEqual(s['recall'],1)
 def test_clarification_is_failure_for_required_bundle(self):
  s=case_metrics(self.row(['a','b','c'],[],'needs_clarification'))
  self.assertFalse(s['menu_exact']);self.assertEqual(s['recall'],0)
 def test_errors_and_missing_usage_are_not_success_or_zero_tokens(self):
  s=summary([self.row(['a'],['a']),self.row(['b'],[],'error',error='HTTP 502')])
  self.assertEqual(s['menu_exact_accuracy'],.5);self.assertEqual(s['macro_recall'],.5)
  self.assertIsNone(s['tokens']['input']['sum'])
 def test_usage_is_summed_across_both_jev_stages(self):
  row=self.row(['a'],['a'],calls=[{'usage':{'input_tokens':10,'output_tokens':2}},{'usage':{'input_tokens':20,'output_tokens':3}}])
  s=summary([row]);self.assertEqual(s['tokens']['input']['sum'],30);self.assertEqual(s['actual_upstream_calls'],2)
if __name__=='__main__':unittest.main()
