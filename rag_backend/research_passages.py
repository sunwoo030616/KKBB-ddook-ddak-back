"""Exact-offset overlapping sentence context for research selection."""
import re


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
