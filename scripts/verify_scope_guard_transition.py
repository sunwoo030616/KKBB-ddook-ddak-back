"""Audit the post-holdout guard fix without rerunning/tuning retrieval models."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    from rag_backend.research_scope import requests_catalog_mutation
    original_commit=json.loads((ROOT/'reports/fulltext-preregistered.json').read_text())['code_commit']
    path='rag_backend/research_scope.py'
    original=subprocess.check_output(['git','show',original_commit+':'+path],cwd=ROOT)
    namespace={};exec(compile(original,path,'exec'),namespace)
    previous=namespace['requests_catalog_mutation'];rows=[]
    for name in ['evidence_graph_cases.json','model_routing_holdout.json','literature_fresh_validation.json','literature_guard_cases.json','literature_preregistered_evaluation.json']:
        for case in json.loads((ROOT/'data'/name).read_text()):
            old=previous(case['question']);new=requests_catalog_mutation(case['question'])
            rows.append({'id':case['id'],'old_rejected':old,'new_rejected':new,'changed':old!=new})
    changed=[r['id'] for r in rows if r['changed']]
    report={'scope':'Post-holdout functional routing repair. First-pass 10/12 remains unchanged; not a retuned holdout score.',
        'source_path':path,'before_commit':original_commit,'before_sha256':hashlib.sha256(original).hexdigest(),
        'after_sha256':hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),'rows':rows,
        'checks':{'only_i11_routing_changed':changed==['i11'],
            'existing_36_routes_unchanged':all(not r['changed'] for r in rows if not r['id'].startswith('i'))},'complete':True}
    (ROOT/'reports/fulltext-scope-guard-transition.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(report['checks'])
    if not all(report['checks'].values()):raise SystemExit(1)

if __name__=='__main__':main()
