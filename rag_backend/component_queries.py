"""Bounded clause views for neural component retrieval, without widget keyword rules."""
import re


def component_queries(message,max_queries=4):
    # Preserve the full utterance: individual clauses can lose negation/context.
    queries=[message]
    fragments=re.split(r'[.!?。！？,，;；\n]+|그리고\s+|(?<=고)\s+|(?<=는데)\s+',message)
    for part in fragments:
        part=part.strip()
        if len(part)>=7 and part!=message and part not in queries:queries.append(part)
        if len(queries)>=max_queries:break
    return queries


def multi_query_scores(ranker,message,kinds,registry,relevance_floor=0.001):
    queries=component_queries(message)
    raw=ranker.score_pairs([(q,registry[k]['purpose']) for q in queries for k in kinds])
    if len(raw)!=len(queries)*len(kinds):raise ValueError('ranker_score_count_mismatch')
    blocks=[raw[i*len(kinds):(i+1)*len(kinds)] for i in range(len(queries))]
    # A low absolute neural score can still be the best match for a second intent.
    # Normalize within each view; these values are ranking features, not confidence.
    # Subtract each clause's background floor so nearly flat, uninformative
    # fragments do not promote every catalog entry. Keep the full-query view intact.
    normalized=[[max(0,float(s)-(min(block) if i else 0))/max(max(block),1e-9)
                 for s in block] for i,block in enumerate(blocks)]
    values=[max(block[i] for block in normalized) for i in range(len(kinds))]
    # Conservative development heuristic, not a calibrated probability threshold.
    # Unknown requests must be able to produce no candidates instead of forced top-1.
    if max(raw,default=0)<relevance_floor:values=[0.0]*len(kinds)
    return values,blocks[0],queries
