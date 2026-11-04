"""Direct multilingual retrieval with one bounded ambiguity adjudication.

The model never writes source IDs/quotes. High-margin retrieval can bypass it;
uncertain tasks share one fixed-schema call, using original request clauses.
"""
import hashlib
import json
import math
import re
import time
from typing import Literal

from pydantic import ConfigDict,Field,create_model

from .evidence_graph import EvidenceGraph,GENERATION_FIELDS,measurement_entities,mentions_entities
from .prompt_registry import load_prompt
from .request_anchors import request_anchors
from .research import parse_json
from .research_passages import contribution_passages,context_passages
from .literature_qualifiers import QualifierPolicy
from .research_scope import requests_catalog_mutation


class AdaptiveLiteratureAgent:
    def __init__(self,store,reranker,prefilter,generator=None,min_score=0.,min_margin=1.,
                 max_candidates=5,context_chars=480,english_reranker=None,min_direct_passage_score=-2.,prompt_version='3',min_candidate_score=-6.):
        if not 1<=max_candidates<=5 or not 80<=context_chars<=1000:raise ValueError('invalid_agent_budget')
        if not all(math.isfinite(x) for x in (min_score,min_margin,min_direct_passage_score,min_candidate_score)) or min_margin<0:raise ValueError('invalid_agent_confidence')
        if prompt_version!='3':raise ValueError('unsupported_adjudication_contract')
        self.store=store;self.reranker=reranker;self.prefilter=prefilter;self.generator=generator
        self.min_score=min_score;self.min_margin=min_margin;self.max_candidates=max_candidates;self.context_chars=context_chars
        self.english_reranker=english_reranker;self.qualifiers=QualifierPolicy();self.min_direct_passage_score=min_direct_passage_score
        self.prompt_version=prompt_version
        self.min_candidate_score=min_candidate_score

    def build(self,question):
        started=time.perf_counter()
        if requests_catalog_mutation(question):
            return {'status':'out_of_scope','tasks':[],'edges':[],'missing_task_ids':[],
                'source_versions_current':True,'trace':[{'step':'request_scope_guard','model_calls':0,'decision':'rejected_mutation'}],
                'latency_ms':round((time.perf_counter()-started)*1000,3),
                'scope':'This endpoint retrieves research candidates and does not approve, publish or delete knowledge.'}
        anchors=request_anchors(question);corpus=self.store.documents('abstract')
        trace=[{'step':'request_anchors','count':len(anchors),'model_calls':0}];tasks=[];options={};documents={};choices={};uncertain=[]
        for i,anchor in enumerate(anchors):
            begin=time.perf_counter();text=anchor['text'];entities=measurement_entities(text,text)
            allowed=[d for d in corpus if mentions_entities(d['title']+'\n'+d['text'],entities)] if entities else corpus
            if entities:trace.append({'step':'measurement_source_presence','task_id':f't{i}','entities':entities,
                'eligible_documents':len(allowed),'model_calls':0})
            qualifiers=self.qualifiers.constraints(text)
            required_span_qualifiers=self.qualifiers.span_constraints(qualifiers)
            method_request=bool(any(name=='interleaved_actions' for name,p in qualifiers) or
                re.search(r'방법|방식|기법|\bmethod\b|\bframework\b|\balgorithm\b|work combining|\bapproach\b',text,re.I))
            if qualifiers:
                allowed=[d for d in allowed if self.qualifiers.matches(d['title']+'\n'+d['text'],qualifiers)]
                trace.append({'step':'explicit_qualifiers','task_id':f't{i}','rules':[name for name,p in qualifiers],
                    'eligible_documents':len(allowed),'policy':self.qualifiers.identity,'model_calls':0,
                    'scope':'Necessary lexical presence only. Conservative domain heuristics, not general semantic parsing.'})
            ranker=self.english_reranker if text.isascii() and self.english_reranker is not None else self.reranker
            # Reserve title and abstract views separately, then rerank their union.
            if self.prefilter is not None and len(allowed)>64:
                title_view=self.prefilter.select(text,[(d,'title',{'text':d['title']}) for d in allowed],per_document=1)[:5]
                body_view=self.prefilter.select(text,[(d,'body',{'text':d['title']+'\n'+d['text']}) for d in allowed],per_document=1)[:15]
                pool=list({d['id']:d for d,id,span in title_view+body_view}.values())
            else:pool=allowed
            scores=ranker.score_pairs([(text,d['title']+'\n'+d['text']) for d in pool]) if pool else []
            if len(scores)!=len(pool) or not all(math.isfinite(s) for s in scores):raise ValueError('invalid_document_scores')
            ranked=[(d,s) for d,s in sorted(zip(pool,scores),key=lambda item:(-item[1],item[0]['id']))
                    if s>=self.min_candidate_score][:self.max_candidates]
            options[i]=[];documents.update({d['id']:d for d,s in ranked})
            all_spans=[]
            for doc,score in ranked:
                spans=contribution_passages(doc['text'],max_chars=self.context_chars) if method_request else {
                    id:{**span,'evidence_role':'abstract_context'} for id,span in context_passages(doc['text'],max_chars=self.context_chars).items()}
                all_spans.extend((doc,span_id,span) for span_id,span in spans.items())
            span_scores=ranker.score_pairs([(text,span['text']) for doc,id,span in all_spans]) if all_spans else []
            if len(span_scores)!=len(all_spans) or not all(math.isfinite(s) for s in span_scores):raise ValueError('invalid_passage_scores')
            best_spans={}
            for (doc,span_id,span),score in zip(all_spans,span_scores):
                coverage=self.qualifiers.coverage(span['text'],qualifiers)
                if doc['id'] not in best_spans or (coverage,score)>(best_spans[doc['id']][3],best_spans[doc['id']][2]):best_spans[doc['id']]=(span_id,span,float(score),coverage)
            for doc,score in ranked:
                if doc['id'] in best_spans:
                    span_id,span,span_score,coverage=best_spans[doc['id']]
                    if not self.qualifiers.matches(span['text'],required_span_qualifiers):continue
                    if method_request and span['evidence_role']=='author_claim_context':
                        claim=doc['text'][span['claim_start']:span['claim_end']]
                        if not self.qualifiers.matches(claim,required_span_qualifiers):continue
                    options[i].append({'document':doc,'span_id':span_id,'span':span,'document_score':float(score),'passage_score':span_score})
            margin=options[i][0]['document_score']-options[i][1]['document_score'] if len(options[i])>1 else None
            direct=bool(options[i] and options[i][0]['document_score']>=self.min_score and options[i][0]['passage_score']>=self.min_direct_passage_score
                        and (not method_request or options[i][0]['span']['evidence_role']=='author_claim_context')
                        and (margin is None or margin>=self.min_margin))
            if direct:choices[i]=0
            elif options[i]:uncertain.append(i)
            else:choices[i]=-1
            tasks.append({'id':f't{i}','request_quote':text,'query':text,'anchor_scope':'exact_quote',
                'anchor_start':anchor['start'],'anchor_end':anchor['end']})
            trace.append({'step':'multilingual_retrieval','task_id':f't{i}','candidate_documents':len(pool),
                'candidate_strategy':'exhaustive_small_corpus' if len(allowed)<=64 else 'bounded_multiview',
                'candidate_source_ids':[d['id'] for d in pool],
                'scored_passages':len(all_spans),'latency_ms':round((time.perf_counter()-begin)*1000,3),
                'direct':direct,'document_margin':float(margin) if margin is not None else None,
                'ranker':ranker.identity if hasattr(ranker,'identity') else {},
                'passage_profile':'author_claim_context' if method_request else 'abstract_context',
                'candidate_score_floor':self.min_candidate_score,
                'candidates':[{'source_id':c['document']['id'],'document_score':c['document_score'],'passage_score':c['passage_score']} for c in options[i]],
                'model_calls':0,'scope':'Raw ranking logits, not calibrated truth probabilities.'})
        if uncertain:
            if self.generator is None:
                choices.update({i:-1 for i in uncertain});trace.append({'step':'adjudicate','status':'unavailable_abstained','model_calls':0})
            else:
                prompt=load_prompt('literature_adjudication',self.prompt_version)
                slots={i:list('abcde')[:len(options[i])] for i in uncertain}
                schema=create_model('LiteratureDecisions',__config__=ConfigDict(extra='forbid'),
                    **{f't{i}':(list[Literal[tuple(slots[i])]],Field(max_length=len(slots[i]))) for i in uncertain})
                payload={'tasks':[{'id':f't{i}','request_quote':anchors[i]['text'],'allowed_slots':slots[i],'candidates':[
                    {'slot':slots[i][j],'title':c['document']['title'][:180],'passage':c['span']['text'],'evidence_role':c['span']['evidence_role']}
                    for j,c in enumerate(options[i])]} for i in uncertain]}
                completed_calls=0;attempted=False
                try:
                    user_payload=json.dumps(payload,ensure_ascii=False)
                    if len(user_payload)>10000:raise ValueError('adjudication_context_budget')
                    attempted=True
                    raw=self.generator.complete(prompt['text'],user_payload,max_tokens=120,output_type=schema)
                    completed_calls=raw.get('model_calls',1)
                    decoded=parse_json(raw['text'])
                    selected=schema.model_validate(decoded).model_dump()
                    if any(len(values)!=len(set(values)) for values in selected.values()):raise ValueError('duplicate_support_slots')
                    # The verifier cannot reorder supporting sources. Preserve
                    # retrieval rank among all candidates marked as supported.
                    choices.update({i:next((j for j,slot in enumerate(slots[i]) if slot in selected[f't{i}']),-1) for i in uncertain})
                    trace.append({'step':'adjudicate','status':'validated','prompt_version':prompt['version'],'prompt_sha256':prompt['sha256'],
                        'selected_slots':selected,'input_chars':len(user_payload),'generation_prompt_sha256':raw.get('prompt_sha256'),
                        **{k:raw.get(k) for k in GENERATION_FIELDS if k!='prompt_sha256'},'model_calls':completed_calls})
                except (ValueError,TypeError,KeyError):
                    choices.update({i:-1 for i in uncertain});trace.append({'step':'adjudicate','status':'invalid_abstained',
                        'model_calls':completed_calls,'generation_attempted':attempted,'error_code':'context_or_schema_contract_failed',
                        'scope':'Completed generation returns counted; exceptions during a model call have unknown execution cost.'})
        edges=[];missing=[]
        for i in range(len(anchors)):
            choice=choices.get(i,-1)
            if choice<0:missing.append(f't{i}');continue
            candidate=options[i][choice];doc=candidate['document']
            edges.append({'task_id':f't{i}','evidence_id':f'e{len(edges)}','source_id':doc['id'],'source_hash':doc['content_hash'],
                'title':doc['title'],'url':doc['source_url'],'span_id':candidate['span_id'],**candidate['span']})
        result={'status':'candidate_complete' if not missing else 'partial' if edges else 'not_found',
            'tasks':tasks,'edges':edges,'missing_task_ids':missing,'selected_document_ids':list(documents),
            'snapshot_hash':hashlib.sha256(json.dumps({id:d['content_hash'] for id,d in documents.items()},sort_keys=True).encode()).hexdigest(),
            'max_documents':3,'trace':trace,'latency_ms':round((time.perf_counter()-started)*1000,3),
            'scope':'Multilingual candidate retrieval with bounded adjudication; semantic correctness requires review.'}
        result['source_versions_current']=EvidenceGraph(self.store,None,self.reranker).validate(result)
        if not result['source_versions_current']:result.update(status='stale_snapshot',edges=[],missing_task_ids=[t['id'] for t in tasks])
        return result
