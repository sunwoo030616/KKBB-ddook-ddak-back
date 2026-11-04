from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
import random

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from rag_backend.app import create_app
from rag_backend.finance import (CalculationRequest, FinanceRequest, InterestInput, LoanInput,
                                 analyze, calculate)
from rag_backend.models import Chunk
from rag_backend.pipeline import Pipeline
from rag_backend.store import DocumentStore
from tests_rag.test_dense import FakeEncoder
from rag_backend.dense import DenseIndex


@pytest.fixture
def pipeline(tmp_path):
    store = DocumentStore(tmp_path / 'finance.db')
    store.ingest()
    index = DenseIndex(store.load()[0], FakeEncoder(), tmp_path / 'vectors.db')
    return Pipeline(store, dense_index=index)


@pytest.mark.parametrize('method', ['bm25', 'hybrid', 'dense', 'fusion'])
@pytest.mark.parametrize('day,expected', [('2025-08-31','fsc-protection-before'),
                                           ('2025-09-01','fsc-protection-current')])
def test_boundary_date_never_mixes_old_and_new(pipeline, method, day, expected):
    req = FinanceRequest(topics=['protection'], as_of=day, retriever=method)
    result = analyze(pipeline, req)
    assert result['status'] == 'answered'
    assert [h.chunk_id for h in result['citations']] == [expected]
    assert result['citations'][0].temporal_basis == 'effective_period'


def test_before_known_history_abstains(pipeline):
    result = analyze(pipeline, FinanceRequest(topics=['protection'], as_of='2024-01-01'))
    assert result['status'] == 'not_found' and not result['citations']


def test_publication_snapshot_not_used_before_content_date(pipeline):
    result = analyze(pipeline, FinanceRequest(topics=['collateral'], as_of='2025-09-01'))
    assert result['status'] == 'not_found'


def test_multi_evidence_and_partial_results(pipeline):
    result = analyze(pipeline, FinanceRequest(topics=['protection','collateral','funding_compare']))
    assert result['status'] == 'answered'
    assert len(result['claims']) == len(result['citations']) == 3
    assert {h.institution for h in result['citations']} == {'kb_bank','fsc'}
    old = analyze(pipeline, FinanceRequest(topics=['protection','collateral'], as_of='2025-09-01'))
    assert old['status'] == 'partial'
    assert old['missing_topics'] == ['collateral']


def test_conflicting_dated_records_abstain(pipeline):
    original = pipeline.by_id['fsc-protection-current']
    pipeline.chunks.append(original.model_copy(update={'id':'conflicting-official-record'}))
    result = analyze(pipeline, FinanceRequest(topics=['protection']))
    assert result['status'] == 'not_found'
    assert result['sections'][0]['status'] == 'conflict'
    assert result['claims'] == []


def test_no_guessed_rates_and_budget_validation(tmp_path):
    client = TestClient(create_app(tmp_path / 'api.db', enable_dense=False))
    invalid = [
      {'topics':['funding_compare'], 'calculation':{'kind':'funding_comparison'}},
      {'topics':['protection']*2},
      {'topics':['protection'], 'as_of':str(date.today()+timedelta(days=1))},
      {'topics':['protection'], 'retriever':'unknown'},
      {'topics':['protection'], 'account_number':'1234'},
      {'topics':['protection','collateral','collateral_eligibility','collateral_close','funding_compare']},
    ]
    for request in invalid:
        assert client.post('/finance/analyze', json=request).status_code == 422
    assert client.post('/finance/analyze', json={'topics':['protection'],'retriever':'dense'}).status_code == 503
    result = client.post('/finance/analyze', json={'topics':['funding_compare']}).json()
    assert result['calculation'] is None  # Never fabricate numeric inputs.


def test_interest_known_value_and_rounding():
    spec = InterestInput(kind='simple_interest', principal_won='10000000', annual_rate_percent='3.65',
                         days=100, tax_rate_percent='15.4')
    result = calculate(spec)
    assert result['values'] == {'gross_interest_won':'100000','tax_won':'15400','net_interest_won':'84600'}
    assert result['generated_by_llm'] is False


