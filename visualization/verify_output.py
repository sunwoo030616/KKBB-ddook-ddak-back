"""Validate exported artifacts against the catalog and actual JEV evidence."""
import json
from pathlib import Path
import numpy as np
from generate_umap import ROOT, sha, validate_trace

out=Path(__file__).resolve().parent/'output'
meta=json.loads((out/'metadata.json').read_text())
data=json.loads((out/'data.json').read_text())
menus=json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text())['menus']
evidence=json.loads((ROOT/'docs/menu-e5-jev-evaluation.json').read_text())
assert meta['catalog_sha256']==sha(ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json')
assert meta['evidence_sha256']==sha(ROOT/'docs/menu-e5-jev-evaluation.json')
assert meta['server_sha256']==sha(ROOT/'scripts/semantic/server.py')
for name,digest in meta['outputs'].items():
    assert sha(out/name)==digest,name
with np.load(out/'embeddings.npz',allow_pickle=False) as saved:
    ids=saved['ids'].tolist(); vectors=saved['vectors']
assert ids==[m['id'] for m in menus]
assert vectors.shape==(585,384) and np.isfinite(vectors).all()
assert np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-5)
coords=np.array([[p['x'],p['y']] for p in data['points']])
assert coords.shape==(585,2) and np.isfinite(coords).all()
assert len({p['cluster'] for p in data['points']})==12
for example in data['examples']:
    row=evidence['results'][example['evidence_index']]
    assert example['query']==row['query']
    ranking=[c['id'] for c in example['candidates']]
    assert validate_trace(evidence,row,data['catalog_sha256'],ranking,40)==example['selected_ids']
    scores=[c['cosine'] for c in example['candidates']]
    assert np.isfinite(scores).all() and all(-1<=s<=1 for s in scores)
    assert scores==sorted(scores,reverse=True)
    assert [c['rank'] for c in example['candidates']]==list(range(1,41))
assert 'cdn.plot.ly' not in (out/'e5_umap.html').read_text().split('</script>')[-1]
print('Verified all output hashes; 585 normalized real vectors and finite coordinates; 12 groups; 3 exact E5/JEV candidate and final-selection traces')
