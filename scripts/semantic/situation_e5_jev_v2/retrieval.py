# coding: utf-8
"""Original E5 candidates preserved; add candidates from generic synonym and lexical evidence."""
import math,re,collections
REPLACEMENTS=[('자가용','자동차'),('처분','판매'),('자가','주택'),('사장','사업자'),('장사','사업'),('창업','사업 시작')]
def normalize(query):
 for before,after in REPLACEMENTS:query=query.replace(before,after)
 return query

def terms(text):
 words=re.findall(r'[가-힣A-Za-z0-9]+',text.lower());result=[]
 for word in words:
  if len(word)>=2:result.append(word)
  result.extend(word[i:i+3] for i in range(max(0,len(word)-2)))
 return result

class LexicalIndex:
 def __init__(self,menus):
  self.ids=[m['id'] for m in menus];self.counts=[];self.df=collections.Counter()
  for m in menus:
   text=(m['name']+' ')*3+m['description']+' '+' '.join(m['select_when'])+' '+' '.join(m.get('aliases',[]))
   counts=collections.Counter(terms(text));self.counts.append(counts);self.df.update(counts.keys())
  self.lengths=[sum(x.values()) for x in self.counts];self.average=sum(self.lengths)/len(self.lengths)
 def search(self,query,limit=20):
  q=set(terms(normalize(query)));scored=[];n=len(self.ids)
  for index,counts in enumerate(self.counts):
   score=0
   for token in q:
    tf=counts.get(token,0)
    if tf:score+=math.log(1+(n-self.df[token]+.5)/(self.df[token]+.5))*tf*2.2/(tf+1.2*(.25+.75*self.lengths[index]/self.average))
   if score>0:scored.append((score,index))
  scored.sort(key=lambda x:(-x[0],x[1]));return [self.ids[i] for _,i in scored[:limit]]

def merge(original,expanded,lexical,limit=100):
 result=list(dict.fromkeys(original));supplement=[]
 for rank in range(max(len(expanded),len(lexical))):
  for group in [expanded,lexical]:
   if rank<len(group) and group[rank] not in result and group[rank] not in supplement:supplement.append(group[rank])
 return (result+supplement)[:limit]
