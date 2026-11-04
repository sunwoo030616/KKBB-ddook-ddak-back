"""Partial encoder fine-tuning with explicit relative-relevance contrastive pairs.

The benchmark has already been inspected while designing this follow-up experiment;
results are exploratory, not a new blind test. No test questions or gold IDs enter loss.
"""
from datetime import datetime, timezone, date
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import re
import time

from .models import Chunk
from .retrieval import institutions_for
from .store import ROOT,DEFAULT_CORPUS


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(query):return re.sub(r'[^a-z0-9가-힣]','',query.lower())


def validate_pairs(rows,chunks,eval_queries):
    ids={c.id:c for c in chunks};seen=set();evaluation={normalized(q) for q in eval_queries}
    for row in rows:
        key=normalized(row['query'])
        if key in seen or key in evaluation:raise ValueError('duplicate_or_evaluation_query')
        seen.add(key)
        if row['positive_id']==row['less_direct_id']:raise ValueError('identical_pair')
        positive,negative=ids[row['positive_id']],ids[row['less_direct_id']]
        if positive.institution!=negative.institution:raise ValueError('cross_institution_negative')
    return {'training_queries':len(rows),'exact_normalized_query_overlap':0,
            'negative_policy':'same institution, human-labeled less-direct passage; not guaranteed irrelevant'}


def ranking_evaluation(model,chunks,cases):
    import numpy as np
    documents=[f'{c.title}\n{c.section}\n{c.text}' for c in chunks]
    vectors=model.encode(documents,batch_size=8,normalize_embeddings=True,show_progress_bar=False)
    queries=model.encode([c['question'] for c in cases],batch_size=8,normalize_embeddings=True,show_progress_bar=False)
    rows=[]
    for case,vector in zip(cases,queries):
        gold=set(case['gold_ids'])
        eligible=[i for i,c in enumerate(chunks) if c.institution in case['institutions'] and c.available_on(date.fromisoformat(case['as_of']))]
        ranked=sorted(eligible,key=lambda i:(-float(np.dot(vector,vectors[i])),chunks[i].id))
        ids=[chunks[i].id for i in ranked[:4]]
        rows.append({'id':case['id'],'question':case['question'],'gold_ids':case['gold_ids'], 'selected_ids':ids,
                     'hit_at_1':bool(gold.intersection(ids[:1])),
                     'recall_at_2':len(gold.intersection(ids[:2]))/len(gold),
                     'recall_at_4':len(gold.intersection(ids))/len(gold),
                     'all_evidence_at_4':gold.issubset(ids)})
    return {'n':len(rows),'hit_at_1':sum(r['hit_at_1'] for r in rows)/len(rows),
            'mean_recall_at_2':sum(r['recall_at_2'] for r in rows)/len(rows),
            'mean_recall_at_4':sum(r['recall_at_4'] for r in rows)/len(rows),
            'all_evidence_at_4':sum(r['all_evidence_at_4'] for r in rows)/len(rows),'cases':rows}


