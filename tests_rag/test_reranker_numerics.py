from threading import Lock

import pytest

from rag_backend.research_models import CrossEncoderReranker


def test_nonfinite_neural_scores_fail_before_component_selection():
    class Model:
        def predict(self,*args,**kwargs):return [float('nan')]
    ranker=object.__new__(CrossEncoderReranker)
    ranker.model=Model();ranker.lock=Lock()
    with pytest.raises(ValueError,match='nonfinite_reranker_score'):
        ranker.score_pairs([('금융 요청','위젯 목적')])
