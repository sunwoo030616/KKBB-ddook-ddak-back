"""Actual-model ablation. No gold evidence is provided to any model prompt."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import tempfile
import time

from fastapi.encoders import jsonable_encoder

from .pipeline import Pipeline
from .research import ResearchPipeline, ResearchRequest
from .research_models import MLXGenerator,CrossEncoderReranker
from .store import ROOT,DEFAULT_CORPUS,DocumentStore

VARIANTS={'baseline':(False,False,False),'rerank':(False,True,False),'decompose':(True,False,False),'decompose_rerank':(True,True,False),'neural_gate':(True,True,True)}
# Declared before test model inference. Balanced pilot generation subset, not selected on results.
GENERATION_CASES={'t01','t02','t04','t05','t06','t07','t09','t12'}


def average(values):return statistics.mean(values) if values else None


def evaluate(split='dev',output=None):
    dataset=ROOT/'data'/'research_questions.json';raw=dataset.read_bytes()
    cases=[c for c in json.loads(raw)['cases'] if c['split']==split]
    output=Path(output or ROOT/'reports'/f'research-{split}-v1.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    generator=MLXGenerator();reranker=CrossEncoderReranker()
    report={'created_at':datetime.now(timezone.utc).isoformat(),'split':split,'evaluation_k':[2,4],
       'dataset_sha256':hashlib.sha256(raw).hexdigest(), 'dataset_snapshot':output.with_suffix('.questions.json').name,
       'relevance_calibration':json.loads((ROOT/'data'/'research_calibration.json').read_text()),
       'models':{'generator':generator.identity,'reranker':reranker.identity},
       'environment':{'python':platform.python_version(),'platform':platform.platform(),
                      'packages':{p:importlib.metadata.version(p) for p in ['mlx','mlx-lm','sentence-transformers','torch','outlines']}},
       'generation_case_ids':sorted(GENERATION_CASES) if split=='test' else [c['id'] for c in cases],
       'limits':['Small same-author hand-labeled dataset and 26 reviewed paraphrases, not independent financial benchmark',
                 'Test generation subset declared before inference; retrieval evaluated on all test cases',
                 'Citation validity and gold evidence coverage do not establish semantic entailment or financial advice accuracy',
                 'Greedy local generation, constrained JSON decoding; no model training or new research-method claim',
                 'Single run; no confidence intervals or cross-model generalization claim'],
       'cases':[],'summary':{}}
    output.with_suffix('.questions.json').write_bytes(raw)
    output.with_suffix('.corpus.json').write_bytes(DEFAULT_CORPUS.read_bytes())
    with tempfile.TemporaryDirectory() as tmp:
        store=DocumentStore(Path(tmp)/'research.db');report['corpus_version']=store.ingest()
        pipeline=Pipeline(store);engine=ResearchPipeline(pipeline,generator,reranker)
        for case in cases:
            req=ResearchRequest(question=case['question'],institutions=case['institutions'],as_of=case['as_of'],top_k=4)
            plan_start=time.perf_counter();subqueries,plan=engine.plan(req.question)
            plan_time=(time.perf_counter()-plan_start)*1000
            row=dict(case,plan=plan,subqueries=subqueries,variants={})
            for variant,(decompose,do_rerank,gate) in VARIANTS.items():
                variant_start=time.perf_counter()
                selected,candidates=engine.retrieve(req.model_copy(update={'rerank':do_rerank,'evidence_gate':gate}),subqueries if decompose else [])
                retrieval_ms=(time.perf_counter()-variant_start)*1000
                ids=[h.chunk_id for h in selected];gold=set(case['gold_ids'])
                values={'selected_ids':ids,'candidate_ids':[h.chunk_id for h in candidates],
                        'scores':[h.score for h in selected],
                        'recall_at_2':len(gold.intersection(ids[:2]))/len(gold) if gold else None,
                        'recall_at_4':len(gold.intersection(ids))/len(gold) if gold else None,
                        'all_evidence_at_4':gold.issubset(ids) if gold else None,
                        'retrieval_ms':round(retrieval_ms,3),
                        'retrieval_plus_plan_ms':round(retrieval_ms+(plan_time if decompose else 0),3)}
                if variant in ('baseline','decompose_rerank','neural_gate') and (split=='dev' or case['id'] in GENERATION_CASES):
                    answer,raw_answer=engine.synthesize(req.question,selected)
                    claims=answer.claims if answer is not None else []
                    emitted={c.evidence_id for c in claims}
                    answered=bool(answer and answer.answerable)
                    values['generation']={'raw':raw_answer,'claims':claims,'answered':answered,
                        'answerability_correct':answered==bool(gold),
                        'complete_evidence_coverage':bool(answered and gold.issubset(emitted)) if gold else None,
                        'emitted_evidence_precision':len(gold.intersection(emitted))/len(emitted) if emitted else None,
                        'schema_and_citation_valid':answer is not None if selected else None,
                        'llm_called':bool(selected),
                        'status': 'answered' if answered else 'invalid_output' if answer is None and selected else 'abstained'}
                row['variants'][variant]=values
            report['cases'].append(row)
            # Checkpoint synthetic experiment outputs, allowing inspection and preserving failures.
            output.write_text(json.dumps(jsonable_encoder(report),ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({'id':case['id'],'plan_status':plan['status'],
                'retrieval':{v:{'recall4':r['recall_at_4'],'gen':r.get('generation',{}).get('status')} for v,r in row['variants'].items()}},ensure_ascii=False),flush=True)
    for variant in VARIANTS:
        results=[c['variants'][variant] for c in report['cases']]
        answerable=[r for r in results if r['recall_at_4'] is not None]
        generated=[r['generation'] for r in results if 'generation' in r]
        report['summary'][variant]={'retrieval_n':len(results),'answerable_n':len(answerable),
            'mean_recall_at_2':average([r['recall_at_2'] for r in answerable]),
            'mean_recall_at_4':average([r['recall_at_4'] for r in answerable]),
            'all_evidence_at_4':average([r['all_evidence_at_4'] for r in answerable]),
            'retrieval_plus_plan_p50_ms':statistics.median([r['retrieval_plus_plan_ms'] for r in results]),
            'generated_n':len(generated),'actual_generation_calls':sum(g['llm_called'] for g in generated),
            'answerability_accuracy':average([g['answerability_correct'] for g in generated]),
            'complete_generation_evidence_coverage':average([g['complete_evidence_coverage'] for g in generated if g['complete_evidence_coverage'] is not None]),
            'valid_generated_structure_and_citations':average([g['schema_and_citation_valid'] for g in generated if g['schema_and_citation_valid'] is not None])}
    report['plan_valid_rate']=average([c['plan']['status']=='valid' for c in report['cases']])
    report['elapsed_seconds']=round(time.perf_counter()-started,3)
    output.write_text(json.dumps(jsonable_encoder(report),ensure_ascii=False,indent=2)+'\n')
    lines=[f'# Local neural RAG ablation ({split})','',f"Corpus `{report['corpus_version']}`; actual local MLX + cross-encoder execution.",'',
           '| Variant | Answerable N | Recall@2 | Recall@4 | All evidence@4 | p50 ms incl plan |',
           '| --- | ---: | ---: | ---: | ---: | ---: |']
    for variant,s in report['summary'].items():
        lines.append(f"| {variant} | {s['answerable_n']} | {s['mean_recall_at_2']:.3f} | {s['mean_recall_at_4']:.3f} | {s['all_evidence_at_4']:.3f} | {s['retrieval_plus_plan_p50_ms']:.1f} |")
    lines += ['', '## Generation pilot','', '| Variant | N | Answerability | Valid structure/citations | Complete gold evidence coverage |', '| --- | ---: | ---: | ---: | ---: |']
    for variant,s in report['summary'].items():
        if s['generated_n']:
            lines.append(f"| {variant} | {s['generated_n']} | {s['answerability_accuracy']:.3f} | {s['valid_generated_structure_and_citations']:.3f} | {s['complete_generation_evidence_coverage']:.3f} |")
    lines += ['','## Limits','',*['- '+x for x in report['limits']],'',
              'Every question, plan, selected ID, raw synthetic generation and failure is retained in the JSON report.']
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['dev','test'],default='dev');p.add_argument('--output')
    args=p.parse_args();evaluate(args.split,args.output)
