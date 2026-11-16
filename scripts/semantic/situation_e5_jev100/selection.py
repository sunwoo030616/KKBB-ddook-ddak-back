"""Deterministic selection from actual Jev Noul answers; no label access."""
import math

def select(candidate_ids,answers,threshold=.7,max_menus=3):
 probabilities={}
 for mid in candidate_ids:
  a=answers.get(mid,{})
  if a.get('type')!='noul' or isinstance(a.get('noul'),bool) or not isinstance(a.get('noul'),(int,float)) or not math.isfinite(a['noul']) or not 0<=a['noul']<=1:raise ValueError('Missing/invalid Noul probability')
  probabilities[mid]=a['noul']
 ranked=sorted(enumerate(candidate_ids),key=lambda pair:(-probabilities[pair[1]],pair[0]))
 return [mid for _,mid in ranked if probabilities[mid]>=threshold][:max_menus],probabilities
