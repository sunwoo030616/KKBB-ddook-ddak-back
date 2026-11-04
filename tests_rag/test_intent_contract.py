import json

import pytest

from rag_backend.canvas import CanvasComposer,ComposeRequest,ScreenDraft
from rag_backend.intent_contract import IntentInterpreter,evidence_spans
from rag_backend.pipeline import Pipeline
from rag_backend.store import DocumentStore


class Model:
    def __init__(self,*outputs):self.outputs=iter(outputs);self.calls=0
    def complete(self,*args,**kwargs):
        self.calls+=1
        value=next(self.outputs)
        return {'text':value.model_dump_json() if hasattr(value,'model_dump_json') else json.dumps(value,ensure_ascii=False),'latency_ms':1}


def plan(*types):return ScreenDraft(title='금융 화면',widgets=[{'type':k,'priority':1} for k in types],clarification='')


@pytest.fixture
def pipeline(tmp_path):
    store=DocumentStore(tmp_path/'source.db');store.ingest();return Pipeline(store)


def test_spans_use_exact_source_offsets_and_keep_long_tail():
    text='보험은 빼고 환전은 보여줘. 다른 일도 하고, 회비도 보고, 비용도 보고, 정산도 보고, 긴 마지막 요청도 있어.'
    spans=evidence_spans(text)
    assert len(spans)<=6
    assert all(s['text']==text[s['start']:s['end']] for s in spans)
    assert spans[-1]['end']==len(text)
    assert ''.join(s['text'] for s in spans)==text


def test_simple_message_skips_intent_model():
    model=Model();interpreter=IntentInterpreter(model)
    assert interpreter.inspect('대출 상환표를 보여줘')==(None,None)
    assert model.calls==0


def test_invented_evidence_ids_fail_contract():
    result,trace=IntentInterpreter(Model({'operation':'merge','stances':{'e99':'request'}})).inspect('보험은 빼줘')
    assert result is None and trace['status']=='rejected'


def test_model_cannot_clear_without_explicit_source_or_previous_screen():
    result,trace=IntentInterpreter(Model({'operation':'clear','stances':{'e0':'exclude'}})).inspect('보험은 빼줘',{'widgets':[]})
    assert result is None and trace['reason']=='ungrounded_clear_operation'


def test_context_and_exclusions_without_positive_goal_never_reach_planner(pipeline,tmp_path):
    model=Model({'operation':'clarify','stances':{'e0':'context','e1':'exclude'}})
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',intent_interpreter=IntentInterpreter(model))
    result=composer.compose(ComposeRequest(message='부산으로 여행 가. 해외 결제는 필요 없어.',intent_mode='auto'))
    assert result['status']=='clarify' and result['widgets']==[] and model.calls==1
    assert result['trace'][0]['positive_span_count']==0


def test_exclude_only_followup_edits_only_previous_candidates(pipeline,tmp_path):
    model=Model(plan('travel_card_charge_widget','travel_insurance_widget'),
        {'operation':'merge','stances':{'e0':'exclude'}},plan('travel_card_charge_widget'))
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',intent_interpreter=IntentInterpreter(model))
    first=composer.compose(ComposeRequest(message='일본 여행 갈 거야'))
    second=composer.compose(ComposeRequest(message='보험 빼줘',intent_mode='auto',session_id=first['session_id'],expected_revision=1))
    assert [w['type'] for w in second['widgets']]==['travel_card_charge_widget']
    retrieval=next(t for t in second['trace'] if t['step']=='component_retrieval')
    assert set(retrieval['candidate_ids'])=={'travel_card_charge_widget','travel_insurance_widget'}
    assert model.calls==3


def test_explicit_clear_commits_empty_revision_instead_of_preserving_old_screen(pipeline,tmp_path):
    model=Model(plan('travel_card_charge_widget'),{'operation':'clear','stances':{'e0':'exclude'}})
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',intent_interpreter=IntentInterpreter(model))
    first=composer.compose(ComposeRequest(message='일본 환전 화면'))
    second=composer.compose(ComposeRequest(message='모두 지워줘',intent_mode='auto',session_id=first['session_id'],expected_revision=1))
    assert second['status']=='composed' and second['revision']==2 and second['widgets']==[]
    assert second['patch']==[{'op':'remove','id':'travel_card_charge_widget'}]
    assert model.calls==1  # exact UI clear directive requires no model


def test_parameter_update_bypasses_even_enforced_intent_model(pipeline,tmp_path):
    model=Model(plan('travel_card_charge_widget'))
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',intent_interpreter=IntentInterpreter(model))
    first=composer.compose(ComposeRequest(message='일본 환전 화면'))
    result=composer.compose(ComposeRequest(message='4일이야',intent_mode='enforce',session_id=first['session_id'],expected_revision=1))
    assert result['context']['trip_days']['value']==4 and model.calls==1


def test_decimal_rate_is_not_split_into_separate_evidence_spans():
    text='보험은 빼고 연 금리 3.65%인 대출의 상환표를 보여줘.'
    spans=evidence_spans(text)
    assert any('3.65%' in s['text'] for s in spans)
    assert ''.join(s['text'] for s in spans)==text


