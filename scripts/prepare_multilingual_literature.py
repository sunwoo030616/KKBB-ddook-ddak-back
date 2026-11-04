"""Explicit free-model setup with immutable revision and artifact hashes."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    from huggingface_hub import HfApi,snapshot_download
    repo='cross-encoder/mmarco-mMiniLMv2-L12-H384-v1';info=HfApi().model_info(repo)
    destination=ROOT/'var/research_models/literature_multilingual'
    names=['config.json','model.safetensors','tokenizer.json','tokenizer_config.json',
        'special_tokens_map.json','sentencepiece.bpe.model','vocab.json']
    snapshot_download(repo,revision=info.sha,local_dir=destination,allow_patterns=names+['README.md'])
    files={name:{'sha256':hashlib.sha256((destination/name).read_bytes()).hexdigest(),'bytes':(destination/name).stat().st_size}
        for name in names if (destination/name).is_file()}
    if not all(name in files for name in ('config.json','model.safetensors','tokenizer.json')):raise ValueError('incomplete_multilingual_snapshot')
    (destination/'manifest.local.json').write_text(json.dumps({'repo_id':repo,'revision':info.sha,
        'license':'apache-2.0','language':'multilingual','files':files},indent=2)+'\n')
    print(json.dumps({'repo':repo,'revision':info.sha,'bytes':sum(f['bytes'] for f in files.values())}))


if __name__=='__main__':main()
