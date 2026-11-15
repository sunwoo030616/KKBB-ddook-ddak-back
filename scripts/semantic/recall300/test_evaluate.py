import unittest
from evaluate import metrics, audit, normalize

class EvaluationTests(unittest.TestCase):
    def test_multigold_macro_not_hit_rate_and_errors_in_denominator(self):
        rows = [{'expected_ids':['a','b'], 'candidate_ids':['a','c','d','e','f','b']},
                {'expected_ids':['z'], 'error':'timeout'}]
        self.assertEqual(metrics(rows)['macro_recall']['5'], .25)
        self.assertEqual(metrics(rows)['hit_rate']['5'], .5)
        self.assertEqual(metrics(rows)['macro_recall']['10'], .5)
        self.assertEqual(metrics(rows)['all_gold_rate']['5'], 0)
    def test_repeated_ids_cannot_inflate_recall(self):
        self.assertEqual(metrics([{'expected_ids':['a','b'], 'candidate_ids':['a']*5}])['macro_recall']['5'], .5)
    def test_invalid_gold_rejected(self):
        cases=[{'case_id':str(i), 'query':'question', 'expected_ids':['missing']} for i in range(300)]
        with self.assertRaises(ValueError):
            audit(cases,[{'id':'a','name':'A'}],[])
    def test_normalization(self):
        self.assertEqual(normalize(' ＡＢＣ! 이체?'), normalize('abc 이체'))

if __name__ == '__main__':
    unittest.main()