def train():
    import numpy as np
    import torch
    import torch.nn.functional as F
    from sentence_transformers import SentenceTransformer
    started=time.perf_counter()
    seed=20261103;random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    torch.set_num_threads(2)
    device='mps' if torch.backends.mps.is_available() else 'cpu'
    train_path=ROOT/'data'/'encoder_train.json';dataset=json.loads(train_path.read_text())
    chunks=[Chunk.model_validate(x) for x in json.loads(DEFAULT_CORPUS.read_text())['chunks']];by_id={c.id:c for c in chunks}
    research_path=ROOT/'data'/'research_questions.json';research=json.loads(research_path.read_text())['cases']
    legacy_path=ROOT/'data'/'evaluation.json';legacy=json.loads(legacy_path.read_text())['cases']
    checks=validate_pairs(dataset['cases'],chunks,[c['question'] for c in research+legacy])
    cases=[c for c in research if c['split']=='test' and c['gold_ids']]
    old=[{'id':c['id'],'question':c['question'],'gold_ids':c['gold'],
          'institutions':sorted(institutions_for(c['question'])),'as_of':'2026-11-02'}
         for c in legacy if c['split']=='test' and c['gold']]
    base=ROOT/'var'/'research_models'/'encoder_base'
    model=SentenceTransformer(str(base),device=device,local_files_only=True,trust_remote_code=False,
                              model_kwargs={'attn_implementation':'eager'})
    # Freeze most weights; only the last two transformer blocks receive gradients.
    for parameter in model.parameters():parameter.requires_grad=False
    for block in model[0].auto_model.encoder.layer[-2:]:
        for parameter in block.parameters():parameter.requires_grad=True
    model.max_seq_length=256
    parameters=[p for p in model.parameters() if p.requires_grad]
    report={'created_at':datetime.now(timezone.utc).isoformat(),'device':device,'seed':seed,
       'training_queries':len(dataset['cases']),'trainable_parameters':sum(p.numel() for p in parameters),
       'total_parameters':sum(p.numel() for p in model.parameters()),
       'training_dataset_sha256':digest(train_path),'research_dataset_sha256':digest(research_path),
       'legacy_dataset_sha256':digest(legacy_path),'corpus_sha256':digest(DEFAULT_CORPUS),
       'base_manifest':json.loads((base/'manifest.local.json').read_text()),'checks':checks,
       'hyperparameters':{'epochs':4,'batch_size':8,'learning_rate':2e-5,'temperature':0.05,
                          'max_seq_length':256,'attention_implementation':'eager (MPS training dropout support)','trainable_blocks':'encoder.layer[-2:]','loss':'two-way cosine softmax contrastive loss'},
       'limits':['52 same-author relative-relevance pairs; less-direct passages can still have partial relevance',
                 'Follow-up experiment designed after inspecting previous test results; exploratory reused evaluation',
                 'No exact normalized query overlap; shared corpus and semantic overlap remain',
                 'Single seed, small corpus, partial fine-tuning; no general finance-domain performance claim',
                 'PyTorch baseline and adapted model both use max length 256; previous ONNX timings/results are not identical experimental conditions'],
       'loss_history':[]}
    model.eval()
    with torch.no_grad():
        report['baseline']={'research_test':ranking_evaluation(model,chunks,cases),'legacy_test':ranking_evaluation(model,chunks,old)}
    optimizer=torch.optim.AdamW(parameters,lr=2e-5)
    rows=dataset['cases'];order=list(range(len(rows)))
    def encode_training(texts):
        batch={k:(v.to(device) if torch.is_tensor(v) else v) for k,v in model.preprocess(texts).items()}
        return F.normalize(model(batch)['sentence_embedding'],dim=1)
    for epoch in range(4):
        random.shuffle(order);model.train();values=[]
        for start in range(0,len(order),8):
            batch=[rows[i] for i in order[start:start+8]]
            positive=[by_id[r['positive_id']] for r in batch];negative=[by_id[r['less_direct_id']] for r in batch]
            texts=[r['query'] for r in batch]+[f'{c.title}\n{c.section}\n{c.text}' for c in positive+negative]
            embeddings=encode_training(texts);n=len(batch);q,p,h=embeddings[:n],embeddings[n:2*n],embeddings[2*n:]
            logits=torch.stack([(q*p).sum(1),(q*h).sum(1)],dim=1)/0.05
            loss=F.cross_entropy(logits,torch.zeros(n,dtype=torch.long,device=device))
            optimizer.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(parameters,1.0);optimizer.step()
            values.append(float(loss.detach().cpu()))
        report['loss_history'].append({'epoch':epoch+1,'mean_loss':sum(values)/len(values),'batch_losses':values})
        print(json.dumps(report['loss_history'][-1]),flush=True)
    model.eval()
    with torch.no_grad():
        report['adapted']={'research_test':ranking_evaluation(model,chunks,cases),'legacy_test':ranking_evaluation(model,chunks,old)}
    target=ROOT/'var'/'research_models'/'encoder_adapted';model.save_pretrained(str(target))
    model_sha=digest(target/'model.safetensors')
    metadata={'parent_repo':'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
              'parent_revision':report['base_manifest']['revision'],'weight_sha256':model_sha,
              'training_dataset_sha256':report['training_dataset_sha256'],'hyperparameters':report['hyperparameters'],
              'trainable_parameters':report['trainable_parameters']}
    (target/'manifest.local.json').write_text(json.dumps(metadata,indent=2)+'\n')
    report['adapted_manifest']=metadata;report['elapsed_seconds']=round(time.perf_counter()-started,3)
    output=ROOT/'reports'/'encoder-adaptation-v1.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    output.with_suffix('.train.json').write_bytes(train_path.read_bytes());output.with_suffix('.corpus.json').write_bytes(DEFAULT_CORPUS.read_bytes())
    print(json.dumps({'device':device,'trainable_parameters':report['trainable_parameters'],
                      'baseline':{k:{a:b for a,b in v.items() if a!='cases'} for k,v in report['baseline'].items()},
                      'adapted':{k:{a:b for a,b in v.items() if a!='cases'} for k,v in report['adapted'].items()},
                      'elapsed_seconds':report['elapsed_seconds']},ensure_ascii=False,indent=2),flush=True)
    return report


if __name__=='__main__':train()
