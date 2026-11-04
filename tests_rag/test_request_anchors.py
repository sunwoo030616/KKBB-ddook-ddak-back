from rag_backend.request_anchors import request_anchors


def test_object_conjunction_splits_but_combined_operations_remain_one_anchor():
    assert len(request_anchors('추론·도구 실행을 번갈아 하는 방식과 자기 성찰 검색 방식을 찾아줘.'))==2
    assert len(request_anchors('검색과 자기 비판을 함께 수행하는 한 모델을 찾아줘.'))==1
    assert len(request_anchors('A method combining reasoning and acting.'))==1


def test_explicit_list_is_bounded_and_covers_all_source_characters():
    question='First method, second method; third method, fourth method.'
    parts=request_anchors(question)
    assert len(parts)==3 and 'fourth method' in parts[-1]['text']
    covered=set()
    for p in parts:
        assert question[p['start']:p['end']]==p['text']
        covered.update(range(p['start'],p['end']))
    assert all(i in covered for i,c in enumerate(question) if not c.isspace())


def test_implicit_with_comparison_is_an_explicit_documented_limitation():
    assert len(request_anchors('Compare retrieval with reflection.'))==1
