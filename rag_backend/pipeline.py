from datetime import date
import re
import time
import uuid

from .generation import OpenAIGenerator, extractive_claims, verify_claims
from .models import AskRequest, AskResponse
from .retrieval import Retriever, institutions_for, topics_for

# Narrow documented heuristics, not a comprehensive prompt-injection or PII detector.
INJECTION = re.compile(r'시스템\s*프롬프트|이전\s*(지시|명령).*무시|ignore.{0,30}(instruction|previous)|reveal.{0,20}(prompt|secret)', re.I)
SENSITIVE = re.compile(r'(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)|(?:비밀번호|인증번호|password)\s*[:=은는]?\s*\d{4,8}', re.I)
PRIORITY = ('delivery', 'compensation', 'exchange_rate', 'reissue_fee', 'autopay', 'refund', 'installment', 'fee', 'limits', 'declined', 'registration', 'reissue', 'bulk', 'release', 'hours', 'overseas', 'report')


class Pipeline:
    def __init__(self, store, generator=None, dense_index=None):
        self.store = store
        self.chunks, self.version = store.load()
        self.retriever = Retriever(self.chunks)
        self.by_id = {c.id: c for c in self.chunks}
        self.generator = generator or OpenAIGenerator()
        self.dense_index = dense_index

    def search(self, question, institution, method, top_k, as_of=None, topic=None):
        as_of = as_of or date.today()
        eligible = [c for c in self.chunks if c.available_on(as_of) and (topic is None or topic in c.topics)]
        allowed = {c.id for c in eligible}
        lexical = Retriever(eligible)
        if method in ('dense', 'fusion'):
            if self.dense_index is None:
                raise ValueError('dense_not_configured')
            # Filter all dense candidates before top-k and RRF, avoiding temporal starvation.
            dense_hits = [h for h in self.dense_index.search(question, institution, len(self.chunks))
                          if h.chunk_id in allowed]
            if method == 'dense':
                return dense_hits[:top_k]
            from .dense import fuse_rankings
            lexical_hits = lexical.search(question, institution, 'hybrid', 20)
            return fuse_rankings([lexical_hits, dense_hits[:20]], top_k)
        return lexical.search(question, institution, method, top_k)

    def ask(self, req: AskRequest):
        start = time.perf_counter()
        trace = []
        request_id = str(uuid.uuid4())

        def finish(status, answer, reason, claims=None, hits=None, generation='none'):
            latency = round((time.perf_counter() - start) * 1000, 3)
            self.store.audit(request_id, status, reason, latency)
            return AskResponse(request_id=request_id, status=status, answer=answer,
                               reason=reason, claims=claims or [], citations=hits or [],
                               generation=generation, corpus_version=self.version,
                               trace=trace, latency_ms=latency)

        q = req.question
        if INJECTION.search(q):
            trace.append({'step': 'input_check', 'result': 'blocked_instruction_pattern'})
            return finish('blocked', '문서 이용안내에 관한 질문을 입력해주세요.', 'instruction_pattern')
        if SENSITIVE.search(q):
            trace.append({'step': 'input_check', 'result': 'sensitive_number_pattern'})
            return finish('blocked', '카드번호·비밀번호·인증번호를 제외하고 질문해주세요.', 'sensitive_number_pattern')

        topics = topics_for(q)
        trace.append({'step': 'route', 'topics': sorted(topics)})
        if not topics:
            return finish('not_found', '현재 문서에서 이 질문을 뒷받침할 근거를 찾지 못했습니다.', 'outside_corpus')
        mentioned = institutions_for(q)
        if any(name in q for name in ('삼성카드', '현대카드', '롯데카드', '하나은행', '우리은행', '신한은행')):
            return finish('not_found', '현재 corpus에는 해당 기관의 안내 문서가 없습니다.', 'unsupported_institution')
        if len(mentioned) > 1 or (req.institution and mentioned and mentioned != {req.institution}):
            return finish('clarify', '질문에 여러 기관이 있거나 선택한 기관과 다릅니다. 한 기관씩 질문해주세요.', 'conflicting_institution')
        institution = req.institution or next(iter(mentioned), None)
        if not institution:
            return finish('clarify', '어느 기관의 카드인가요? KB국민카드·KB증권·KB국민은행·신한카드 중 알려주세요.', 'missing_institution')
        # International reporting, not international spending, when both are present.
        topic = 'overseas_report' if 'report' in topics and 'overseas' in topics else next(t for t in PRIORITY if t in topics)
        trace.append({'step': 'scope', 'institution': institution, 'topic': topic})
        hits = self.search(q, institution, req.retriever, max(req.top_k, 5), req.as_of)
        trace.append({'step': 'retrieve', 'method': req.retriever,
                      'candidate_ids': [h.chunk_id for h in hits]})
        hits = [h for h in hits if topic in self.by_id[h.chunk_id].topics][:req.top_k]
        if not hits:
            return finish('not_found', '선택한 기관의 문서에서 해당 절차를 확인하지 못했습니다. 공식 고객센터에서 확인해주세요.', 'missing_topic_evidence')
        # Only extract the most relevant passage by default. Search endpoint exposes all candidates.
        evidence = hits[:1]
        generation = 'extractive'
        reason = 'grounded_excerpt'
        claims = extractive_claims(evidence)
        if req.generation == 'llm':
            if not self.generator.configured:
                raise ValueError('llm_not_configured')
            try:
                claims = self.generator.generate(q, evidence)
                generation = 'llm'
                reason = 'validated_llm_structure'
            except Exception:
                # Never expose provider response/error bodies or credentials.
                generation = 'extractive_fallback'
                reason = 'generation_failed_or_invalid_evidence'
        verify_claims(claims, evidence)
        used_ids = {c.evidence_id for c in claims}
        evidence = [h for h in evidence if h.chunk_id in used_ids]
        trace.append({'step': 'validate', 'evidence_ids': sorted(used_ids),
                      'checks': ['known_evidence_id', 'exact_supporting_quote', 'numeric_consistency'],
                      'semantic_entailment_checked': False})
        answer = '\n'.join(f'{claim.text} [{claim.evidence_id}]' for claim in claims)
        return finish('answered', answer, reason, claims, evidence, generation)
