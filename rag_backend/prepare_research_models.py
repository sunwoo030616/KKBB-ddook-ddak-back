from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib,json
from huggingface_hub import HfApi,snapshot_download
from .store import ROOT
root=ROOT/'var'/'research_models'
models={'generator':'mlx-community/Qwen3-1.7B-4bit','reranker':'BAAI/bge-reranker-v2-m3','encoder_base':'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2','canvas_generator':'mlx-community/Qwen3-4B-4bit'}
def fetch(item):
 role,repo=item
 info=HfApi().model_info(repo)
 dest=root/role
 snapshot_download(repo,revision=info.sha,local_dir=dest,allow_patterns=['*.json','*.safetensors','*.txt','*.model','*.jinja'],ignore_patterns=['onnx/*','openvino/*','coreml/*'])
 files={}
 for p in sorted(dest.rglob("*")):
  if p.is_file() and '.cache' not in p.relative_to(dest).parts and p.name!='manifest.local.json' and not p.name.startswith('.'):
   sha=hashlib.sha256()
   with p.open('rb') as f:
    for block in iter(lambda:f.read(8*1024*1024),b''):sha.update(block)
   files[str(p.relative_to(dest))]={'sha256':sha.hexdigest(),'bytes':p.stat().st_size}
 manifest={'repo_id':repo,'revision':info.sha,'files':files}
 (dest/'manifest.local.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps({'role':role,'repo_id':repo,'revision':info.sha,'bytes':sum(v['bytes'] for v in files.values())}),flush=True)
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description='Download approximately 3.3 GB of public research models into project-local var/.')
 parser.add_argument('--download',action='store_true',required=True)
 parser.add_argument('--role',action='append',choices=list(models))
 args=parser.parse_args()
 selected={k:v for k,v in models.items() if not args.role or k in args.role}
 with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(fetch,selected.items()))
