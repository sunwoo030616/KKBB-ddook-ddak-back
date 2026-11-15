"""Finite user-approved acceptable-set scoring; reference never sent to inference providers."""
import importlib.util,statistics
from pathlib import Path
path=Path(__file__).resolve().parents[1]/'situation_v3/metrics.py'
spec=importlib.util.spec_from_file_location('canonical_metrics',path);legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
canonical_case_metrics=legacy.case_metrics

def case_metrics(row):
 s=canonical_case_metrics(row);s['canonical_menu_exact']=s['menu_exact'];s['canonical_status_and_menu_exact']=s['status_and_menu_exact']
 pred=set(row.get('selected_ids',[])) if not row.get('error') else set();accepted=[set(x) for x in row['acceptable_sets']]
 allowed=set().union(*accepted);groups=row['required_groups'];covered=sum(bool(pred&set(g['acceptable_ids'])) for g in groups)
 valid=not row.get('error') and any(pred==x for x in accepted)
 s.update(menu_exact=bool(valid),status_and_menu_exact=bool(valid and row.get('status')==row['expected_status']),accepted_menu_set_exact=bool(valid),required_outcome_recall=covered/len(groups),allowed_menu_precision=len(pred&allowed)/len(pred) if pred else 0,disallowed_menu_count=len(pred-allowed),missing_outcome_count=len(groups)-covered)
 return s
legacy.case_metrics=case_metrics

def summary(rows):
 s=legacy.summary(rows)
 canonical_keys=['macro_precision','macro_recall','macro_f1','micro_precision','micro_recall','micro_f1','true_positive_menus','extra_menus','missing_menus','cases_with_extra_menus','cases_with_missing_menus']
 s['canonical_only_metrics']={k:s.pop(k) for k in canonical_keys}
 scores=[case_metrics(r) for r in rows]
 s['scoring']='exact match to one preapproved acceptable menu-ID set plus expected status; canonical P/R are secondary only'
 s['required_outcome_recall']=statistics.mean(x['required_outcome_recall'] for x in scores) if scores else None
 s['allowed_menu_precision']=statistics.mean(x['allowed_menu_precision'] for x in scores) if scores else None
 s['disallowed_menu_count']=sum(x['disallowed_menu_count'] for x in scores)
 s['missing_outcome_count']=sum(x['missing_outcome_count'] for x in scores)
 return s
