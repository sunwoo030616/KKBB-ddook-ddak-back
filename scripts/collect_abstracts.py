#!/usr/bin/env python3
"""Fetch a small primary-source arXiv Atom snapshot; full abstracts stay in var/."""
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
IDS=['2005.11401','2210.03629','2310.11511','2403.14403','2305.14283','2307.03172']


def fetch():
    url='https://export.arxiv.org/api/query?'+urllib.parse.urlencode({'id_list':','.join(IDS),'max_results':len(IDS)})
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'KKBB-KnowledgeLab/1.0'}),timeout=45) as response:
        raw=response.read()
    root=ET.fromstring(raw);ns={'a':'http://www.w3.org/2005/Atom'};records=[]
    for entry in root.findall('a:entry',ns):
        source=entry.findtext('a:id',namespaces=ns)
        identifier=source.rsplit('/',1)[-1]
        if re.sub(r'v\d+$','',identifier) not in IDS:raise ValueError('unexpected_paper_id')
        clean=lambda key:re.sub(r'\s+',' ',entry.findtext('a:'+key,default='',namespaces=ns)).strip()
        records.append({'id':'arxiv:'+re.sub(r'v\d+$','',identifier),'title':clean('title'),'text':clean('summary'),
            'source_url':'https://arxiv.org/abs/'+identifier,'kind':'abstract',
            'published_at':clean('published'),'updated_at':clean('updated')})
    if len(records)!=len(IDS):raise ValueError('incomplete_arxiv_snapshot')
    folder=ROOT/'var/literature';folder.mkdir(parents=True,exist_ok=True)
    (folder/'abstracts.json').write_text(json.dumps({'records':records},ensure_ascii=False,indent=2)+'\n')
    manifest={'api_url':url,'response_sha256':hashlib.sha256(raw).hexdigest(),
        'scope':'Abstracts, not full papers; full text is not included in Git.',
        'records':[{k:v for k,v in r.items() if k!='text'}|{'text_sha256':hashlib.sha256(r['text'].encode()).hexdigest()}
                   for r in records]}
    (ROOT/'data/literature_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'collected':len(records),'titles':[r['title'] for r in records]},ensure_ascii=False))


if __name__=='__main__':fetch()
