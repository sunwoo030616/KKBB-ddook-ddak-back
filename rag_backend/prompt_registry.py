"""Reviewed prompt artifacts with immutable content fingerprints."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def load_prompt(name,version='1'):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',name) or not re.fullmatch(r'[1-9][0-9]{0,3}',version):
        raise ValueError('invalid_prompt_identifier')
    raw=(ROOT/'data/prompts'/f'{name}.v{version}.json').read_bytes();data=json.loads(raw)
    if set(data)!= {'name','version','text'} or data['name']!=name or data['version']!=version:
        raise ValueError('prompt_contract_mismatch')
    if not isinstance(data['text'],str) or not 20<=len(data['text'])<=4096:raise ValueError('prompt_text_budget')
    return {**data,'sha256':hashlib.sha256(raw).hexdigest()}
