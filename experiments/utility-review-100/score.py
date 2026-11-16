"""Apply frozen shared utility labels to saved answers. No API calls."""
import json,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parent;SRC=ROOT.parent/'model-answer-review/answers.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def evaluate(answers,labels,cap=None):
 stats={'cases':len(answers),'at_least_one':0,'at_least_two':0,'at_least_three':0,'recommended_menus':0,'valid_menus':0,'valid_function_groups_two':0}
 # Utility count is distinct menu IDs, not inferred independent outcome coverage.
 for a in answers:
  selected=a['ids'] if cap is None else a['ids'][:cap];valid=sum(x['label'] in labels for x in selected) if not a['error'] else 0
  for n,key in [(1,'at_least_one'),(2,'at_least_two'),(3,'at_least_three')]:stats[key]+=valid>=n
  stats['recommended_menus']+=len(selected);stats['valid_menus']+=valid
 stats.pop('valid_function_groups_two');stats['menu_validity']=stats['valid_menus']/stats['recommended_menus'] if stats['recommended_menus'] else 0
 stats['mean_recommendations']=stats['recommended_menus']/stats['cases'];return stats

def main():
 source=json.loads(SRC.read_text());review=json.loads((ROOT/'review-rules.json').read_text());freeze=json.loads((ROOT/'review-freeze.json').read_text());assert sha(SRC)==freeze['source_sha256'];assert sha(ROOT/'review-rules.json')==freeze['review_rules_sha256'];assert sha(ROOT/'define_review.py')==freeze['definition_script_sha256']
 keys=['improved','llm','jev'];models=[next(m for m in source['models'] if m['id']==k) for k in keys];rows=[]
 for q in source['questions']:
  row={k:q[k] for k in ['case_id','family_id','situation','query','expected_ids','required_groups','acceptable_sets']};row['answers']={}
  for key in keys:
   old=q['answers'][key];ids=old['ids'];judgements=[{'id':mid,'name':source['names'][mid],**review['rules'][q['family_id']][mid]} for mid in ids]
   row['answers'][key]={**old,'old_allowed_hits':old['allowed_hits'],'ids':judgements,'direct_hits':sum(j['label']=='D' for j in judgements) if not old['error'] else 0,'inclusive_hits':sum(j['label'] in ['D','C'] for j in judgements) if not old['error'] else 0}
  rows.append(row)
 summary={}
 for key in keys:
  a=[r['answers'][key] for r in rows]
  summary[key]={'name':next(m['name'] for m in models if m['id']==key),'old':next(s for s in source['summary'] if s['id']==key),'direct':evaluate(a,{'D'}),'direct_or_conditional':evaluate(a,{'D','C'}),'first_three_direct':evaluate(a,{'D'},3),'first_three_inclusive':evaluate(a,{'D','C'},3),'label_counts':dict(collections.Counter(j['label'] for x in a for j in x['ids']))}
 data={'scope':'same100 existing cases; 3 arms; no new inference','review_status':review['status'],'definitions':review['labels'],'principles':review['principles'],'models':models,'summary':summary,'questions':rows,'names':source['names'],'freeze':freeze}
 (ROOT/'reviewed-answers.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
