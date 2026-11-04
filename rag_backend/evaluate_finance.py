"""Exploratory temporal ablation on explicit dated-policy cases, not a blind benchmark."""
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from fastapi.encoders import jsonable_encoder
import tempfile

from .dense import DenseIndex, LocalEncoder, fuse_rankings
from .finance import FinanceRequest, analyze
from .pipeline import Pipeline
from .retrieval import Retriever
from .store import DEFAULT_CORPUS, DocumentStore, ROOT


def evaluate():
    methods = ('bm25','hybrid','dense','fusion')
    dates = [('2025-07-21',None), ('2025-07-22','fsc-protection-before'),
             ('2025-08-30','fsc-protection-before'),('2025-08-31','fsc-protection-before'),
             ('2025-09-01','fsc-protection-current'),('2025-09-02','fsc-protection-current'),
             ('2026-11-02','fsc-protection-current')]
    queries = ['예금보호한도 원금 이자','예금자보호 얼마까지 보호되나요',
               '원금과 이자 합해서 예금 보호 한도', '예금보험 한도 알려줘']
    cases = [{'as_of':day,'question':q,'gold_id':gold} for day,gold in dates for q in queries]
    report = {'created_at':datetime.now(timezone.utc).isoformat(),
              'limits':['28개는 7개 날짜와 4개 표현을 조합한 상관된 탐색적 사례; 독립 표본 28개가 아님',
                        '공식 출처 2개/정답 청크 2개의 좁은 제도 사례',
                        '분류·검색 평가이며 생성 LLM·실상품 지급 판정 평가 아님',
                        '무기한 effective_until은 최신 정책 자동 확인을 의미하지 않음'],
              'dataset_sha256':hashlib.sha256(json.dumps(cases,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
              'runs':{}}
    with tempfile.TemporaryDirectory() as tmp:
        store = DocumentStore(Path(tmp)/'finance.db')
        report['corpus_version'] = store.ingest()
        chunks,_ = store.load()
        dense = DenseIndex(chunks,LocalEncoder(),ROOT/'var'/'eval-vectors.db')
        report['embedding_model'] = dense.encoder.name
        pipeline = Pipeline(store,dense_index=dense)
        # Same institutional/topic scope and ranking rules; only date filtering differs.
        scoped = [c for c in chunks if c.institution=='fsc' and 'protection' in c.topics]
        lexical = Retriever(scoped)
        for method in methods:
            rows = []
            for case in cases:
                if method in ('dense','fusion'):
                    raw = dense.search(case['question'],'fsc',len(chunks))
                    baseline = raw if method=='dense' else fuse_rankings([lexical.search(case['question'],'fsc','hybrid',20),raw],20)
                else:
                    baseline = lexical.search(case['question'],'fsc',method,20)
                filtered = pipeline.search(case['question'],'fsc',method,1,date.fromisoformat(case['as_of']),topic='protection')
                without = baseline[0].chunk_id if baseline else None
                with_filter = filtered[0].chunk_id if filtered else None
                rows.append(case | {'without_temporal_filter':without, 'with_temporal_filter':with_filter,
                                    'baseline_correct':without==case['gold_id'],
                                    'filtered_correct':with_filter==case['gold_id']})
            report['runs'][method] = {'n':len(rows), 'without_filter_correct':sum(c['baseline_correct'] for c in rows),
                                      'with_filter_correct':sum(c['filtered_correct'] for c in rows),'cases':rows}
        examples = [
            FinanceRequest(topics=['protection'],as_of='2025-08-31'),
            FinanceRequest(topics=['protection'],as_of='2025-09-01'),
            FinanceRequest(topics=['protection','collateral','funding_compare']),
            FinanceRequest(topics=['protection','collateral'],as_of='2025-09-01'),
            FinanceRequest(topics=['funding_compare','funding_inputs'],calculation={
                'kind':'funding_comparison','maturity_interest_net_won':'1000000',
                'early_interest_net_won':'300000','loan_principal_won':'10000000',
                'annual_loan_rate_percent':'3.65','loan_days':100,'extra_loan_cost_won':'10000'}),
        ]
        report['workflow_examples'] = [{'request':r.model_dump(mode='json'),'response':analyze(pipeline,r)} for r in examples]
    output = ROOT/'reports'/'finance-temporal-v1.json'
    output.write_text(json.dumps(jsonable_encoder(report),ensure_ascii=False,indent=2)+'\n')
    output.with_suffix('.corpus.json').write_bytes(DEFAULT_CORPUS.read_bytes())
    lines = ['# Financial temporal retrieval ablation','', f"Corpus: `{report['corpus_version']}`",'',
             '| Method | Cases | Without date scope | With date scope |', '| --- | ---: | ---: | ---: |']
    for method,r in report['runs'].items():
        lines.append(f"| {method} | {r['n']} | {r['without_filter_correct']} | {r['with_filter_correct']} |")
    lines += ['','## Limits','', *['- '+v for v in report['limits']], '',
              'ケースごとの失敗とワークフロー出力は同名 JSON に保存。']
    lines[-1]='각 사례의 실패와 실제 워크플로 출력은 같은 이름의 JSON 파일에 보존했습니다.'
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({m:{k:v for k,v in r.items() if k!='cases'} for m,r in report['runs'].items()},ensure_ascii=False,indent=2))


if __name__=='__main__':
    evaluate()
