from scripts.evaluate_scifact_external import covered_length


def test_rationale_coverage_does_not_double_count_overlapping_quotes():
    assert covered_length([(0,10),(5,20),(5,20)],3,18)==15
    assert covered_length([(0,3),(8,20)],2,10)==3
    assert covered_length([],0,10)==0
    assert covered_length([(0,3)],5,10)==0
