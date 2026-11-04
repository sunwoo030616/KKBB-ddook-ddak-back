#!/usr/bin/env python3
"""Small scientific metadata transfer experiment; no full text or invented abstracts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


class PaperIndex:
    def __init__(self,path):
        self.path=path;path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS papers USING fts5(doi UNINDEXED,title,authors,year UNINDEXED)')

    def ingest(self,records):
        records={r['doi'].lower():r for r in records if r.get('doi') and r.get('title')}
        with sqlite3.connect(self.path) as db:
            db.execute('DELETE FROM papers')
            db.executemany('INSERT INTO papers VALUES(?,?,?,?)',[(doi,r['title'],', '.join(r['authors']),str(r['year']))
                                                                  for doi,r in records.items()])
        return len(records)

    def search(self,query,limit=5):
        import re
        tokens=re.findall(r'[a-zA-Z0-9]+',query)[:12]
        if not tokens:return []
        expression=' OR '.join('"'+t+'"' for t in tokens)
        with sqlite3.connect(self.path) as db:
            return [dict(doi=r[0],title=r[1],authors=r[2],year=r[3],score=r[4]) for r in db.execute(
                'SELECT doi,title,authors,year,bm25(papers) FROM papers WHERE papers MATCH ? ORDER BY bm25(papers) LIMIT ?',
                (expression,min(10,max(1,limit))))]


def collect(query,rows):
    url='https://api.crossref.org/works?'+urllib.parse.urlencode({'query.bibliographic':query,'rows':rows,
        'select':'DOI,title,author,published,type'})
    req=urllib.request.Request(url,headers={'User-Agent':'KKBB-Paper-Metadata-Experiment/1.0'})
    with urllib.request.urlopen(req,timeout=40) as response:raw=response.read()
    records=[]
    for item in json.loads(raw)['message']['items']:
        if not item.get('DOI') or not item.get('title'):continue
        records.append({'doi':item['DOI'].lower(),'title':item['title'][0],
            'authors':[' '.join(filter(None,[a.get('given'),a.get('family')])) for a in item.get('author',[])],
            'year':item.get('published',{}).get('date-parts',[[None]])[0][0],
            'url':'https://doi.org/'+item['DOI'],'type':item.get('type')})
    return {'source':'Crossref REST API','query':query,'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'response_sha256':hashlib.sha256(raw).hexdigest(),'scope':'Bibliographic metadata only; no full-text understanding or relevance labels.',
            'records':list({r['doi']:r for r in records}.values())}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--query',default='retrieval augmented generation evidence evaluation');p.add_argument('--rows',type=int,default=25);args=p.parse_args()
    result=collect(args.query,args.rows)
    (ROOT/'data/paper_metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    index=PaperIndex(ROOT/'var/papers.sqlite3');count=index.ingest(result['records'])
    report={'indexed':count,'queries':{q:index.search(q) for q in ('retrieval evidence','evaluation generation','grounding citations')},
            'scope':result['scope']}
    (ROOT/'reports/paper-metadata-search.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Indexed',count,'unique DOI metadata records')
