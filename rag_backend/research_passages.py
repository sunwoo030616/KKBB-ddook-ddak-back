"""Exact-offset overlapping sentence context for research selection."""
import re

CLAIM=re.compile(r'\bwe (?:propose|introduce|present|develop|explore|design|study|investigate|provide|build|release|demonstrate|show|find)\b|'
    r'\bour (?:method|approach|framework|model|system|algorithm|illustrative work)\b|'
    r'\bthis (?:paper|work|study) (?:addresses|proposes|introduces|presents|explores|studies|develops|provides)\b|'
    r'\bpropos(?:e|es|ing) (?:a|an|the|our)\b',re.I)


def contribution_passages(text,max_chars=480):
    """Author-claim sentence windows, a disclosed heuristic, not discourse truth."""
    boundaries=[0]+[m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z])',text)]+[len(text)]
    selected={}
    for i,(start,end) in enumerate(zip(boundaries,boundaries[1:])):
        if not CLAIM.search(text[start:end]):continue
        window_end=boundaries[i+2] if i+2<len(boundaries) else end
        for local in context_passages(text[start:window_end],max_chars).values():
            a=start+local['start'];b=start+local['end']
            # Retain later chunks of the SAME long author sentence, even if
            # its 'We introduce' marker fell into the first chunk. Never mark
            # a following background-only sentence as an author claim.
            if a>=end:continue
            selected[(a,b)]={'start':a,'end':b,'text':text[a:b],'evidence_role':'author_claim_context',
                'claim_start':start,'claim_end':end}
            if len(selected)>=12:break
        if len(selected)>=12:break
    if not selected:return {id:{**s,'evidence_role':'abstract_context'} for id,s in context_passages(text,max_chars).items()}
    return {f'c{i}':span for i,span in enumerate(selected.values())}


def context_passages(text,max_chars=480):
    if not 80<=max_chars<=1000:raise ValueError('invalid_passage_budget')
    boundaries=[0]+[m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z])',text)]+[len(text)]
    segments=[]
    for a,b in zip(boundaries,boundaries[1:]):
        while a<b and text[a].isspace():a+=1
        while b>a and text[b-1].isspace():b-=1
        if b>a:segments.append((a,b))
    spans=[]
    for i,(start,end) in enumerate(segments):
        if i+1<len(segments) and segments[i+1][1]-start<=max_chars:end=segments[i+1][1]
        if end-start<=max_chars:spans.append((start,end));continue
        words=list(re.finditer(r'\S+',text[start:end]));j=0
        while j<len(words):
            stop=j+1
            while stop<len(words) and words[stop].end()-words[j].start()<=max_chars:stop+=1
            a=start+words[j].start();b=start+words[stop-1].end()
            if b-a>max_chars:
                # An unusually long token is split without inventing any source bytes.
                for offset in range(a,b,max_chars):
                    begin=max(a,min(offset,b-max_chars));spans.append((begin,min(begin+max_chars,b)))
            else:spans.append((a,b))
            if stop==len(words):break
            j=max(j+1,stop-8)
    unique=list(dict.fromkeys((a,b) for a,b in spans if text[a:b].strip()))
    return {f'p{i}':{'start':a,'end':b,'text':text[a:b]} for i,(a,b) in enumerate(unique)}
