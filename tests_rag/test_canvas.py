import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
import pytest

from rag_backend.app import create_app
from rag_backend.canvas import (CanvasComposer,ComposeConflict,ComposeRequest,ScreenDraft,
                                InvalidScreen,ScreenStore,compile_screen)
from rag_backend.pipeline import Pipeline
from rag_backend.store import DocumentStore


def draft(*kinds):
    return ScreenDraft(title='내 금융 화면',clarification='',widgets=[{'type':k,'priority':1} for k in kinds])


class Model:
    def __init__(self,*drafts):self.drafts=iter(drafts)
    def complete(self,*args,**kwargs):
        return {'text':next(self.drafts).model_dump_json(),'latency_ms':1}


@pytest.fixture
def pipeline(tmp_path):
    s=DocumentStore(tmp_path/'source.db');s.ingest();return Pipeline(s)


def test_dependency_compiler_orders_inputs_before_output():
    nodes,added=compile_screen(draft('funding_comparison_widget'))
    assert [n['type'] for n in nodes]==['funding_inputs_widget','funding_comparison_widget']
    assert added==['funding_inputs_widget']
    assert nodes[1]['bindings'][0]['source']=='funding_inputs_widget'


def test_conflicting_actions_and_duplicate_widgets_rejected():
    for plan in [draft('card_freeze_all','card_recovery_widget'),draft('deposit_protection_widget','deposit_protection_widget')]:
        with pytest.raises(InvalidScreen):compile_screen(plan)


def test_implicit_dependencies_cannot_exceed_screen_budget():
    plan=draft('funding_comparison_widget','loan_repayment_schedule_widget','card_freeze_all',
               'travel_insurance_widget','deposit_protection_widget','expense_report_widget')
    with pytest.raises(InvalidScreen,match='screen_budget_exceeded'):compile_screen(plan)


def test_sensitive_widget_never_claims_transaction_complete():
    nodes,_=compile_screen(draft('atm_smart_withdrawal','card_freeze_all'))
    assert nodes[0]['type']=='card_freeze_all'
    for n in nodes:
        assert n['actions'][0]['enabled'] is False
        assert n['actions'][0]['requires_user_confirmation'] is True
        assert 'authCode' not in n['data'] and 'frozen' not in n['data']


def test_multi_turn_patch_preserves_stable_widget_and_calculation(pipeline,tmp_path):
    c=CanvasComposer(pipeline,Model(draft('funding_comparison_widget'),draft('funding_comparison_widget','deposit_protection_widget')),tmp_path/'screens.db')
    first=c.compose(ComposeRequest(message='예금 유지 해지 비교 화면',calculation={
        'kind':'funding_comparison','maturity_interest_net_won':'1000000','early_interest_net_won':'300000',
        'loan_principal_won':'10000000','annual_loan_rate_percent':'3.65','loan_days':100,'extra_loan_cost_won':'10000'}))
    second=c.compose(ComposeRequest(message='예금보호도 추가해줘',session_id=first['session_id'],expected_revision=1))
    assert second['revision']==2
    assert [p for p in second['patch'] if p['op']=='add']==[{'op':'add','id':'deposit_protection_widget','index':2}]
    node=next(n for n in second['widgets'] if n['type']=='funding_comparison_widget')
    assert node['data']['values']['interest_difference_won']=='590000'
    assert second['widgets'][-1]['data']['evidence'][0]['institution']=='fsc'


def test_one_bounded_model_repair(pipeline,tmp_path):
    c=CanvasComposer(pipeline,Model(draft('card_freeze_all','card_recovery_widget'),draft('card_recovery_widget')),tmp_path/'s.db')
    result=c.compose(ComposeRequest(message='분실했던 카드를 찾았어'))
    assert result['status']=='composed'
    assert [step['status'] for step in result['trace'] if step['step']=='llm_plan']==['rejected','validated']


def test_revision_conflicts_do_not_overwrite_screen(tmp_path):
    store=ScreenStore(tmp_path/'s.db');store.commit('screen',0,{'widgets':[]})
    gate=Barrier(2)
    def update(i):
        store.read('screen',1);gate.wait()
        try:store.commit('screen',1,{'winner':i});return 'ok'
        except ComposeConflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(update,[1,2]))
    assert sorted(results)==['conflict','ok']
    with pytest.raises(ComposeConflict):store.read('screen',1)
    assert store.read('screen',2)['winner'] in (1,2)


def test_raw_message_and_model_output_not_persisted(pipeline,tmp_path):
    c=CanvasComposer(pipeline,Model(draft('deposit_protection_widget')),tmp_path/'s.db')
    raw='이 문장은 화면 상태 DB에 저장되면 안 됩니다. 예금 보호 화면 부탁해'
    result=c.compose(ComposeRequest(message=raw),debug=True)
    with c.store.connect() as db:payload=db.execute('SELECT payload FROM screens').fetchone()[0]
    assert raw not in payload and 'model_output' not in payload
    assert result['trace'][1]['model_output']


def test_unconfigured_canvas_and_input_contract(tmp_path):
    client=TestClient(create_app(tmp_path/'api.db',enable_dense=False,enable_research=False,enable_canvas=False))
    assert len(client.get('/canvas/catalog').json()['widgets'])==16
    assert client.post('/canvas/compose',json={'message':'금융 화면 구성'}).status_code==503
    for invalid in [{'message':' '},{'message':'금융 화면','expected_revision':-1},
                    {'message':'금융 화면','session_id':'not-a-session'},{'message':'금융 화면','debug':True}]:
        assert client.post('/canvas/compose',json=invalid).status_code==422
