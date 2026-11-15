# coding: utf-8
"""Compute partial hits from saved outputs; never issues API requests."""
import json,sys
from pathlib import Path
from partial_metrics import partial_summary
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=ROOT/'docs/situation-goal100';run=json.loads((OUT/'run/results.json').read_text())
by={p:{r['case_id']:r for r in run['results'] if r['provider']==p} for p in run['providers']};common=set.intersection(*(set(x) for x in by.values()))
result={'complete':run['complete'],'primary_metric_changed_by_user_during_run':True,'sources_and_labels_unchanged':True,'common_evaluated_cases':len(common),'common_case_summary':{p:partial_summary([row for row in run['results'] if row['provider']==p and row['case_id'] in common]) for p in by},'all_available_by_provider':{p:partial_summary(list(rows.values())) for p,rows in by.items()},'family_results':{p:{f:partial_summary([r for r in rows.values() if r['family_id']==f]) for f in sorted({r['family_id'] for r in rows.values()})} for p,rows in by.items()}}
(OUT/'partial-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('complete',run['complete'],'common cases',len(common))
for p,s in result['common_case_summary'].items():print(p,s['partial_hit_correct'],'/',s['cases'],'precision',s['menu_level_allowed_precision'],'mean menus',s['mean_recommended_menus'])
