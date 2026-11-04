"""Indexed catalog, bounded lexical retrieval and version-checked source spans."""
import json
import re

KINDS=('abstract','financial_summary')


class KnowledgeCatalog:
    def __init__(self,store):
        self.store=store
        with store.connect() as db:
            db.executescript('''
                BEGIN IMMEDIATE;
                CREATE INDEX IF NOT EXISTS documents_kind_id ON documents(json_extract(payload,'$.kind'),id);
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(title,text,id UNINDEXED,kind UNINDEXED,hash UNINDEXED);
                CREATE TRIGGER IF NOT EXISTS knowledge_fts_insert AFTER INSERT ON documents BEGIN
                    INSERT INTO knowledge_fts(rowid,title,text,id,kind,hash) VALUES(new.rowid,json_extract(new.payload,'$.title'),json_extract(new.payload,'$.text'),new.id,json_extract(new.payload,'$.kind'),new.hash);
                END;
                CREATE TRIGGER IF NOT EXISTS knowledge_fts_update AFTER UPDATE ON documents BEGIN
                    DELETE FROM knowledge_fts WHERE rowid=old.rowid;
                    INSERT INTO knowledge_fts(rowid,title,text,id,kind,hash) VALUES(new.rowid,json_extract(new.payload,'$.title'),json_extract(new.payload,'$.text'),new.id,json_extract(new.payload,'$.kind'),new.hash);
                END;
                CREATE TRIGGER IF NOT EXISTS knowledge_fts_delete AFTER DELETE ON documents BEGIN
                    DELETE FROM knowledge_fts WHERE rowid=old.rowid;
                END;
                CREATE TABLE IF NOT EXISTS knowledge_catalog_schema(version INTEGER PRIMARY KEY);
                INSERT INTO knowledge_fts(rowid,title,text,id,kind,hash)
                    SELECT rowid,json_extract(payload,'$.title'),json_extract(payload,'$.text'),id,json_extract(payload,'$.kind'),hash
                    FROM documents WHERE NOT EXISTS(SELECT 1 FROM knowledge_catalog_schema WHERE version=1);
                INSERT OR IGNORE INTO knowledge_catalog_schema VALUES(1);
                COMMIT;
            ''')

    @staticmethod
    def validate(kind,limit):
        if kind not in KINDS or type(limit) is not int or not 1<=limit<=100:raise ValueError('invalid_catalog_bounds')

    def page(self,kind='abstract',after='',limit=25):
        self.validate(kind,limit)
        if not isinstance(after,str) or len(after)>200:raise ValueError('invalid_catalog_cursor')
        with self.store.connect() as db:
            rows=db.execute("SELECT id,hash,json_extract(payload,'$.title'),json_extract(payload,'$.source_url') FROM documents WHERE json_extract(payload,'$.kind')=? AND id>? ORDER BY id LIMIT ?",(kind,after,limit+1)).fetchall()
        return {'records':[{'id':id,'hash':hash,'title':title,'source_url':url,'kind':kind} for id,hash,title,url in rows[:limit]],
            'next_cursor':rows[limit-1][0] if len(rows)>limit else None,'scope':'Keyset cursor over current versions; not a multi-page snapshot.'}

    def search(self,question,kind='abstract',limit=5):
        self.validate(kind,limit)
        if not isinstance(question,str) or not question.strip() or len(question)>500:raise ValueError('invalid_catalog_question')
        terms=list(dict.fromkeys(re.findall(r'\w+',question)))[:16]
        if not terms:return {'hits':[],'mode':'fts5'}
        expression=' OR '.join('"'+term.replace('"','""')+'"' for term in terms)
        with self.store.connect() as db:
            rows=db.execute('''SELECT d.id,d.hash,json_extract(d.payload,'$.title'),json_extract(d.payload,'$.source_url'),bm25(knowledge_fts)
                FROM knowledge_fts JOIN documents d ON d.rowid=knowledge_fts.rowid
                WHERE knowledge_fts MATCH ? AND json_extract(d.payload,'$.kind')=? AND d.hash=knowledge_fts.hash
                ORDER BY bm25(knowledge_fts),d.id LIMIT ?''',(expression,kind,limit)).fetchall()
        return {'hits':[{'id':id,'hash':hash,'title':title,'source_url':url,'lexical_rank':score} for id,hash,title,url,score in rows],
            'mode':'fts5','scope':'Lexical candidates only; Korean-English semantic search is a separate model route.'}

    def source_span(self,id,expected_hash,start,end):
        if not isinstance(id,str) or not 1<=len(id)<=200 or not isinstance(expected_hash,str) or not re.fullmatch(r'[a-f0-9]{64}',expected_hash):raise ValueError('invalid_source_identity')
        if type(start) is not int or type(end) is not int or not 0<=start<end or end-start>1000:raise ValueError('invalid_source_span_budget')
        with self.store.connect() as db:
            row=db.execute('SELECT hash,payload FROM documents WHERE id=?',(id,)).fetchone()
        if row is None:raise ValueError('unknown_source')
        if row[0]!=expected_hash:raise ValueError('stale_source_version')
        document=json.loads(row[1])
        if end>len(document['text']):raise ValueError('source_span_out_of_range')
        return {'id':id,'hash':row[0],'title':document['title'],'source_url':document['source_url'],
            'start':start,'end':end,'quote':document['text'][start:end],
            'scope':'Current at this read; revalidate before later use. Provenance, not semantic truth.'}

    def query_plan(self,kind='abstract',after=''):
        self.validate(kind,1)
        with self.store.connect() as db:
            rows=db.execute("EXPLAIN QUERY PLAN SELECT id FROM documents WHERE json_extract(payload,'$.kind')=? AND id>? ORDER BY id LIMIT 25",(kind,after)).fetchall()
        return [row[3] for row in rows]
