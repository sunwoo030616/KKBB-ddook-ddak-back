"""Positive-menu P/R/F1 and separate negative behavior; errors remain in denominators."""
import math,statistics
from common import usage_counts

def case_metrics(row):
 gold=set(row['expected_ids']);pred=set(row.get('selected_ids',[])) if not row.get('error') else set()
 tp=len(gold&pred);fp=len(pred-gold);fn=len(gold-pred)
 p=tp/len(pred) if pred else 0;r=tp/len(gold) if gold else None
 f1=2*p*r/(p+r) if gold and p+r else 0 if gold else None
 exact=not row.get('error') and pred==gold
 return {'tp':tp,'fp':fp,'fn':fn,'precision':p if gold else None,'recall':r,'f1':f1,'menu_exact':bool(exact),'status_and_menu_exact':bool(exact and row.get('status')==row['expected_status'])}

def summary(rows):
 scores=[case_metrics(r) for r in rows];n=len(rows);positive=[s for s in scores if s['recall'] is not None]
 tp=sum(s['tp'] for s in scores);fp=sum(s['fp'] for s in scores);fn=sum(s['fn'] for s in scores)
 times=sorted(r['http_ms'] for r in rows if not r.get('error'))
 usages=[usage_counts(c.get('usage')) for r in rows for c in r.get('calls',[])]
 def total(k):
  values=[u[k] for u in usages if isinstance(u[k],int)]
  return {'observed_calls':len(values),'sum':sum(values) if values else None,'mean_per_case':sum(values)/n if values and n else None}
 return {'cases':n,'positive_cases':len(positive),'negative_cases':n-len(positive),'errors':sum(bool(r.get('error')) for r in rows),
  'menu_exact_correct':sum(s['menu_exact'] for s in scores),'menu_exact_accuracy':sum(s['menu_exact'] for s in scores)/n if n else None,
  'status_and_menu_correct':sum(s['status_and_menu_exact'] for s in scores),'status_and_menu_accuracy':sum(s['status_and_menu_exact'] for s in scores)/n if n else None,
  'macro_precision':statistics.mean(s['precision'] for s in positive) if positive else None,'macro_recall':statistics.mean(s['recall'] for s in positive) if positive else None,'macro_f1':statistics.mean(s['f1'] for s in positive) if positive else None,
  'micro_precision':tp/(tp+fp) if tp+fp else 0,'micro_recall':tp/(tp+fn) if tp+fn else 0,'micro_f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
  'true_positive_menus':tp,'extra_menus':fp,'missing_menus':fn,'cases_with_extra_menus':sum(s['fp']>0 for s in scores),'cases_with_missing_menus':sum(s['fn']>0 for s in scores),
  'mean_http_ms':statistics.mean(times) if times else None,'median_http_ms':statistics.median(times) if times else None,'p95_http_ms':times[math.ceil(.95*len(times))-1] if times else None,
  'actual_upstream_calls':len(usages),'tokens':{'input':total('input'),'output':total('output'),'cached_input':total('cached_input')},
  'statuses':{s:sum(r.get('status')==s for r in rows) for s in sorted({r.get('status','error') for r in rows})}}
