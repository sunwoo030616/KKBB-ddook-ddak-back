"""Content-addressed span embeddings and bounded deterministic score reuse.

Document embeddings can persist; user-query embeddings and raw query cache keys do not.
"""
from collections import OrderedDict
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from threading import Lock


class CachedReranker:
    def __init__(self,base,capacity=4096):
        if capacity<1:raise ValueError('positive_cache_capacity_required')
        self.base=base;self.capacity=capacity;self.cache=OrderedDict();self.lock=Lock()
        self.device=getattr(base,'device','unknown');self.dtype=getattr(base,'dtype','unknown')
        self.identity=getattr(base,'identity',{})
        self.stats={'requested_pairs':0,'computed_pairs':0,'reused_pairs':0}

    def score_pairs(self,pairs):
        keys=[hashlib.sha256(json.dumps(p,ensure_ascii=False).encode()).hexdigest() for p in pairs]
        with self.lock:
            self.stats['requested_pairs']+=len(pairs)
            missing={k:p for k,p in zip(keys,pairs) if k not in self.cache}
            values=self.base.score_pairs(list(missing.values())) if missing else []
            if len(values)!=len(missing):raise ValueError('reranker_count_mismatch')
            if not all(math.isfinite(v) for v in values):raise ValueError('nonfinite_reranker_score')
            fresh=dict(zip(missing,values));self.stats['computed_pairs']+=len(fresh)
            output=[self.cache[k] if k in self.cache else fresh[k] for k in keys]
            self.stats['reused_pairs']+=len(pairs)-len(fresh)
            for k,value in zip(keys,output):
                self.cache[k]=value;self.cache.move_to_end(k)
                while len(self.cache)>self.capacity:self.cache.popitem(last=False)
            return output

    def rerank(self,question,hits,top_k):
        scores=self.score_pairs([(question,f'{h.title}\n{h.section}\n{h.text}') for h in hits])
        ranked=sorted(zip(hits,scores),key=lambda x:(-x[1],x[0].chunk_id))
        return [h.model_copy(update={'score':score}) for h,score in ranked[:top_k]]


class SpanPrefilter:
    def __init__(self,encoder,path):
        self.encoder=encoder;self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=Lock();self.stats={'embedded_spans':0,'reused_spans':0,'query_embeddings':0}
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS spans(model TEXT,hash TEXT,vector TEXT,PRIMARY KEY(model,hash))')

    def vectors(self,texts):
        keys=[hashlib.sha256(t.encode()).hexdigest() for t in texts]
        with self.lock,sqlite3.connect(self.path) as db:
            cached={k:json.loads(row[0]) for k in set(keys)
                    if (row:=db.execute('SELECT vector FROM spans WHERE model=? AND hash=?',(self.encoder.name,k)).fetchone())}
            missing={k:t for k,t in zip(keys,texts) if k not in cached}
            values=self.encoder.encode(list(missing.values())) if missing else []
            if len(values)!=len(missing):raise ValueError('span_embedding_count_mismatch')
            for key,value in zip(missing,values):
                if not value or not all(math.isfinite(x) for x in value):raise ValueError('invalid_span_embedding')
                cached[key]=value
                db.execute('INSERT OR REPLACE INTO spans VALUES(?,?,?)',(self.encoder.name,key,json.dumps(value)))
            self.stats['embedded_spans']+=len(missing);self.stats['reused_spans']+=len(texts)-len(missing)
        return [cached[k] for k in keys]

    def select(self,query,spans,per_document=2):
        if per_document<1:raise ValueError('positive_span_budget_required')
        if not spans:return []
        vectors=self.vectors([span['text'] for doc,id,span in spans])
        q=self.encoder.encode([query])[0];self.stats['query_embeddings']+=1
        if not q or not all(math.isfinite(x) for x in q):raise ValueError('invalid_query_embedding')
        def cosine(v):
            if len(v)!=len(q):raise ValueError('span_vector_dimension_mismatch')
            denominator=math.sqrt(sum(x*x for x in q)*sum(x*x for x in v))
            return sum(x*y for x,y in zip(q,v))/denominator if denominator else 0
        ranked=sorted(zip(spans,vectors),key=lambda x:(-cosine(x[1]),x[0][0]['id'],x[0][1]))
        counts={};selected=[]
        for span,vector in ranked:
            id=span[0]['id']
            if counts.get(id,0)>=per_document:continue
            counts[id]=counts.get(id,0)+1;selected.append(span)
        return selected
