"""Reproducible local retrieval/pipeline comparison. Never calls a paid API."""
import argparse
import hashlib
import json
import platform
import statistics
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .models import AskRequest
from .pipeline import Pipeline
from .retrieval import institutions_for
from .store import DocumentStore, ROOT


def evaluate(split, output, local_dense=False):
    dataset_path = ROOT / 'data' / 'evaluation.json'
    dataset_bytes = dataset_path.read_bytes()
    cases = [c for c in json.loads(dataset_bytes)['cases'] if c['split'] == split]
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'split': split,
              'dataset_sha256': hashlib.sha256(dataset_bytes).hexdigest(),
              'python': platform.python_version(), 'generation': 'extractive',
              'limits': ['수작업 소규모 corpus/질문; 외부 독립 벤치마크 아님',
                         '검색/라우팅/추출형 답변 평가; LLM 품질/환각률 평가 아님',
                         '로컬 파이프라인 시간; 네트워크/LLM 지연 제외'], 'runs': {}}
    with tempfile.TemporaryDirectory() as tmp:
        store = DocumentStore(Path(tmp) / 'eval.sqlite3')
        report['corpus_version'] = store.ingest()
        dense_index = None
        if local_dense:
            import time
            from .dense import DenseIndex, LocalEncoder
            start = time.perf_counter()
            dense_index = DenseIndex(store.load()[0], LocalEncoder(), ROOT / 'var' / 'eval-vectors.db')
            report['embedding'] = {'model': dense_index.encoder.name,
                                   'startup_seconds': round(time.perf_counter() - start, 3),
                                   'cache_hits': dense_index.cache_hits, 'new_embeddings': dense_index.new_embeddings}
        pipeline = Pipeline(store, dense_index=dense_index)
        methods = ('bm25', 'hybrid', 'dense', 'fusion') if local_dense else ('bm25', 'hybrid')
        for method in methods:
            rows = []
            for case in cases:
                req = AskRequest(question=case['question'], retriever=method)
                result = pipeline.ask(req)
                institution = next(iter(institutions_for(req.question)), None)
                raw_hits = pipeline.search(req.question, institution, method, 3) if case['gold'] else []
                rank = next((i for i, h in enumerate(raw_hits, 1) if h.chunk_id in case['gold']), None)
                evidence_correct = bool(case['gold']) and bool(result.citations) and all(h.chunk_id in case['gold'] for h in result.citations)
                status_correct = result.status == case['status']
                rows.append({'id': case['id'], 'category': case['category'], 'question': case['question'],
                             'expected_status': case['status'], 'actual_status': result.status,
                             'status_correct': status_correct, 'gold_ids': case['gold'],
                             'retrieved_ids': [h.chunk_id for h in raw_hits], 'first_relevant_rank': rank,
                             'evidence_ids': [h.chunk_id for h in result.citations],
                             'evidence_correct': evidence_correct if case['gold'] else None,
                             'end_to_end_correct': status_correct and (evidence_correct if case['gold'] else True),
                             'reason': result.reason, 'latency_ms': result.latency_ms})
            answerable = [row for row in rows if row['gold_ids']]
            unanswerable = [row for row in rows if not row['gold_ids']]
            latencies = sorted(r['latency_ms'] for r in rows)
            report['runs'][method] = {
                'summary': {'n': len(rows), 'answerable_n': len(answerable),
                    'hit_at_1': sum(r['first_relevant_rank'] == 1 for r in answerable) / max(len(answerable), 1),
                    'hit_at_3': sum(r['first_relevant_rank'] is not None for r in answerable) / max(len(answerable), 1),
                    'mrr_at_3': sum(1 / r['first_relevant_rank'] if r['first_relevant_rank'] else 0 for r in answerable) / max(len(answerable), 1),
                    'status_accuracy': statistics.mean(r['status_correct'] for r in rows),
                    'end_to_end_accuracy': statistics.mean(r['end_to_end_correct'] for r in rows),
                    'nonanswer_status_accuracy': statistics.mean(r['status_correct'] for r in unanswerable) if unanswerable else None,
                    'latency_p50_ms': statistics.median(latencies),
                    'latency_p95_ms': latencies[min(len(latencies) - 1, int(.95 * len(latencies)))]},
                'failures': [r for r in rows if not r['end_to_end_correct']], 'cases': rows}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    from .store import DEFAULT_CORPUS
    output.with_suffix('.corpus.json').write_bytes(DEFAULT_CORPUS.read_bytes())
    report['corpus_snapshot'] = output.with_suffix('.corpus.json').name
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = [f'# Retrieval experiment: {split}', '',
             f"Corpus: `{report['corpus_version']}`. Generation: **extractive, no LLM calls**.", '',
             '| Method | N | Answerable | Hit@1 | Hit@3 | MRR@3 | End-to-end | p50 ms |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for method, run in report['runs'].items():
        s = run['summary']
        lines.append(f"| {method} | {s['n']} | {s['answerable_n']} | {s['hit_at_1']:.3f} | {s['hit_at_3']:.3f} | {s['mrr_at_3']:.3f} | {s['end_to_end_accuracy']:.3f} | {s['latency_p50_ms']:.3f} |")
    lines += ['', '## Limits', '', *['- ' + limit for limit in report['limits']], '',
              '## Failures (retained, not filtered)', '']
    for method, run in report['runs'].items():
        lines.append(f"### {method}: {len(run['failures'])} failures")
        lines += [f"- {r['id']}: {r['question']} / {r['reason']} / evidence={r['evidence_ids']}" for r in run['failures']]
    output.with_suffix('.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({method: run['summary'] for method, run in report['runs'].items()}, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', choices=['dev', 'test'], default='dev')
    parser.add_argument('--output', default='reports/dev.json')
    parser.add_argument('--local-dense', action='store_true')
    args = parser.parse_args()
    evaluate(args.split, args.output, args.local_dense)
