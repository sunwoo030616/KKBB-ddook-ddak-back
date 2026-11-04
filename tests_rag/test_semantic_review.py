import json

import pytest

from rag_backend.canvas import CanvasComposer,ComposeRequest,REGISTRY,ScreenDraft
from rag_backend.semantic_review import SemanticReviewer,ReviewDraft,satisfies_review
from rag_backend.pipeline import Pipeline
from rag_backend.store import DocumentStore


def plan(*kinds):
    return ScreenDraft(title='금융 화면',widgets=[{'type':k,'priority':1} for k in kinds],clarification='')


def review(**changes):
    return ReviewDraft(**({'required':[],'forbidden':[],'preserve':[],'unnecessary':[],'clarification':''}|changes))


class Model:
    def __init__(self,*responses):self.responses=iter(responses);self.calls=0
    def complete(self,*args,**kwargs):
        self.calls+=1
        result=next(self.responses)
        return {'text':result if isinstance(result,str) else result.model_dump_json(),'latency_ms':1}


@pytest.mark.parametrize('output,reason',[
    (review(required=[{'widget':'invented','quote':'보험'}]),'review_outside_capability'),
    (review(required=[{'widget':'travel_insurance_widget','quote':'보험 필수'}]),'review_quote_not_in_request'),
    (review(preserve=['travel_insurance_widget']),'review_invented_history'),
    (review(required=[{'widget':'travel_insurance_widget','quote':'보험'}],forbidden=[{'widget':'travel_insurance_widget','quote':'보험'}]),'review_conflicting_requirements'),
    ('not JSON',''),
])
def test_invalid_critique_cannot_be_used(output,reason):
    result,trace=SemanticReviewer(Model(output)).inspect('보험은 빼줘',plan('travel_insurance_widget'),None,REGISTRY,{})
    assert result is None and trace['status']=='invalid_review' and not trace['needs_revision']
    assert reason in trace['reason']


def test_repair_checks_unnecessary_as_well_as_explicit_forbidden():
    critique=review(required=[{'widget':'loan_repayment_schedule_widget','quote':'상환표'}],unnecessary=['travel_insurance_widget'])
    assert not satisfies_review(plan('loan_repayment_schedule_widget','travel_insurance_widget'),critique)
    assert satisfies_review(plan('loan_repayment_schedule_widget'),critique)


@pytest.fixture
def pipeline(tmp_path):
    store=DocumentStore(tmp_path/'source.db');store.ingest();return Pipeline(store)


class NarrowRanker:
    def score_pairs(self,pairs):return [1 if '예금보호' in purpose else 0 for _,purpose in pairs]


def test_critic_recovers_component_excluded_by_retrieval(pipeline,tmp_path):
    model=Model(plan('deposit_protection_widget'),
        review(required=[{'widget':'loan_repayment_schedule_widget','quote':'월 상환표'}],unnecessary=['deposit_protection_widget']),
        plan('loan_repayment_schedule_widget'))
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',NarrowRanker(),SemanticReviewer(model))
    result=composer.compose(ComposeRequest(message='대출 월 상환표를 보여줘',review_mode='repair'))
    assert [n['type'] for n in result['widgets']]==['loan_inputs_widget','loan_repayment_schedule_widget']
    assert model.calls==3
    assert result['trace'][-3]['status']=='accepted'


def test_bad_repair_keeps_valid_initial_plan(pipeline,tmp_path):
    model=Model(plan('travel_insurance_widget'),
        review(required=[{'widget':'loan_repayment_schedule_widget','quote':'월 상환표'}]),plan('travel_insurance_widget'))
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',semantic_reviewer=SemanticReviewer(model))
    result=composer.compose(ComposeRequest(message='월 상환표를 보여줘',review_mode='repair'))
    assert [n['type'] for n in result['widgets']]==['travel_insurance_widget']
    assert any(t['step']=='semantic_refinement' and t['status']=='rejected' for t in result['trace'])
    assert model.calls==3


def test_audit_logs_critique_without_modification(pipeline,tmp_path):
    model=Model(plan('travel_insurance_widget'),review(forbidden=[{'widget':'travel_insurance_widget','quote':'보험 빼'}]))
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',semantic_reviewer=SemanticReviewer(model))
    result=composer.compose(ComposeRequest(message='보험 빼 주세요',review_mode='audit'))
    assert result['widgets'][0]['type']=='travel_insurance_widget' and model.calls==2


def test_parameter_route_skips_review_and_all_model_calls(pipeline,tmp_path):
    model=Model(plan('travel_card_charge_widget'))
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',semantic_reviewer=SemanticReviewer(model))
    first=composer.compose(ComposeRequest(message='일본 환전 화면',review_mode='off'))
    second=composer.compose(ComposeRequest(message='4일이야',session_id=first['session_id'],expected_revision=1,review_mode='repair'))
    assert model.calls==1
    assert second['context']['trip_days']['value']==4
    assert not any(t['step']=='semantic_review' for t in second['trace'])


def test_review_grammar_disallows_nonexistent_history_before_generation():
    reviewer=SemanticReviewer(Model())
    schema=reviewer.schema_for({'travel_insurance_widget','deposit_protection_widget'},set(),{'deposit_protection_widget'})
    with pytest.raises(ValueError):schema.model_validate(review(preserve=['travel_insurance_widget']).model_dump())
    with pytest.raises(ValueError):schema.model_validate(review(unnecessary=['travel_insurance_widget']).model_dump())
    assert reviewer.schema_for({'deposit_protection_widget','travel_insurance_widget'},set(),{'deposit_protection_widget'}) is schema


def test_capability_removes_result_when_required_input_renderer_is_absent(pipeline,tmp_path):
    model=Model()
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db')
    result=composer.compose(ComposeRequest(message='月 상환표를 보여줘',supported_widgets=['loan_repayment_schedule_widget']))
    assert result['status']=='clarify' and model.calls==0


def test_clarification_without_widget_edits_does_not_trigger_third_model_call(pipeline,tmp_path):
    model=Model(plan('travel_card_charge_widget'),review(
        required=[{'widget':'travel_card_charge_widget','quote':'환전'}],clarification='추가로 필요한 것이 있나요?'))
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db',semantic_reviewer=SemanticReviewer(model))
    result=composer.compose(ComposeRequest(message='일본 환전 화면',review_mode='repair'))
    assert model.calls==2 and result['status']=='composed'
    assert not any(t['step']=='semantic_refinement' for t in result['trace'])
