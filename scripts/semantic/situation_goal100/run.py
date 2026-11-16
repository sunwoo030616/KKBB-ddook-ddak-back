# coding: utf-8
"""Same frozen inference/baseline, new approved situation-only references and scoring."""
from pathlib import Path
import argparse,sys,json,datetime,ast
HERE=Path(__file__).resolve().parent;COMPARE=HERE.parent/'situation_compare_v3';BASE=HERE.parent/'situation_v3'
sys.path.insert(0,str(HERE));sys.path.insert(0,str(COMPARE));sys.path.insert(0,str(BASE))
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true');a,rest=p.parse_known_args()
if '--resume' in sys.argv:sys.argv.remove('--resume')
if a.resume:assert a.output.exists(),'No saved run'
else:
 assert not a.output.exists(),'Do not overwrite prior results';a.output.parent.mkdir(parents=True,exist_ok=False)
 a.output.write_text(json.dumps({'complete':False,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':[]})+'\n')
 (a.output.parent/'upstream-calls.jsonl').write_text('')
# Reuse the tested continuation transformer without executing its argument parsing/seeding.
tree=ast.parse((COMPARE/'continue_measured.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='transform')
namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(COMPARE/'continue_measured.py'),'exec'),namespace);continuation=namespace['transform']
def transform(source):
 source=continuation(source)
 source=source.replace('from metrics import case_metrics,summary','from goal_metrics import case_metrics,summary')
 source=source.replace(" P={row['score']['precision']}"," canonicalP={row['score']['precision']}").replace(" R={row['score']['recall']}"," canonicalR={row['score']['recall']}")
 return source
path=COMPARE/'paired.py';wrapper=path.read_text();old="exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})";assert old in wrapper
wrapper=wrapper.replace(old,'source=transform(source)\n'+old)
exec(compile(wrapper,str(path),'exec'),{'__file__':str(path),'__name__':'__main__','transform':transform})
