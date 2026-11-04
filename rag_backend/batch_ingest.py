"""Bounded JSONL ingestion with data and checkpoint committed atomically."""
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

from .knowledge_catalog import KnowledgeCatalog,KINDS


def validate_record(record):
    if not isinstance(record,dict):raise ValueError('record_object_required')
    for key,maximum in [('id',200),('title',500),('text',32768),('source_url',2048)]:
        value=record.get(key)
        if not isinstance(value,str) or not value.strip() or len(value)>maximum:raise ValueError('invalid_record_'+key)
    url=urlsplit(record['source_url'])
    if url.scheme!='https' or not url.netloc or record.get('kind') not in KINDS:raise ValueError('invalid_record_source_or_kind')
    return record


def ingest_jsonl(path,store,batch_size=200,max_batches=1000):
    if type(batch_size) is not int or not 1<=batch_size<=1000 or type(max_batches) is not int or not 1<=max_batches<=10000:
        raise ValueError('invalid_batch_budget')
    path=Path(path);before=path.stat();signature=(before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    dataset=digest.hexdigest();KnowledgeCatalog(store)
    def source_unchanged():
        current=path.stat()
        if (current.st_ino,current.st_size,current.st_mtime_ns,current.st_ctime_ns)!=signature:raise ValueError('ingestion_source_changed')
    def state(db):
        columns=('offset','line','seen','changed','unchanged','batches','complete','revision')
        row=db.execute('SELECT '+','.join(columns)+' FROM ingestion_runs WHERE id=?',(dataset,)).fetchone()
        return dict(zip(columns,row))
    source_unchanged();started=time.perf_counter()
    with store.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS ingestion_runs(id TEXT PRIMARY KEY,bytes INTEGER NOT NULL,
            offset INTEGER NOT NULL DEFAULT 0,line INTEGER NOT NULL DEFAULT 0,seen INTEGER NOT NULL DEFAULT 0,
            changed INTEGER NOT NULL DEFAULT 0,unchanged INTEGER NOT NULL DEFAULT 0,batches INTEGER NOT NULL DEFAULT 0,
            complete INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 0)''')
        db.execute('INSERT OR IGNORE INTO ingestion_runs(id,bytes) VALUES(?,?)',(dataset,before.st_size))
        current=state(db)
    executed=0
    with path.open('rb') as handle:
        handle.seek(current['offset'])
        while not current['complete'] and executed<max_batches:
            records=[];line=current['line']
            while len(records)<batch_size:
                raw=handle.readline(65537)
                if not raw:break
                line+=1
                if len(raw)>65536:raise ValueError('record_line_too_large:'+str(line))
                if raw.strip():records.append(validate_record(json.loads(raw)))
            offset=handle.tell();complete=offset==before.st_size
            source_unchanged()
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE');owned=state(db)
                if owned['revision']!=current['revision'] or owned['offset']!=current['offset']:
                    raise ValueError('ingestion_checkpoint_conflict_retry')
                result=store.ingest_in_transaction(db,records)
                db.execute('''UPDATE ingestion_runs SET offset=?,line=?,seen=seen+?,changed=changed+?,unchanged=unchanged+?,
                    batches=batches+?,complete=?,revision=revision+1 WHERE id=?''',
                    (offset,line,result['seen'],len(result['changed']),result['unchanged'],int(bool(records)),int(complete),dataset))
                current=state(db)
            executed+=int(bool(records))
    return {'dataset_sha256':dataset,'state':current,'batches_this_run':executed,'seconds':time.perf_counter()-started,
        'scope':'Local bounded batches; document versions, FTS and cursor share one SQLite transaction. Not distributed ingestion.'}
