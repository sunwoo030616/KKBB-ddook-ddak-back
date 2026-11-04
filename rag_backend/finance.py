"""Bounded financial evidence workflow and deterministic, Decimal-based tools.

The client selects typed intents; no claim of autonomous LLM planning. No live rates,
loan approval, transactions, or product-specific taxation are inferred.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Annotated, Literal
import time
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import Claim, SearchHit
from .generation import extractive_claims, verify_claims

Money = Annotated[Decimal, Field(ge=0, le=Decimal('1000000000000'), decimal_places=0)]
Principal = Annotated[Decimal, Field(gt=0, le=Decimal('1000000000000'), decimal_places=0)]
Rate = Annotated[Decimal, Field(ge=0, le=100, decimal_places=6)]
Topic = Literal['protection', 'collateral', 'collateral_eligibility', 'collateral_close', 'funding_compare', 'funding_inputs']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class InterestInput(StrictModel):
    kind: Literal['simple_interest']
    principal_won: Principal
    annual_rate_percent: Rate
    days: int = Field(ge=1, le=3650)
    day_basis: Literal[365, 366] = 365
    tax_rate_percent: Rate  # Explicit assumption: no inferred statutory tax rate.


class LoanInput(StrictModel):
    kind: Literal['amortized_loan']
    principal_won: Principal
    annual_rate_percent: Rate
    months: int = Field(ge=1, le=600)


class CompareInput(StrictModel):
    kind: Literal['funding_comparison']
    maturity_interest_net_won: Money
    early_interest_net_won: Money
    loan_principal_won: Principal
    annual_loan_rate_percent: Rate
    loan_days: int = Field(ge=1, le=3650)
    day_basis: Literal[365, 366] = 365
    extra_loan_cost_won: Money  # Must be supplied, including zero.

    @model_validator(mode='after')
    def interest_order(self):
        if self.early_interest_net_won > self.maturity_interest_net_won:
            raise ValueError('중도해지 이자가 만기 이자보다 크면 이 단순 비교 모형을 적용할 수 없습니다.')
        return self


Calculation = Annotated[InterestInput | LoanInput | CompareInput, Field(discriminator='kind')]


class CalculationRequest(StrictModel):
    calculation: Calculation


class FinanceRequest(StrictModel):
    topics: list[Topic] = Field(min_length=1, max_length=4)
    as_of: date = Field(default_factory=date.today)
    retriever: Literal['bm25', 'hybrid', 'dense', 'fusion'] = 'hybrid'
    calculation: Calculation | None = None

    @field_validator('topics')
    @classmethod
    def distinct_topics(cls, value):
        if len(set(value)) != len(value):
            raise ValueError('중복 주제는 허용하지 않습니다.')
        return value

    @field_validator('as_of')
    @classmethod
    def no_future(cls, value):
        if value > date.today():
            raise ValueError('미래 기준일은 지원하지 않습니다.')
        return value


class FinanceSection(StrictModel):
    topic: Topic
    status: Literal['answered', 'not_found', 'conflict']
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    temporal_note: str | None = None


class FinanceResponse(StrictModel):
    request_id: str
    status: Literal['answered', 'partial', 'not_found']
    as_of: date
    corpus_version: str
    sections: list[FinanceSection]
    claims: list[Claim]
    citations: list[SearchHit]
    calculation: dict | None
    missing_topics: list[Topic]
    trace: list[dict]
    latency_ms: float
    generation: Literal['extractive_with_deterministic_tools']
    real_transactions_executed: Literal[False]


WON = Decimal('1')


def won(value):
    return format(value.quantize(WON, rounding=ROUND_HALF_UP), 'f')


def calculate(spec):
    with localcontext() as context:
        context.prec = 40
        if isinstance(spec, InterestInput):
            gross = spec.principal_won * spec.annual_rate_percent / 100 * spec.days / spec.day_basis
            # Round gross and tax separately, then subtract for exact output reconciliation.
            gross_rounded = Decimal(won(gross))
            tax = Decimal(won(gross_rounded * spec.tax_rate_percent / 100))
            values = {'gross_interest_won': won(gross_rounded), 'tax_won': won(tax),
                      'net_interest_won': won(gross_rounded - tax)}
            formula = 'gross = principal * annual_rate_percent / 100 * days / day_basis; tax = rounded_gross * tax_rate_percent / 100'
            assumptions = ['고정금리 단리', '사용자가 지정한 365/366 일수 기준', '세율은 사용자 가정값', '세전 이자와 세금을 각각 원 단위 반올림; 실제 은행 절사 방식과 다를 수 있음']
        elif isinstance(spec, CompareInput):
            interest = Decimal(won(spec.loan_principal_won * spec.annual_loan_rate_percent / 100 * spec.loan_days / spec.day_basis))
            cost = interest + spec.extra_loan_cost_won
            gap = spec.maturity_interest_net_won - cost - spec.early_interest_net_won
            values = {'loan_interest_won': won(interest), 'total_loan_cost_won': won(cost),
                      'retained_net_interest_won': won(spec.maturity_interest_net_won - cost),
                      'interest_difference_won': won(gap),
                      'interest_only_result': 'retain_higher' if gap > 0 else 'terminate_higher' if gap < 0 else 'equal'}
            formula = 'difference = maturity_interest_net - (principal * annual_rate / 100 * days / day_basis + extra_cost) - early_interest_net'
            assumptions = ['세후 만기/해지 이자는 사용자 입력', '고정금리 만기일시상환 대출 단리', '대출 원금은 별도로 상환해야 함', '이자 수익만 비교하며 서로 다른 시점의 재투자·기회비용·할인율·추가 자금 흐름은 제외', '상품 추천이나 대출 가능 여부 판단이 아님']
        else:
            rate = spec.annual_rate_percent / 1200
            principal = spec.principal_won
            monthly = principal / spec.months if rate == 0 else principal * rate / (1 - (1 + rate) ** -spec.months)
            payment = Decimal(won(monthly))
            balance = principal
            rows = []
            for month in range(1, spec.months + 1):
                interest = Decimal(won(balance * rate))
                # Last payment clears rounding residual; tiny principals may clear early.
                repaid = min(balance, max(Decimal(0), payment - interest)) if month < spec.months else balance
                balance -= repaid
                rows.append({'month': month, 'payment_won': won(repaid + interest),
                             'principal_won': won(repaid), 'interest_won': won(interest),
                             'balance_won': won(balance)})
            total_interest = sum(Decimal(row['interest_won']) for row in rows)
            values = {'regular_payment_won': won(payment), 'total_interest_won': won(total_interest),
                      'total_payment_won': won(principal + total_interest), 'schedule': rows}
            formula = 'payment = P * r / (1 - (1+r)^(-n)); r = annual_rate_percent / 1200; zero_rate => P/n'
            assumptions = ['고정금리 원리금균등 월납', '매월 이자·납입액 원 단위 반올림, 마지막 회차 잔액 정산', '실제 일수·휴일·중도상환·수수료·금리 변경 제외']
        return {'tool': spec.kind, 'input': spec.model_dump(mode='json'), 'values': values,
                'formula': formula, 'rounding': 'KRW integer, ROUND_HALF_UP', 'assumptions': assumptions,
                'origin': 'deterministic_decimal_tool_v1', 'generated_by_llm': False}


# A fixed, auditable intent registry. Retrieval and calculation have separate provenance.
INTENTS = {
    'protection': ('fsc', '예금보호한도 원금 이자'),
    'collateral': ('kb_bank', '예금담보대출 예금 적금 담보'),
    'collateral_eligibility': ('kb_bank', '예금담보대출 신청 제한 명의'),
    'collateral_close': ('kb_bank', '예금담보대출 해지 상환'),
    'funding_compare': ('kb_bank', '예금 중도해지 예금담보대출 비용 비교'),
    'funding_inputs': ('kb_bank', '비교 계산 필요한 기간 만기 이자'),
}


def analyze(pipeline, req: FinanceRequest):
    started = time.perf_counter()
    request_id = str(uuid.uuid4())
    trace = [{'step': 'plan', 'planner': 'typed_intent_registry_v1', 'max_retrieval_calls': 4,
              'topics': req.topics, 'as_of': str(req.as_of)}]
    sections, claims, citations = [], [], []
    missing = []
    for topic in req.topics:
        institution, query = INTENTS[topic]
        # Filter exact topic and temporal validity before ranking, not after a small top-k.
        scoped = [c for c in pipeline.chunks if c.institution == institution and topic in c.topics
                  and c.available_on(req.as_of)]
        ids = {c.id for c in scoped}
        # Retrieve all once, then select from the topic set. Dense encoder reused.
        candidates = pipeline.search(query, institution, req.retriever, len(pipeline.chunks), req.as_of, topic=topic) if scoped else []
        hits = [h for h in candidates if h.chunk_id in ids][:1]
        trace.append({'step': 'retrieve', 'topic': topic, 'institution': institution,
                      'eligible_ids': sorted(ids), 'selected_ids': [h.chunk_id for h in hits]})
        if not hits:
            missing.append(topic)
            sections.append({'topic': topic, 'status': 'not_found', 'reason': 'no_dated_topic_evidence'})
            continue
        # Detect conflicting effective-period records instead of silently picking one.
        periods = [c for c in scoped if c.temporal_basis == 'effective_period']
        if len(periods) > 1:
            missing.append(topic)
            sections.append({'topic': topic, 'status': 'conflict', 'reason': 'overlapping_effective_records'})
            continue
        extracted = extractive_claims(hits)
        verify_claims(extracted, hits)
        claims.extend(extracted)
        citations.extend(hits)
        sections.append({'topic': topic, 'status': 'answered', 'evidence_ids': [h.chunk_id for h in hits],
                         'temporal_note': '공표된 시행 기간 기준' if periods else '출처 작성시점의 설명; 현재 상품 조건 재확인 필요'})
    result = calculate(req.calculation) if req.calculation else None
    if result:
        trace.append({'step': 'calculate', 'tool': req.calculation.kind,
                      'input_origin': 'user_supplied', 'rate_inferred_from_documents': False})
    status = 'partial' if missing and (claims or result) else 'not_found' if missing else 'answered'
    latency = round((time.perf_counter() - started) * 1000, 3)
    pipeline.store.audit(request_id, status, 'financial_workflow', latency)
    return {'request_id': request_id, 'status': status, 'as_of': req.as_of, 'corpus_version': pipeline.version,
            'sections': sections, 'claims': claims, 'citations': citations, 'calculation': result,
            'missing_topics': missing, 'trace': trace, 'latency_ms': latency,
            'generation': 'extractive_with_deterministic_tools', 'real_transactions_executed': False}
