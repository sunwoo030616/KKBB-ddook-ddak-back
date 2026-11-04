#!/usr/bin/env python3
"""Explicit download of a free English reranker. Never called on request paths."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    from huggingface_hub import HfApi,snapshot_download
    repo='cross-encoder/ms-marco-MiniLM-L6-v2'
    info=HfApi().model_info(repo);dest=ROOT/'var/research_models/literature_reranker'
    snapshot_download(repo,revision=info.sha,local_dir=dest,
        allow_patterns=['config.json','model.safetensors','tokenizer.json','tokenizer_config.json',
                        'special_tokens_map.json','vocab.txt','README.md'])
    files={}
    for name in ('config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','vocab.txt'):
        path=dest/name
        if path.exists():files[name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
    if not all(n in files for n in ('config.json','model.safetensors','tokenizer_config.json','vocab.txt')):
        raise ValueError('incomplete_model_snapshot')
    manifest={'repo_id':repo,'revision':info.sha,'language':'en','license':'apache-2.0',
              'scope':'English literature queries and abstracts only. No hosted inference.', 'files':files}
    (dest/'manifest.local.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'repo':repo,'revision':info.sha,'bytes':sum(v['bytes'] for v in files.values())}))


if __name__=='__main__':main()
