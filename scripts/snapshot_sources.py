#!/usr/bin/env python3
"""Snapshot approved official HTML as review candidates, not approved retrieval data.

Raw pages/candidates stay in ignored var/. Commit only hashes and fetch metadata.
Unknown policy dates are never inferred from a page's retrieval timestamp.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag_backend.prepare_document import chunk_text
from rag_backend.store import ALLOWED_HOSTS, ROOT
from urllib.parse import urlparse


class Text(HTMLParser):
    def __init__(self):super().__init__();self.skip=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript'):self.skip+=1
        elif tag in ('p','div','br','li','h1','h2','h3','tr'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)


def snapshot(corpus, output, limit=6):
    output.mkdir(parents=True,exist_ok=True);sources={}
    for c in corpus['chunks']:sources.setdefault(c['url'],c)
    records=[]
    for url,source in list(sources.items())[:limit]:
        record={'source_id':source['source_id'],'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),
                'approved_for_retrieval':False,'policy_dates':'unverified','status':'failed'}
        try:
            if urlparse(url).hostname not in ALLOWED_HOSTS:raise ValueError('unapproved_host')
            request=urllib.request.Request(url,headers={'User-Agent':'KKBB-document-research/1.0'})
            with urllib.request.urlopen(request,timeout=25) as response:
                if urlparse(response.url).hostname not in ALLOWED_HOSTS:raise ValueError('unapproved_redirect')
                raw=response.read(4_000_001)
                if len(raw)>4_000_000:raise ValueError('document_too_large')
                charset=response.headers.get_content_charset() or 'utf-8'
            digest=hashlib.sha256(raw).hexdigest();folder=output/source['source_id'];folder.mkdir(exist_ok=True)
            previous=json.loads((folder/'current.json').read_text()) if (folder/'current.json').exists() else None
            parser=Text();parser.feed(raw.decode(charset,errors='replace'))
            chunks=chunk_text(''.join(parser.parts))
            (folder/(digest+'.html')).write_bytes(raw)
            candidates={'source_sha256':digest,'review_required':True,
                        'chunks':[{'id':f'{source["source_id"]}-{digest[:8]}-{i}',
                                   'source_id':source['source_id'],'url':url,'text':text,
                                   'locator':f'extracted-text chunk {i}; verify against original HTML'}
                                  for i,text in enumerate(chunks,1)]}
            (folder/(digest+'.candidates.json')).write_text(json.dumps(candidates,ensure_ascii=False,indent=2))
            record.update(status='prepared',sha256=digest,candidate_count=len(chunks),
                          changed=previous is not None and previous.get('sha256')!=digest)
            (folder/'current.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
        except Exception as e:record['error_type']=type(e).__name__
        records.append(record)
    return {'scope':'Unreviewed extraction candidates; not an expanded approved corpus. No financial dates inferred.',
            'sources':records}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=6);args=p.parse_args()
    result=snapshot(json.loads((ROOT/'data/financial_guides.json').read_text()),ROOT/'var/source_snapshots',args.limit)
    (ROOT/'reports/source-snapshot.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'prepared':sum(x['status']=='prepared' for x in result['sources']),
                      'failed':sum(x['status']=='failed' for x in result['sources'])}))
