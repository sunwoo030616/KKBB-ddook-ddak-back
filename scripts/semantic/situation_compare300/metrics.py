"""Set-based multi-menu metrics. Errors stay in all denominators."""
import math,statistics
from common import usage_counts

def case_metrics(row):
    gold=set(row['expected_ids']);pred=set(row.get('selected_ids',[])) if not row.get('error') else set()
    tp=len(gold&pred);fp=len(pred-gold);fn=len(gold-pred)
    precision=tp/len(pred) if pred else 0
    recall=tp/len(gold) if gold else None
    f1=2*precision*recall/(precision+recall) if precision+recall else 0
    exact=not row.get('error') and pred==gold
    return {'tp':tp,'fp':fp,'fn':fn,'precision':precision,'recall':recall,'f1':f1,
            'menu_exact':bool(exact),'status_and_menu_exact':bool(exact and row.get('status')==row['expected_status'])}

def summary(rows):
    n=len(rows)
    scores=[case_metrics(r) for r in rows]
    tp=sum(s['tp'] for s in scores);fp=sum(s['fp'] for s in scores);fn=sum(s['fn'] for s in scores)
    times=sorted(r['http_ms'] for r in rows if not r.get('error'))
    usage=[usage_counts(c.get('usage')) for r in rows for c in r.get('calls',[])]
    def total(k):
        vals=[u[k] for u in usage if isinstance(u[k],int)]
        return {'observed_calls':len(vals),'sum':sum(vals) if vals else None,
                'mean_per_case':sum(vals)/n if vals and n else None}
    return {'cases':n,'errors':sum(bool(r.get('error')) for r in rows),
        'menu_exact_correct':sum(s['menu_exact'] for s in scores),'menu_exact_accuracy':sum(s['menu_exact'] for s in scores)/n if n else None,
        'status_and_menu_correct':sum(s['status_and_menu_exact'] for s in scores),'status_and_menu_accuracy':sum(s['status_and_menu_exact'] for s in scores)/n if n else None,
        'macro_precision':sum(s['precision'] for s in scores)/n if n else None,
        'macro_recall':sum(s['recall'] for s in scores)/n if n else None,
        'macro_f1':sum(s['f1'] for s in scores)/n if n else None,
        'micro_precision':tp/(tp+fp) if tp+fp else 0,'micro_recall':tp/(tp+fn) if tp+fn else 0,
        'micro_f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
        'true_positive_menus':tp,'extra_menus':fp,'missing_menus':fn,
        'cases_with_extra_menus':sum(s['fp']>0 for s in scores),'cases_with_missing_menus':sum(s['fn']>0 for s in scores),
        'mean_http_ms':statistics.mean(times) if times else None,'median_http_ms':statistics.median(times) if times else None,
        'p95_http_ms':times[math.ceil(.95*len(times))-1] if times else None,
        'actual_upstream_calls':len(usage),'tokens':{'input':total('input'),'output':total('output'),'cached_input':total('cached_input')},
        'statuses':{s:sum(r.get('status')==s for r in rows) for s in sorted({r.get('status','error') for r in rows})}}
