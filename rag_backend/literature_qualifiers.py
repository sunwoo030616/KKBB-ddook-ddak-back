"""Reviewed concept aliases, never source-ID rules or a semantic truth judge."""
import hashlib
import json
from pathlib import Path
import re

PATH=Path(__file__).resolve().parents[1]/'data/literature_qualifiers.json'


class QualifierPolicy:
    def __init__(self):
        raw=PATH.read_bytes();data=json.loads(raw)
        self.identity={'version':data['version'],'sha256':hashlib.sha256(raw).hexdigest()}
        self.rules=[(rule['name'],re.compile(rule['request'],re.I),re.compile(rule['source'],re.I)) for rule in data['rules']]
        self.span_names={rule['name'] for rule in data['rules'] if rule.get('require_span',False)}

    def constraints(self,text):return [(name,source) for name,request,source in self.rules if request.search(text)]

    def span_constraints(self,rules):return [(name,source) for name,source in rules if name in self.span_names]

    @staticmethod
    def matches(text,rules):return all(pattern.search(text) for name,pattern in rules)

    @staticmethod
    def coverage(text,rules):return sum(bool(pattern.search(text)) for name,pattern in rules)
