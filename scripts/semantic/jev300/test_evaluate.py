import unittest
from evaluate import successful, summarize, validate_response

class FinalSelectionTests(unittest.TestCase):
    def test_single_requires_correct_menu_and_selected_status(self):
        base={'expected_ids':['a'],'selected_ids':['a'],'status':'selected'}
        self.assertTrue(successful(base))
        self.assertFalse(successful({**base,'selected_ids':['b']}))
        self.assertFalse(successful({**base,'status':'needs_clarification'}))
    def test_multi_requires_clarification_not_either_menu(self):
        base={'expected_ids':['a','b'],'selected_ids':[],'status':'needs_clarification'}
        self.assertTrue(successful(base))
        self.assertFalse(successful({**base,'selected_ids':['a'],'status':'selected'}))
        self.assertFalse(successful({**base,'status':'no_match'}))
    def test_errors_and_abstentions_stay_in_denominator(self):
        rows=[{'case_id':'1','expected_ids':['a'],'selected_ids':['a'],'status':'selected','http_ms':1},
              {'case_id':'2','expected_ids':['b'],'status':'error','error':'HTTP 502'},
              {'case_id':'3','expected_ids':['c'],'selected_ids':[],'status':'needs_clarification','http_ms':3}]
        self.assertEqual(summarize(rows)['single_exact_accuracy'],1/3)
        self.assertEqual(summarize(rows)['single_accuracy_among_selected'],1)
        self.assertEqual(summarize(rows)['p95_http_ms'],3)
    def test_candidates_must_match_catalog_and_selection(self):
        ids=[str(i) for i in range(40)]
        body={'catalogSha256':'hash','pipeline':'e5_jev','candidateIds':ids,'menus':[{'id':'x'}], 'jevCalls':1,'status':'selected','confidence':.9}
        with self.assertRaises(ValueError):validate_response(body,'hash',set(ids))
        body['menus']=[{'id':'0'}]
        self.assertEqual(validate_response(body,'hash',set(ids))[1],['0'])

if __name__=='__main__':unittest.main()
