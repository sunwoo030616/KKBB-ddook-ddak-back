from types import SimpleNamespace
import pytest

from rag_backend.train_encoder import validate_pairs


@pytest.fixture
def chunks():
    return [SimpleNamespace(id='a',institution='kb_bank'),SimpleNamespace(id='b',institution='kb_bank'),
            SimpleNamespace(id='c',institution='kb_card')]


def test_normalized_evaluation_query_overlap_is_rejected(chunks):
    rows=[{'query':'예금, 담보 대출?','positive_id':'a','less_direct_id':'b'}]
    with pytest.raises(ValueError,match='duplicate_or_evaluation_query'):
        validate_pairs(rows,chunks,['예금담보대출'])


def test_cross_institution_and_identical_training_pairs_rejected(chunks):
    for pos,neg in [('a','a'),('a','c')]:
        with pytest.raises(ValueError):
            validate_pairs([{'query':'학습 질문','positive_id':pos,'less_direct_id':neg}],chunks,[])


def test_training_pair_check_does_not_require_model_runtime(chunks):
    result=validate_pairs([{'query':'독립 학습 질문','positive_id':'a','less_direct_id':'b'}],chunks,['다른 질문'])
    assert result['training_queries']==1 and result['exact_normalized_query_overlap']==0
