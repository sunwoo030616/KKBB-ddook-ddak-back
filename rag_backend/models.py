from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

Institution = Literal['kb_card', 'kb_securities', 'kb_bank', 'shinhan_card', 'fsc']


class Chunk(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    source_id: str
    institution: Institution
    title: str
    section: str
    url: HttpUrl
    verified_at: date
    published_at: date | None = None
    content_as_of: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    temporal_basis: Literal['undated', 'effective_period', 'publication_snapshot'] = 'undated'
    text: str = Field(min_length=10)
    topics: list[str]
    keywords: list[str]

    @model_validator(mode='after')
    def valid_period(self):
        if self.effective_until and (not self.effective_from or self.effective_until < self.effective_from):
            raise ValueError('Invalid effective period')
        if self.temporal_basis == 'effective_period' and not self.effective_from:
            raise ValueError('Effective period requires a start date')
        if self.temporal_basis == 'publication_snapshot' and not self.content_as_of:
            raise ValueError('Publication snapshot requires content_as_of')
        return self

    def available_on(self, as_of: date):
        if self.published_at and as_of < self.published_at:
            return False
        if self.effective_from and as_of < self.effective_from:
            return False
        if self.effective_until and as_of > self.effective_until:
            return False
        if self.content_as_of and as_of < self.content_as_of:
            return False
        return True


class AskRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=2, max_length=1500)
    as_of: date = Field(default_factory=date.today)
    institution: Institution | None = None
    retriever: Literal['bm25', 'hybrid', 'dense', 'fusion'] = 'hybrid'
    generation: Literal['extractive', 'llm'] = 'extractive'
    top_k: int = Field(default=3, ge=1, le=5)

    @field_validator('as_of')
    @classmethod
    def no_future(cls, value):
        if value > date.today():
            raise ValueError('미래 기준일은 지원하지 않습니다.')
        return value

    @field_validator('question')
    @classmethod
    def question_not_blank(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('질문은 두 글자 이상 입력하세요.')
        return value


class SearchHit(BaseModel):
    chunk_id: str
    source_id: str
    institution: Institution
    title: str
    section: str
    url: str
    verified_at: str
    text: str
    score: float
    published_at: date | None = None
    content_as_of: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    temporal_basis: str = 'undated' 


class Claim(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=600)
    evidence_id: str
    quote: str = Field(min_length=5, max_length=500)


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    claims: list[Claim] = Field(min_length=1, max_length=3)


class AskResponse(BaseModel):
    request_id: str
    status: Literal['answered', 'clarify', 'not_found', 'blocked']
    answer: str
    claims: list[Claim] = []
    citations: list[SearchHit] = []
    generation: Literal['none', 'extractive', 'llm', 'extractive_fallback']
    reason: str
    corpus_version: str
    trace: list[dict]
    latency_ms: float
