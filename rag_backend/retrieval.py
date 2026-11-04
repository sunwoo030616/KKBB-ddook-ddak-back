"""BM25 baseline vs BM25 + Korean character TF-IDF with RRF.

Both are lexical retrievers. Character vectors are NOT neural embeddings.
Metadata scope is applied before ranking for both methods.
"""
import math
import re
from collections import Counter

from .models import Chunk, SearchHit

TOPICS = {
    'hours': ('주말', '일요일', '공휴일', '24시간', '밤', '언제 신고', '신고 시간'),
    'bulk': ('지갑', '일괄', '여러 카드', '여러카드', '한꺼번에', '통째로'),
    'delivery': ('배송', '도착', '며칠 걸', '소요기간', '소요 기간'),
    'compensation': ('보상', '배상'),
    'exchange_rate': ('환율',),
    'reissue_fee': ('재발급 수수료', '재발급수수료', '재발급 비용', '재발급비용'),
    'report': ('분실', '잃어', '잃었', '도난', '신고'),
    'release': ('해제', '풀어', '풀려', '풀고', '찾았', '되찾', '재사용', '다시 쓰', '다시 사용'),
    'reissue': ('재발급', '다시 발급', '새로 발급', '새 카드'),
    'overseas': ('해외', '외국', '일본', '중국', '미국', '출국', '외화'),
    'refund': ('환불', '승인취소', '승인 취소', '결제 취소', '결제취소', '입금'),
    'fee': ('연회비',),
    'installment': ('할부',),
    'declined': ('거절', '잔액 부족', '잔고 부족', '잔액부족', '결제 안', '결제가 안'),
    'autopay': ('자동납부', '자동 납부', '자동이체', '통신요금', '통신 요금'),
    'registration': ('사용등록', '사용 등록', '수령', '받았'),
    'limits': ('한도',),
}
ALIASES = {
    'kb_securities': ('kb증권', 'kb 증권', '케이비증권', '국민증권'),
    'kb_card': ('kb국민카드', 'kb 국민카드', '국민카드', 'kb pay', 'kbpay', 'kb페이', 'kb 페이', '케이비페이'),
    'kb_bank': ('kb국민은행', '국민은행', 'kb스타뱅킹', '스타뱅킹', '보안카드', 'otp'),
    'shinhan_card': ('신한카드', '신한 카드'),
}


def topics_for(question: str):
    return {topic for topic, forms in TOPICS.items() if any(f in question.lower() for f in forms)}


def institutions_for(question):
    lower = question.lower()
    return {inst for inst, forms in ALIASES.items() if any(form in lower for form in forms)}


def tokens(text):
    return re.findall(r'[a-z0-9]+|[가-힣]+', text.lower())


def char_tokens(text):
    # Keep Korean spacing-independent matches; do not concatenate across sentences.
    words = re.findall(r'[a-z0-9가-힣]+', text.lower())
    return [word[i:i + n] for word in words for n in (2, 3) for i in range(len(word) - n + 1)]


def bm25(query, documents):
    doc_tokens = [tokens(text) for text in documents]
    avg = sum(map(len, doc_tokens)) / max(len(doc_tokens), 1)
    scores = []
    for terms in doc_tokens:
        counts = Counter(terms)
        score = 0.0
        for term in set(tokens(query)):
            df = sum(term in doc for doc in doc_tokens)
            idf = math.log(1 + (len(doc_tokens) - df + .5) / (df + .5))
            tf = counts[term]
            score += idf * tf * 2.5 / (tf + 1.5 * (.25 + .75 * len(terms) / max(avg, 1)))
        scores.append(score)
    return scores


def char_cosines(query, documents):
    counters = [Counter(char_tokens(text)) for text in documents]
    q = Counter(char_tokens(query))
    vocab = set(q).union(*(set(c) for c in counters))
    idf = {t: math.log((1 + len(counters)) / (1 + sum(t in c for c in counters))) + 1 for t in vocab}

    def vector(c):
        return {t: (1 + math.log(v)) * idf[t] for t, v in c.items()}

    qv = vector(q)
    qnorm = math.sqrt(sum(v * v for v in qv.values()))
    scores = []
    for c in counters:
        dv = vector(c)
        norm = math.sqrt(sum(v * v for v in dv.values()))
        scores.append(sum(v * dv.get(t, 0) for t, v in qv.items()) / (qnorm * norm) if qnorm * norm else 0)
    return scores


class Retriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks

    def search(self, question, institution=None, method='hybrid', top_k=3):
        chunks = [c for c in self.chunks if not institution or c.institution == institution]
        if not chunks:
            return []
        documents = [f'{c.title} {c.section} {c.text}' for c in chunks]
        query = question
        if method == 'hybrid':
            query += ' ' + ' '.join(TOPICS[t][0] for t in sorted(topics_for(question)))
            documents = [d + ' ' + ' '.join(c.keywords) for d, c in zip(documents, chunks)]
        sparse = bm25(query, documents)
        if method == 'bm25':
            scores = sparse
        else:
            char = char_cosines(query, documents)
            scores = [0.0] * len(chunks)
            for ranking in (sparse, char):
                for rank, i in enumerate(sorted(range(len(chunks)), key=lambda i: (-ranking[i], chunks[i].id)), 1):
                    if ranking[i] > 0:
                        scores[i] += 1 / (60 + rank)
        ranked = sorted(range(len(chunks)), key=lambda i: (-scores[i], chunks[i].id))
        return [SearchHit(chunk_id=c.id, source_id=c.source_id, institution=c.institution,
                          title=c.title, section=c.section, url=str(c.url), verified_at=c.verified_at.isoformat(),
                          text=c.text, published_at=c.published_at, content_as_of=c.content_as_of, effective_from=c.effective_from,
                          effective_until=c.effective_until, temporal_basis=c.temporal_basis, score=round(scores[i], 8))
                for i in ranked[:top_k] if scores[i] > 0 for c in [chunks[i]]]
