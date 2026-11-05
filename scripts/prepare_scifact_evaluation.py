"""Freeze a small externally annotated dataset subset before observing results."""
import hashlib
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[1]
SEED=20261105


def main():
    folder=ROOT/'var/scifact'
    raw={name:(folder/name).read_bytes() for name in ['corpus.jsonl','claims_dev.jsonl','data.tar.gz']}
    corpus={str(d['doc_id']):d for d in map(json.loads,raw['corpus.jsonl'].splitlines())}
    claims=list(map(json.loads,raw['claims_dev.jsonl'].splitlines()))
    eligible=[c for c in claims if len(c['evidence'])==1 and
        all(e['label']=='SUPPORT' for evidence in c['evidence'].values() for e in evidence)]
    rng=random.Random(SEED);selected=sorted(rng.sample(sorted(eligible,key=lambda c:c['id']),10),key=lambda c:c['id'])
    positives={id for c in selected for id in c['evidence']}
    remaining=sorted(set(corpus)-positives)
    ids=sorted(positives|set(rng.sample(remaining,200-len(positives))))
    protocol={'version':1,'source':'https://github.com/allenai/scifact','download':'https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz',
        'scope':'External researcher-annotated SciFact dev SUPPORT-only subset: 10 single-positive claims, 200-document corpus containing positives plus seeded random distractors. Not full SciFact, not official leaderboard metric, no CONTRADICT/NEI classification or Korean/financial-domain claim.',
        'seed':SEED,'claim_ids':[c['id'] for c in selected],'corpus_ids':ids,
        'sha256':{name:hashlib.sha256(data).hexdigest() for name,data in raw.items()},
        'metrics':['document_hit','exact_quote_offsets','gold_rationale_character_coverage','at_least_one_gold_sentence_fully_covered','latency_seconds'],
        'selection_policy':'Frozen before model output; no tuning on results; gold labels never passed to generator/retriever.'}
    out=ROOT/'data/scifact_external_protocol.json'
    if out.exists() and json.loads(out.read_text())!=protocol:raise ValueError('external_protocol_changed')
    out.write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
    print('frozen',len(selected),'claims',len(ids),'documents')

if __name__=='__main__':main()
