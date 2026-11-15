"""Freeze data before development, then freeze code independently for each run."""
import argparse,json,subprocess
from pathlib import Path
from common import sha
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
data_files=['scripts/semantic/situation_v2/'+n for n in ['development-12.json','regression-300.json','fresh-100.json','fresh-labels.tsv']]
data_freeze=HERE/'data-freeze.json'
if data_freeze.exists():
 for name,digest in json.loads(data_freeze.read_text()).items():assert sha(ROOT/name)==digest,name
else:data_freeze.write_text(json.dumps({f:sha(ROOT/f) for f in data_files},indent=2)+'\n')
files=data_files+['scripts/semantic/situation_v2/'+n for n in ['run.py','metrics.py','common.py']]+['src/main/java/com/example/kb_ai_backend/service/'+n for n in ['SemanticMenuRecommendationService.java','SemanticMenuSelectionService.java','SemanticMenuRetriever.java','JevDecisionClient.java','MenuCatalog.java']]+['src/main/resources/kb_starbanking_menu_structure_cleaned.json','scripts/semantic/server.py','scripts/semantic/model_manifest.json','docs/situation-v2/PROTOCOL.md']
if a.output.exists():raise ValueError('Refuse to overwrite a prior freeze')
a.output.write_text(json.dumps({'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'files':{f:sha(ROOT/f) for f in files}},indent=2)+'\n')
print('Frozen data and code:',a.output)
