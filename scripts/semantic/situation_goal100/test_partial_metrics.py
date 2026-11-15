"""Partial hit must not conceal missing required outcomes or unauthorized extras."""
import unittest,json
from pathlib import Path
from partial_metrics import partial_summary
CASES=json.loads(Path(__file__).with_name('cases.json').read_text())
class PartialMetricsTest(unittest.TestCase):
 def row(self,family,ids,error=None):
  d=dict(next(r for r in CASES if r['family_id']==family),selected_ids=ids)
  if error:d['error']=error
  return d
 def test_one_correct_plus_one_wrong_is_hit_but_half_precision(self):
  s=partial_summary([self.row('S01',['kb_menu_0323','kb_menu_0030'])]);self.assertEqual(s['partial_hit_rate'],1);self.assertEqual(s['menu_level_allowed_precision'],.5);self.assertEqual(s['partial_with_no_disallowed_rate'],0)
 def test_optional_only_hit_does_not_cover_a_required_outcome(self):
  s=partial_summary([self.row('S06',['kb_menu_0260'])]);self.assertEqual(s['partial_hit_rate'],1);self.assertEqual(s['macro_required_outcome_recall'],0)
 def test_errors_do_not_pass_on_stale_ids(self):
  s=partial_summary([self.row('S01',['kb_menu_0323'],error='HTTP 502')]);self.assertEqual(s['partial_hit_rate'],0);self.assertEqual(s['errors'],1)
if __name__=='__main__':unittest.main()
