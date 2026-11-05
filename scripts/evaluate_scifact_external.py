"""External annotations, fixed subset; never an official full SciFact score."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def covered_length(intervals,start,end):
    clipped=sorted((max(start,a),min(end,b)) for a,b in intervals if a<end and b>start)
    total=0;last=start
    for a,b in clipped:
        if b>last:total+=b-max(a,last);last=b
    return total


def main():
    os.environ.update(OPENAI_API_KEY='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    protocol=json.loads((ROOT/'data/scifact_external_protocol.json').read_text());folder=ROOT/'var/scifact'
    for name,digest in protocol['sha256'].items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:raise ValueError('external_dataset_hash_changed')
    corpus={str(d['doc_id']):d for d in map(json.loads,(folder/'corpus.jsonl').read_text().splitlines())}
    claims={c['id']:c for c in map(json.loads,(folder/'claims_dev.jsonl').read_text().splitlines())}
    from rag_backend.knowledge_lab import KnowledgeStore
    from rag_backend.research_models import MLXGenerator
    from rag_backend.adaptive_literature import AdaptiveLiteratureAgent
    from rag_backend.retrieval_acceleration import SpanPrefilter,CachedReranker
    from rag_backend.dense import LocalEncoder
    from rag_backend.multilingual_literature import MultilingualLiteratureReranker
    from rag_backend.literature_reranker import EnglishLiteratureReranker
    store=KnowledgeStore(folder/'evaluation.sqlite3')
    store.ingest([{'id':'scifact:'+id,'title':corpus[id]['title'],'text':' '.join(corpus[id]['abstract']),
        'kind':'abstract','source_url':protocol['download'],'dataset':'SciFact','dataset_doc_id':id} for id in protocol['corpus_ids']])
    if len(store.documents())!=200:raise ValueError('external_corpus_mismatch')
    setup=time.perf_counter();generator=MLXGenerator('canvas_generator')
    agent=AdaptiveLiteratureAgent(store,CachedReranker(MultilingualLiteratureReranker()),
        SpanPrefilter(LocalEncoder(),folder/'vectors.sqlite3'),generator,
        english_reranker=CachedReranker(EnglishLiteratureReranker()))
    before={d['id']:d['content_hash'] for d in store.documents()}
    report={'scope':protocol['scope'],'protocol_sha256':hashlib.sha256((ROOT/'data/scifact_external_protocol.json').read_bytes()).hexdigest(),
        'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'backend_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'rag_backend').glob('*.py')},
        'generator':generator.identity,'paid_api_enabled':False,'source_hashes':before,'setup_seconds':time.perf_counter()-setup,
        'attribution':'SciFact: Wadden et al., Fact or Fiction: Verifying Scientific Claims. Claims/evidence CC BY 4.0; corpus S2ORC ODC-By 1.0. https://github.com/allenai/scifact',
        'rows':[]}
    path=ROOT/'reports/scifact-external-subset.json'
    for id in protocol['claim_ids']:
        case=claims[id];start=time.perf_counter();graph=agent.build(case['claim']);elapsed=time.perf_counter()-start
        actual=sorted({e['source_id'] for e in graph['edges']});expected=['scifact:'+d for d in sorted(case['evidence'])]
        coverages=[];sentence_hits=[];rationale_hits=[]
        for doc_id,alternatives in case['evidence'].items():
            sentences=corpus[doc_id]['abstract'];offsets=[];cursor=0
            for sentence in sentences:offsets.append((cursor,cursor+len(sentence)));cursor+=len(sentence)+1
            quotes=[(e['start'],e['end']) for e in graph['edges'] if e['source_id']=='scifact:'+doc_id]
            for alternative in alternatives:
                spans=[offsets[n] for n in alternative['sentences']]
                lengths=[covered_length(quotes,a,b) for a,b in spans]
                coverages.append(sum(lengths)/sum(b-a for a,b in spans))
                sentence_hits.append(any(length==b-a for length,(a,b) in zip(lengths,spans)))
                rationale_hits.append(all(length==b-a for length,(a,b) in zip(lengths,spans)))
        current={d['id']:d for d in store.documents()}
        quotes_valid=all(current[e['source_id']]['content_hash']==e['source_hash'] and
            current[e['source_id']]['text'][e['start']:e['end']]==e['text'] for e in graph['edges'])
        row={'claim_id':id,'claim_sha256':hashlib.sha256(case['claim'].encode()).hexdigest(),
            'expected_sources':expected,'actual_sources':actual,'document_hit':actual==expected,
            'best_gold_rationale_character_coverage':max(coverages,default=0),
            'any_gold_sentence_fully_covered':any(sentence_hits),'complete_gold_rationale_covered':any(rationale_hits),
            'quotes_valid':quotes_valid,'source_versions_current':graph['source_versions_current'],'seconds':elapsed,
            'status':graph['status'],'citation_count':len(graph['edges']),
            'edges':[{k:v for k,v in e.items() if k!='text'}|{'quote_sha256':hashlib.sha256(e['text'].encode()).hexdigest()} for e in graph['edges']],
            'trace':graph['trace']}
        report['rows'].append(row);path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(id,'doc',row['document_hit'],'rationale',round(row['best_gold_rationale_character_coverage'],3),round(elapsed,3),flush=True)
    rows=report['rows'];report.update(complete=True,summary={'n':len(rows),'document_hits':sum(r['document_hit'] for r in rows),
        'any_gold_sentence_fully_covered':sum(r['any_gold_sentence_fully_covered'] for r in rows),
        'complete_gold_rationale_covered':sum(r['complete_gold_rationale_covered'] for r in rows),
        'mean_best_gold_rationale_character_coverage':statistics.mean(r['best_gold_rationale_character_coverage'] for r in rows),
        'all_quotes_valid':all(r['quotes_valid'] for r in rows),'median_seconds':statistics.median(r['seconds'] for r in rows),
        'max_seconds':max(r['seconds'] for r in rows),'source_data_unchanged':before=={d['id']:d['content_hash'] for d in store.documents()}})
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
