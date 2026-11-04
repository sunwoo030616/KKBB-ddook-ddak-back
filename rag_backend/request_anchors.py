"""Surface clause anchors, not a general semantic parser.

Explicit lists and requested-object conjunctions provide server-owned boundaries.
Implicit comparisons can remain a single clause; no complete-coverage claim.
"""
import re

HEADS=r'(?:방법|방식|연구|기법|모델|전략|현상|영향|한계|데이터셋|벤치마크|측정값|실측값)'


def request_anchors(question,max_parts=3):
    if not 1<=max_parts<=3:raise ValueError('invalid_anchor_budget')
    cuts=[m.end() for m in re.finditer(r'[,;\n]+\s*|'+HEADS+r'(?:과|와)\s+',question)]
    if not cuts and not re.search(r'combin|joint|together|interleav|alternat',question,re.I):
        cuts=[m.end() for m in re.finditer(r'\s+and\s+',question,re.I)]
    boundaries=[0]+sorted(set(cuts))[:max_parts-1]+[len(question)]
    parts=[]
    for start,end in zip(boundaries,boundaries[1:]):
        while start<end and question[start].isspace():start+=1
        while end>start and question[end-1].isspace():end-=1
        if end>start:parts.append({'start':start,'end':end,'text':question[start:end]})
    return parts
