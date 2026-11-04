"""Explicit, revision-pinned download; never invoked by the HTTP path."""
import hashlib
import json
import argparse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    from huggingface_hub import HfApi,snapshot_download
    parser=argparse.ArgumentParser();parser.add_argument('--variant',choices=('small','big'),default='small');args=parser.parse_args()
    repo='Helsinki-NLP/opus-mt-ko-en' if args.variant=='small' else 'Helsinki-NLP/opus-mt-tc-big-ko-en'
    role='literature_translator_small' if args.variant=='small' else 'literature_translator'
    info=HfApi().model_info(repo);destination=ROOT/'var/research_models'/role
    weights='pytorch_model.bin' if args.variant=='small' else 'model.safetensors'
    names=['config.json','generation_config.json',weights,'source.spm','target.spm',
           'vocab.json','tokenizer_config.json','special_tokens_map.json']
    snapshot_download(repo,revision=info.sha,local_dir=destination,allow_patterns=names+['README.md'])
    files={name:{'bytes':(destination/name).stat().st_size,
        'sha256':hashlib.sha256((destination/name).read_bytes()).hexdigest()}
        for name in names if (destination/name).is_file()}
    if not all(name in files for name in ('config.json',weights,'source.spm','target.spm','vocab.json')):
        raise ValueError('incomplete_translation_snapshot')
    manifest={'repo_id':repo,'revision':info.sha,'language':'ko-en','license':'apache-2.0' if args.variant=='small' else 'cc-by-4.0',
        'attribution':'Helsinki-NLP / University of Helsinki, OPUS-MT; https://huggingface.co/'+repo,
        'files':files,'scope':'Local Korean-English literature query translation; not a fact generator.'}
    (destination/'manifest.local.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'repo':repo,'revision':info.sha,'bytes':sum(f['bytes'] for f in files.values())}))


if __name__=='__main__':main()
