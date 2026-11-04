import json
from pathlib import Path

import pytest

from rag_backend.canvas_context import (ContextError,SlotUpdate,explicit_updates,merge_context,parse_amount)
from rag_backend.canvas import CanvasComposer,ComposeRequest
from rag_backend.pipeline import Pipeline
from rag_backend.store import DocumentStore
from rag_backend.widget_registry import WidgetRegistry
from tests_rag.test_canvas import Model,draft


def test_pdf_japan_then_duration_preserves_provenance():
    message='일본 여행 갈거야'
    first,_=merge_context(None,explicit_updates(message),message)
    next_message='3박 4일이야'
    second,_=merge_context(first,explicit_updates(next_message),next_message)
    assert second['destination']['value']=='일본'
    assert second['currency']['value']=='JPY'
    assert second['trip_days']['value']==4
    assert second['trip_days']['quote']=='3박 4일'
    assert second['currency']['origin']=='destination_lookup'


def test_destination_change_replaces_currency_and_scope():
    old,_=merge_context(None,explicit_updates('일본 여행 갈거야'),'일본 여행 갈거야')
    new,_=merge_context(old,explicit_updates('부산으로 여행 바꿔줘'),'부산으로 여행 바꿔줘')
    assert new['currency']['value']=='KRW'
    assert new['travel_scope']['value']=='domestic'


@pytest.mark.parametrize('update',[
    SlotUpdate(slot='destination',value='미국',quote='일본'),
    SlotUpdate(slot='trip_days',value='3',quote='3박4일'),
    SlotUpdate(slot='currency',value='USD',quote='일본'),
    SlotUpdate(slot='amount',value='2000',quote='2만엔'),
    SlotUpdate(slot='group_name',value='테니스',quote='없는 문장'),
])
def test_model_cannot_invent_context(update):
    with pytest.raises((ContextError,ValueError)):
        merge_context(None,[update],'일본 여행 3박4일 2만엔')


def test_currency_and_amount_units_never_silently_convert():
    assert parse_amount('50만원')=={'value':'500000','currency':'KRW'}
    assert parse_amount('2만엔')=={'value':'20000','currency':'JPY'}
    assert parse_amount('100.50 USD')=={'value':'100.50','currency':'USD'}


def test_composer_carries_pdf_context_across_turns(tmp_path):
    source=DocumentStore(tmp_path/'source.db');source.ingest()
    model=Model(draft('travel_card_charge_widget','travel_insurance_widget'),draft('travel_card_charge_widget'))
    c=CanvasComposer(Pipeline(source),model,tmp_path/'screen.db')
    first=c.compose(ComposeRequest(message='일본 여행 갈거야'))
    second=c.compose(ComposeRequest(message='3박4일이야. 보험은 빼줘',session_id=first['session_id'],expected_revision=1))
    assert [n['type'] for n in second['widgets']]==['travel_card_charge_widget']
    assert second['widgets'][0]['data']['currency']=='JPY'
    assert second['widgets'][0]['data']['tripDays']==4
    assert second['context']['destination']['value']=='일본'


def test_hot_disable_and_frontend_capabilities_are_hard_limits(tmp_path):
    source=DocumentStore(tmp_path/'source.db');source.ingest()
    c=CanvasComposer(Pipeline(source),Model(draft('deposit_protection_widget')),tmp_path/'screen.db')
    active,before=c.registry.snapshot();assert 'travel_insurance_widget' in active
    c.registry.set_enabled('travel_insurance_widget',False)
    active,after=c.registry.snapshot();assert 'travel_insurance_widget' not in active and before!=after
    candidates,_=c.candidates('여행 준비',None,active)
    assert 'travel_insurance_widget' not in candidates
    result=c.compose(ComposeRequest(message='예금보호를 보여줘',supported_widgets=['deposit_protection_widget']))
    assert {n['type'] for n in result['widgets']}=={'deposit_protection_widget'}


def test_registry_startup_preserves_disabled_state(tmp_path):
    definitions={'a':{'label':'A'}}
    r=WidgetRegistry(tmp_path/'r.db',definitions);r.set_enabled('a',False)
    again=WidgetRegistry(tmp_path/'r.db',definitions)
    assert again.snapshot()[0]=={}


def test_model_can_repeat_verified_destination_currency_without_relabeling_as_explicit():
    slots,_=merge_context(None,explicit_updates('일본 여행 갈 거야'),'일본 여행 갈 거야')
    merged,_=merge_context(slots,[SlotUpdate(slot='currency',value='JPY',quote='일본')],'일본 여행 갈 거야')
    assert merged['currency']['origin']=='destination_lookup'


def test_pure_parameter_followup_does_not_call_model(tmp_path):
    source=DocumentStore(tmp_path/'source.db');source.ingest()
    c=CanvasComposer(Pipeline(source),Model(draft('travel_card_charge_widget')),tmp_path/'screen.db')
    first=c.compose(ComposeRequest(message='일본 여행 갈 거야'))
    # No scripted output remains: a second model call would fail the test.
    second=c.compose(ComposeRequest(message='3박4일이야',session_id=first['session_id'],expected_revision=1))
    assert second['context']['trip_days']['value']==4
    assert any(t.get('model_calls')==0 for t in second['trace'])


def test_non_location_entities_are_not_saved_as_destination():
    context,changes=merge_context(None,[SlotUpdate(slot='destination',value='국민카드',quote='국민카드')],'국민카드를 찾았어')
    assert 'destination' not in context
    assert changes==['rejected_irrelevant_destination']


def test_unsupported_slot_does_not_destroy_valid_layout_edit(tmp_path):
    source=DocumentStore(tmp_path/'source.db');source.ingest()
    first=draft('travel_card_charge_widget','travel_insurance_widget')
    changed=draft('travel_card_charge_widget')
    changed.slot_updates=[SlotUpdate(slot='destination',value='미국',quote='일본')]
    c=CanvasComposer(Pipeline(source),Model(first,changed),tmp_path/'screen.db')
    initial=c.compose(ComposeRequest(message='일본 여행 갈 거야'))
    result=c.compose(ComposeRequest(message='3박4일이야. 보험은 빼줘',session_id=initial['session_id'],expected_revision=1))
    assert result['status']=='composed'
    assert result['context']['destination']['value']=='일본'
    assert result['context']['trip_days']['value']==4
    assert any(t.get('slot_rejections') for t in result['trace'])
    assert [w['type'] for w in result['widgets']]==['travel_card_charge_widget']
