"""User-requested partial-hit analysis. Does not change frozen references or inference."""
import statistics

def partial_summary(rows):
 n=len(rows);hits=required_hits=clean_hits=menu_total=allowed_total=covered=required_total=0;recalls=[];errors=0;budget_hits={1:0,2:0,3:0}
 for r in rows:
  error=bool(r.get('error'));errors+=error
  ordered=r.get('selected_ids',[]) if not error else [];pred=set(ordered)
  allowed=set().union(*(set(s) for s in r['acceptable_sets']))
  group_count=len(r['required_groups']);group_hits=sum(bool(pred&set(g['acceptable_ids'])) for g in r['required_groups'])
  has_hit=bool(pred&allowed);hits+=has_hit;required_hits+=bool(group_hits);clean_hits+=bool(has_hit and not pred-allowed)
  menu_total+=len(pred);allowed_total+=len(pred&allowed);covered+=group_hits;required_total+=group_count;recalls.append(group_hits/group_count)
  for k in budget_hits:budget_hits[k]+=bool(set(ordered[:k])&allowed)
 return {'cases':n,'partial_hit_correct':hits,'partial_hit_rate':hits/n if n else None,'at_least_one_required_outcome_correct':required_hits,'at_least_one_required_outcome_rate':required_hits/n if n else None,'partial_with_no_disallowed_correct':clean_hits,'partial_with_no_disallowed_rate':clean_hits/n if n else None,'predicted_menu_count':menu_total,'allowed_predicted_menu_count':allowed_total,'menu_level_allowed_precision':allowed_total/menu_total if menu_total else 0,'mean_recommended_menus':menu_total/n if n else None,'macro_required_outcome_recall':statistics.mean(recalls) if recalls else None,'micro_required_outcome_recall':covered/required_total if required_total else None,'covered_required_groups':covered,'required_groups':required_total,'errors':errors,'response_order_budget_hits':{str(k):{'hits':v,'rate':v/n if n else None} for k,v in budget_hits.items()},'definition':'Hit if at least one predicted ID is in the union of preapproved acceptable answer sets, including approved optional suggestions. Errors fail. Extra wrong menus do not erase the hit, so precision and recommendation count must be reported. Response-order budgets are not guaranteed relevance rankings.'}
