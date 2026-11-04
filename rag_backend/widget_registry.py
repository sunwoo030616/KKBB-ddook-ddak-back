"""Local registry feature switches; CLI updates have no public write endpoint."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


class WidgetRegistry:
    def __init__(self,path,definitions):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS registry(type TEXT PRIMARY KEY,definition TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1)')
            for kind,definition in definitions.items():
                db.execute('INSERT INTO registry VALUES(?,?,1) ON CONFLICT(type) DO UPDATE SET definition=excluded.definition',
                           (kind,json.dumps(definition,ensure_ascii=False,sort_keys=True)))

    def connect(self):return sqlite3.connect(self.path,timeout=10)

    def snapshot(self):
        with self.connect() as db:rows=db.execute('SELECT type,definition,enabled FROM registry ORDER BY type').fetchall()
        active={kind:json.loads(definition) for kind,definition,enabled in rows if enabled}
        raw=json.dumps(rows,ensure_ascii=False).encode()
        return active,hashlib.sha256(raw).hexdigest()[:16]

    def set_enabled(self,kind,enabled):
        with self.connect() as db:
            row=db.execute('UPDATE registry SET enabled=? WHERE type=?',(int(enabled),kind))
            if row.rowcount!=1:raise ValueError('Unknown widget type')


if __name__=='__main__':
    from .canvas import REGISTRY
    from .store import ROOT
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['list','enable','disable'])
    parser.add_argument('widget',nargs='?');parser.add_argument('--db',default=str(ROOT/'var'/'widgets.sqlite3'))
    args=parser.parse_args();registry=WidgetRegistry(args.db,REGISTRY)
    if args.operation!='list':
        if not args.widget:parser.error('widget type is required')
        registry.set_enabled(args.widget,args.operation=='enable')
    active,version=registry.snapshot();print(json.dumps({'version':version,'enabled':list(active)},ensure_ascii=False))