def test_interest_against_independent_rational_oracle():
    rng = random.Random(20261102)
    # Integer rational arithmetic oracle, independent of Decimal implementation.
    def half_up(f):
        return (2*f.numerator + f.denominator)//(2*f.denominator)
    for _ in range(100):
        principal, rate_basis_points, days = rng.randint(1,10**9), rng.randint(0,3000), rng.randint(1,1000)
        tax_basis_points = rng.randint(0,3000)
        spec = InterestInput(kind='simple_interest', principal_won=principal,
                             annual_rate_percent=Decimal(rate_basis_points)/100,
                             days=days, tax_rate_percent=Decimal(tax_basis_points)/100)
        result = calculate(spec)['values']
        gross = half_up(Fraction(principal*rate_basis_points*days,10000*365))
        tax = half_up(Fraction(gross*tax_basis_points,10000))
        assert int(result['gross_interest_won']) == gross
        assert int(result['tax_won']) == tax
        assert int(result['net_interest_won']) == gross-tax


@pytest.mark.parametrize('principal,rate,months', [('1000000','0',3), ('100000000','4.2',360),
                                                  ('1','0',600),('1','100',600),('1200000','12',12)])
def test_loan_schedule_conserves_principal(principal, rate, months):
    result = calculate(LoanInput(kind='amortized_loan', principal_won=principal, annual_rate_percent=rate, months=months))['values']
    rows = result['schedule']
    assert len(rows) == months and rows[-1]['balance_won'] == '0'
    assert sum(int(row['principal_won']) for row in rows) == int(principal)
    assert sum(int(row['payment_won']) for row in rows) == int(result['total_payment_won'])
    for row in rows:
        assert int(row['payment_won']) == int(row['principal_won']) + int(row['interest_won'])
        assert int(row['balance_won']) >= 0


@pytest.mark.parametrize('patch', [{'annual_rate_percent':'NaN'}, {'principal_won':'-1'},
                                  {'principal_won':'1.5'}, {'annual_rate_percent':'Infinity'},
                                  {'days':0}, {'tax_rate_percent':101}, {'day_basis':360}])
def test_invalid_calculations_rejected(patch):
    args = dict(kind='simple_interest',principal_won='10000',annual_rate_percent='3',days=365,tax_rate_percent='0')
    with pytest.raises(ValidationError):
        InterestInput(**(args | patch))


def test_comparison_numeric_provenance_separate_from_citations(pipeline):
    calculation = {'kind':'funding_comparison','maturity_interest_net_won':'1000000',
                   'early_interest_net_won':'300000','loan_principal_won':'10000000',
                   'annual_loan_rate_percent':'3.65','loan_days':100,'extra_loan_cost_won':'10000'}
    result = analyze(pipeline, FinanceRequest(topics=['funding_compare','funding_inputs'], calculation=calculation))
    assert result['calculation']['values']['interest_difference_won'] == '590000'
    assert result['calculation']['origin'] == 'deterministic_decimal_tool_v1'
    assert result['trace'][-1]['rate_inferred_from_documents'] is False
    assert len(result['citations']) == 2
    with pipeline.store.connect() as db:
        row = db.execute('SELECT * FROM requests WHERE request_id=?', (result['request_id'],)).fetchone()
    assert '10000000' not in str(row)


def test_invalid_date_metadata_rejected(pipeline):
    item = pipeline.chunks[0].model_dump()
    with pytest.raises(ValidationError):
        Chunk.model_validate(item | {'effective_from':date(2026,1,1),'effective_until':date(2025,1,1)})


def test_publication_date_prevents_lookahead(pipeline):
    result = analyze(pipeline, FinanceRequest(topics=['collateral'], as_of='2026-06-20'))
    assert result['status'] == 'not_found'
    result = analyze(pipeline, FinanceRequest(topics=['collateral'], as_of='2026-06-22'))
    assert result['status'] == 'answered'
    assert str(result['citations'][0].content_as_of) == '2026-06-17'
