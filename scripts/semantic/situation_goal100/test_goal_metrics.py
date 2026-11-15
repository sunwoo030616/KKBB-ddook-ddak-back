"""Test alternatives, prohibited extras, incomplete outcomes and errors without external calls."""
import unittest,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'situation_v3'))
from goal_metrics import case_metrics,summary
CASES=json.loads(Path(__file__).with_name('cases.json').read_text())
class AcceptedSetsTest(unittest.TestCase):
 def row(self,family,ids,status='ready',error=None):
  d=dict(next(r for r in CASES if r['family_id']==family),selected_ids=ids,status=status,http_ms=1,calls=[])
  if error:d['error']=error
  return d
 def test_approved_payment_alternative_is_not_canonical_but_is_correct(self):
  s=case_metrics(self.row('S01',['kb_menu_0323','kb_menu_0608','kb_menu_0602']))
  self.assertTrue(s['status_and_menu_exact']);self.assertFalse(s['canonical_menu_exact']);self.assertEqual(s['required_outcome_recall'],1)
 def test_approved_card_and_roaming_can_accompany_one_payment_channel(self):
  self.assertTrue(case_metrics(self.row('S01',['kb_menu_0323','kb_menu_0608','kb_menu_0603','kb_menu_0602','kb_menu_0612']))['status_and_menu_exact'])
 def test_missing_insurance_and_unrelated_loan_are_not_passes(self):
  self.assertFalse(case_metrics(self.row('S01',['kb_menu_0323','kb_menu_0413']))['status_and_menu_exact'])
  self.assertFalse(case_metrics(self.row('S01',['kb_menu_0323','kb_menu_0413','kb_menu_0602','kb_menu_0030']))['status_and_menu_exact'])
 def test_completed_travel_tasks_are_not_allowed_extras(self):
  self.assertFalse(case_metrics(self.row('S08',['kb_menu_0385','kb_menu_0612','kb_menu_0323']))['status_and_menu_exact'])
 def test_error_is_failure_even_if_ids_look_correct(self):
  self.assertFalse(case_metrics(self.row('S05',['kb_menu_0597','kb_menu_0596'],error='HTTP 502'))['status_and_menu_exact'])
 def test_two_support_options_are_preapproved(self):
  self.assertTrue(case_metrics(self.row('S09',['kb_menu_0018','kb_menu_0017','kb_menu_0019']))['status_and_menu_exact'])
 def test_summary_separates_canonical_only_metrics(self):
  d=summary([self.row('S01',['kb_menu_0323','kb_menu_0608','kb_menu_0602'])]);self.assertEqual(d['status_and_menu_correct'],1);self.assertIn('canonical_only_metrics',d);self.assertNotIn('macro_f1',d)
if __name__=='__main__':unittest.main()
