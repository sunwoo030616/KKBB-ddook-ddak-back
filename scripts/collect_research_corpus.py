#!/usr/bin/env python3
"""Collect pinned research IDs from official arXiv; abstracts remain local."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
NS={'a':'http://www.w3.org/2005/Atom'}


def parse(raw,specs):
    expected={s['arxiv_id']:s for s in specs}
    if len(expected)!=len(specs):raise ValueError('duplicate_requested_id')
    rows=[];seen=set()
    for entry in ET.fromstring(raw).findall('a:entry',NS):
        clean=lambda key:re.sub(r'\s+',' ',entry.findtext('a:'+key,default='',namespaces=NS)).strip()
        versioned=clean('id').rsplit('/',1)[-1];id=re.sub(r'v\d+$','',versioned)
        if id not in expected or id in seen or not re.fullmatch(r'\d{4}\.\d{4,5}(v\d+)?',versioned):
            raise ValueError('unexpected_or_duplicate_arxiv_id')
        spec=expected[id];title=clean('title');text=clean('summary')
        if spec['title_contains'].lower() not in title.lower():raise ValueError('paper_title_mismatch:'+id)
        if not title or len(text)<50 or not clean('updated') or not clean('published'):
            raise ValueError('incomplete_paper_record')
        rows.append({'id':'arxiv:'+id,'title':title,'text':text,'kind':'abstract',
                     'source_url':'https://arxiv.org/abs/'+versioned,
                     'published_at':clean('published'),'updated_at':clean('updated'),'topic':spec['topic']})
        seen.add(id)
    if seen!=set(expected):raise ValueError('incomplete_arxiv_snapshot')
    return sorted(rows,key=lambda r:r['id'])


def fetch():
    specs=json.loads((ROOT/'data/research_corpus_sources.json').read_text())
    url='https://export.arxiv.org/api/query?'+urllib.parse.urlencode({'id_list':','.join(s['arxiv_id'] for s in specs),'max_results':len(specs)})
    request=urllib.request.Request(url,headers={'User-Agent':'KKBB-KnowledgeLab/2.0'})
    with urllib.request.urlopen(request,timeout=45) as response:raw=response.read(1_000_001)
    if len(raw)>1_000_000:raise ValueError('oversized_arxiv_snapshot')
    rows=parse(raw,specs);folder=ROOT/'var/literature';folder.mkdir(parents=True,exist_ok=True)
    destination=folder/'expanded-abstracts.json';temp=destination.with_suffix('.tmp')
    temp.write_text(json.dumps({'records':rows},ensure_ascii=False,indent=2)+'\n');temp.replace(destination)
    manifest={'api_url':url,'fetched_at':datetime.now(timezone.utc).isoformat(),'response_sha256':hashlib.sha256(raw).hexdigest(),
              'scope':'Curated research abstracts; not full papers or approved financial facts.',
              'records':[{k:v for k,v in r.items() if k!='text'}|{'text_sha256':hashlib.sha256(r['text'].encode()).hexdigest()} for r in rows]}
    (ROOT/'data/expanded_literature_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'collected':len(rows),'titles':[r['title'] for r in rows]},ensure_ascii=False))
    return rows


if __name__=='__main__':fetch()
