"""Freeze v3 source, dataset, labels and protocol without rewriting prior freezes."""
import json,hashlib,argparse,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
files=[*sorted((ROOT/'src/main/java/com/example/kb_ai_backend/service').glob('*.java')),*sorted((ROOT/'src/main/java/com/example/kb_ai_backend/controller').glob('*RecommendationController.java')),*sorted(HERE.glob('*.py')),*sorted(HERE.glob('*-*.json')),HERE/'holdout-labels.tsv',ROOT/'docs/situation-v3/PROTOCOL.md',ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json',ROOT/'scripts/semantic/server.py',ROOT/'scripts/semantic/model_manifest.json']
files=[f for f in files if 'freeze-' not in f.name]
assert not a.output.exists()
a.output.write_text(json.dumps({'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'files':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}},indent=2)+'\n')
print('Frozen:',a.output)
