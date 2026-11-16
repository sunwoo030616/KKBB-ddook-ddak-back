import unittest
from metrics import case_metrics,summary
class V2MetricsTests(unittest.TestCase):
 def test_negative_empty_result_not_counted_as_positive_recall(self):
  rows=[dict(expected_ids=[],expected_status='no_match',selected_ids=[],status='no_match',http_ms=1),dict(expected_ids=['a','b'],expected_status='ready',selected_ids=['a'],status='ready',http_ms=1)]
  s=summary(rows);self.assertEqual(s['status_and_menu_accuracy'],.5);self.assertEqual(s['macro_recall'],.5);self.assertEqual(s['positive_cases'],1)
 def test_wrong_clarification_on_negative_still_fails_status(self):
  s=case_metrics(dict(expected_ids=[],expected_status='no_match',selected_ids=[],status='needs_clarification'))
  self.assertTrue(s['menu_exact']);self.assertFalse(s['status_and_menu_exact'])
 def test_errors_not_dropped_and_actual_calls_all_counted(self):
  rows=[dict(expected_ids=['a'],expected_status='ready',status='error',error='HTTP 502',http_ms=1,calls=[{'usage':{'input_tokens':10,'output_tokens':2}}])]
  s=summary(rows);self.assertEqual(s['menu_exact_accuracy'],0);self.assertEqual(s['macro_recall'],0);self.assertEqual(s['tokens']['input']['sum'],10)
if __name__=='__main__':unittest.main()