def test_again_word_does_not_authorize_whole_screen_clear():
    result,trace=IntentInterpreter(Model({'operation':'clear','stances':{'e0':'exclude'}})).inspect(
        '보험만 다시 지워줘',{'widgets':[{'type':'travel_insurance_widget'},{'type':'travel_card_charge_widget'}]})
    assert result is None and trace['reason']=='ungrounded_clear_operation'


def test_explicit_requested_same_widget_protects_against_subfeature_exclusion():
    from rag_backend.intent_contract import bind_exclusions
    class Ranker:
        def score_pairs(self,pairs):return [.8,.1,.9,.1]
    blocked,trace=bind_exclusions({'excluded_queries':['우대 금리는 빼줘'],'positive_queries':['대출 상환표는 보여줘']},
        {'loan':{'purpose':'대출 상환'},'fx':{'purpose':'환전'}},Ranker())
    assert blocked==set() and trace['protected_ids']==['loan']


def test_negative_binding_removes_previous_widget_from_generation_allowlist(pipeline,tmp_path):
    class Ranker:
        def score_pairs(self,pairs):
            return [.9 if ('예금보호' in query and '예금보호' in purpose) else
                    .9 if ('월 상환표' in query and '월 납입액' in purpose) else .8 if ('예금 비용 비교' in query and '중도해지' in purpose) else .0001 for query,purpose in pairs]
    class CheckedModel(Model):
        def complete(self,*args,**kwargs):
            # Third call is final planning: previously present protection is now
            # impossible to select, even if the model says it was removed in prose.
            if self.calls==2:
                assert 'deposit_protection_widget' not in json.dumps(kwargs['output_type'].model_json_schema())
            return super().complete(*args,**kwargs)
    model=CheckedModel(plan('funding_comparison_widget','deposit_protection_widget'),
        {'operation':'merge','stances':{'e0':'exclude','e1':'request'}},
        plan('funding_comparison_widget','loan_repayment_schedule_widget'))
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',Ranker(),intent_interpreter=IntentInterpreter(model))
    first=composer.compose(ComposeRequest(message='예금 비용 비교와 예금보호'))
    second=composer.compose(ComposeRequest(message='예금보호는 빼고 월 상환표를 추가해줘',session_id=first['session_id'],expected_revision=1,intent_mode='auto'))
    assert {w['type'] for w in second['widgets']}=={'funding_inputs_widget','funding_comparison_widget','loan_inputs_widget','loan_repayment_schedule_widget'}
    assert any(p['op']=='remove' and p['id']=='deposit_protection_widget' for p in second['patch'])


def test_bound_removal_of_only_existing_widget_commits_empty_screen(pipeline,tmp_path):
    class Ranker:
        def score_pairs(self,pairs):return [.9 if '보험' in p else .0001 for _,p in pairs]
    model=Model(plan('travel_insurance_widget'),{'operation':'merge','stances':{'e0':'exclude'}})
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',Ranker(),intent_interpreter=IntentInterpreter(model))
    first=composer.compose(ComposeRequest(message='여행 보험 화면'))
    second=composer.compose(ComposeRequest(message='보험 빼줘',intent_mode='auto',session_id=first['session_id'],expected_revision=1))
    assert second['status']=='composed' and second['widgets']==[] and second['revision']==2
    assert model.calls==2  # intent inference, no subsequent planner call for a bound removal


def test_repeated_model_selection_canonicalizes_without_inventing_other_features(pipeline,tmp_path):
    from rag_backend.canvas import decode_model_draft,compile_screen,InvalidScreen
    raw=ScreenDraft(title='상환표',widgets=[{'type':'loan_repayment_schedule_widget','priority':2},
        {'type':'loan_repayment_schedule_widget','priority':0}],clarification='')
    normalized,repeated=decode_model_draft(raw.model_dump_json(),ScreenDraft)
    assert repeated==['loan_repayment_schedule_widget']
    assert len(normalized.widgets)==1 and normalized.widgets[0].priority==0
    assert [n['type'] for n in compile_screen(normalized)[0]]==['loan_inputs_widget','loan_repayment_schedule_widget']
    with pytest.raises(InvalidScreen,match='duplicate_widgets'):compile_screen(raw)


def test_clear_then_new_goal_is_not_mistaken_for_empty_screen(pipeline,tmp_path):
    model=Model(plan('funding_comparison_widget'),
        {'operation':'replace','stances':{'e0':'exclude','e1':'request'}},plan('loan_repayment_schedule_widget'))
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',intent_interpreter=IntentInterpreter(model))
    first=composer.compose(ComposeRequest(message='예금 비용 비교'))
    second=composer.compose(ComposeRequest(message='화면을 모두 지우고 대출 상환표를 새로 보여줘',intent_mode='auto',session_id=first['session_id'],expected_revision=1))
    assert [n['type'] for n in second['widgets']]==['loan_inputs_widget','loan_repayment_schedule_widget']
    assert model.calls==3
