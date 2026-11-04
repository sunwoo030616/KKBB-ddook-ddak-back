"""Local durable review workflow. AI output never approves itself.

Leases fence late workers; they do not promise exactly-once model execution.
All state shares the KnowledgeStore database so version checks and writes are atomic.
"""
import hashlib
import json
import math
import re
import time
import uuid


class WorkflowConflict(ValueError):pass


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


class CurationWorkflow:
    def __init__(self,store,clock=time.time,max_attempts=3):
        if not 1<=max_attempts<=10:raise ValueError('invalid_attempt_budget')
        self.store=store;self.clock=clock;self.max_attempts=max_attempts
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS curation_jobs(
                    id TEXT PRIMARY KEY,document_id TEXT NOT NULL,source_hash TEXT NOT NULL,
                    model_hash TEXT NOT NULL,prompt TEXT NOT NULL,state TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,available REAL NOT NULL,
                    lease_token TEXT,lease_until REAL,result TEXT,error TEXT,
                    review TEXT NOT NULL DEFAULT 'pending',review_revision INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS curation_queue ON curation_jobs(state,available);
                CREATE TABLE IF NOT EXISTS curation_events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT,at REAL NOT NULL,
                    kind TEXT NOT NULL,details TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS curation_releases(
                    id TEXT PRIMARY KEY,manifest TEXT NOT NULL,created REAL NOT NULL,operator TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS curation_active(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),revision INTEGER NOT NULL,release_id TEXT);
                INSERT OR IGNORE INTO curation_active VALUES(1,0,NULL);
            ''')

    def event(self,db,id,kind,**details):
        db.execute('INSERT INTO curation_events(job_id,at,kind,details) VALUES(?,?,?,?)',
                   (id,self.clock(),kind,json.dumps(details,sort_keys=True)))

    def enqueue(self,model_identity,prompt,kind=None):
        if not prompt or len(prompt)>200:raise ValueError('invalid_prompt_version')
        model_hash=digest(model_identity);added=0
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT id,hash,payload FROM documents ORDER BY id').fetchall()
            for document_id,source_hash,payload in rows:
                if kind and json.loads(payload)['kind']!=kind:continue
                id=digest([document_id,source_hash,model_hash,prompt])
                cursor=db.execute('INSERT OR IGNORE INTO curation_jobs(id,document_id,source_hash,model_hash,prompt,state,available) VALUES(?,?,?,?,?,?,?)',
                                  (id,document_id,source_hash,model_hash,prompt,'queued',self.clock()))
                if cursor.rowcount:
                    added+=1;self.event(db,id,'enqueued',source_hash=source_hash)
                else:
                    restored=db.execute("UPDATE curation_jobs SET state='queued',available=?,lease_token=NULL,lease_until=NULL,error=NULL WHERE id=? AND state='stale' AND attempts<?",(self.clock(),id,self.max_attempts))
                    if restored.rowcount:
                        added+=1;self.event(db,id,'reenqueued_after_source_restore',source_hash=source_hash)
        return added

    def claim(self,lease_seconds=300,model_hash=None,prompt=None):
        if not 1<=lease_seconds<=3600:raise ValueError('invalid_lease_duration')
        now=self.clock()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Source replacement invalidates queued/running work, even after a crash.
            stale=db.execute("SELECT j.id FROM curation_jobs j LEFT JOIN documents d ON d.id=j.document_id AND d.hash=j.source_hash WHERE j.state IN ('queued','running') AND d.id IS NULL").fetchall()
            for (id,) in stale:
                db.execute("UPDATE curation_jobs SET state='stale',lease_token=NULL,lease_until=NULL WHERE id=?",(id,))
                self.event(db,id,'source_invalidated')
            expired=db.execute("SELECT id,attempts FROM curation_jobs WHERE state='running' AND lease_until<=?",(now,)).fetchall()
            for id,attempts in expired:
                state='failed' if attempts>=self.max_attempts else 'queued'
                db.execute('UPDATE curation_jobs SET state=?,lease_token=NULL,lease_until=NULL,error=? WHERE id=?',
                           (state,'lease_expired',id));self.event(db,id,'lease_expired',next_state=state)
            row=db.execute("SELECT id,document_id,source_hash,model_hash,prompt,attempts FROM curation_jobs WHERE state='queued' AND available<=? AND (? IS NULL OR model_hash=?) AND (? IS NULL OR prompt=?) ORDER BY available,id LIMIT 1",(now,model_hash,model_hash,prompt,prompt)).fetchone()
            if row is None:return None
            id,document_id,source_hash,model_hash,prompt,attempts=row
            token=uuid.uuid4().hex
            db.execute("UPDATE curation_jobs SET state='running',attempts=attempts+1,lease_token=?,lease_until=? WHERE id=?",(token,now+lease_seconds,id))
            payload=json.loads(db.execute('SELECT payload FROM documents WHERE id=? AND hash=?',(document_id,source_hash)).fetchone()[0])
            self.event(db,id,'claimed',attempt=attempts+1)
        return {'id':id,'lease_token':token,'lease_until':now+lease_seconds,'attempt':attempts+1,
                'model_hash':model_hash,'prompt':prompt,'document':dict(payload,content_hash=source_hash)}

    def import_legacy(self,model_identity,prompt):
        """Migrate compatible pending cards, never importing an approval decision."""
        legacy_model=hashlib.sha256(json.dumps(model_identity,sort_keys=True).encode()).hexdigest()
        imported=0;invalid=0
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute("SELECT j.id,j.document_id,j.source_hash,n.payload,d.payload FROM curation_jobs j JOIN notes n ON n.id=j.document_id AND n.hash=j.source_hash JOIN documents d ON d.id=j.document_id AND d.hash=j.source_hash WHERE j.state='queued' AND j.attempts=0 AND j.model_hash=? AND j.prompt=? AND n.model=? AND n.prompt=?",(digest(model_identity),prompt,legacy_model,prompt)).fetchall()
            for id,document_id,source_hash,payload,source in rows:
                try:
                    candidate=json.loads(payload);document=json.loads(source)
                    self.validate_candidate(candidate,document_id,source_hash,document['text'],document['source_url'])
                except (ValueError,TypeError,KeyError):invalid+=1;continue
                db.execute("UPDATE curation_jobs SET state='prepared',result=?,review='pending' WHERE id=?",(payload,id))
                self.event(db,id,'imported_legacy_candidate',candidate_hash=digest(candidate));imported+=1
        return {'imported':imported,'invalid':invalid,'automatic_approval':False}

    def work_one(self,generator,prompt,lease_seconds=300):
        from .knowledge_lab import select_candidate,validate_selection
        job=self.claim(lease_seconds,model_hash=digest(generator.identity),prompt=prompt)
        if job is None:return {'state':'idle','model_calls':0}
        calls=0
        try:
            raw,schema,spans=select_candidate(job['document'],generator)
            calls=raw.get('model_calls',1)
            candidate=validate_selection(job['document'],raw,schema,spans)
            current=self.complete(job,candidate)
            return {'id':job['id'],'state':'prepared' if current else 'stale','model_calls':calls,
                    'latency_ms':raw.get('latency_ms'),'source_id':job['document']['id']}
        except WorkflowConflict:
            return {'id':job['id'],'state':'lost_lease','model_calls':calls}
        except Exception as error:
            code=('invalid_output' if isinstance(error,(ValueError,TypeError)) else
                  'model_unavailable' if isinstance(error,OSError) else 'inference_error')
            try:state=self.fail(job,code,retryable=code!='invalid_output')
            except WorkflowConflict:state='lost_lease'
            return {'id':job['id'],'state':state,'error':code,'model_calls':calls,
                    'scope':'model_calls counts completed generation returns; failed in-flight calls are unknown'}

    def _owned(self,db,job):
        row=db.execute('SELECT state,lease_token,lease_until,document_id,source_hash,attempts FROM curation_jobs WHERE id=?',(job['id'],)).fetchone()
        if row is None or row[0]!='running' or row[1]!=job['lease_token'] or row[2]<=self.clock():
            raise WorkflowConflict('expired_or_replaced_lease')
        return row

    @staticmethod
    def validate_candidate(candidate,document_id,source_hash,source_text,source_url):
        from .knowledge_lab import EvidenceCard
        EvidenceCard.model_validate({k:candidate.get(k) for k in ('category','quote','tags')})
        start=candidate.get('start');end=candidate.get('end');quote=candidate.get('quote')
        if (candidate.get('source_id')!=document_id or candidate.get('source_hash')!=source_hash
            or candidate.get('source_url')!=source_url
            or type(start) is not int or type(end) is not int or not 0<=start<end<=len(source_text)
            or not isinstance(quote,str) or not quote.strip() or source_text[start:end]!=quote):
            raise ValueError('candidate_provenance_mismatch')
        if candidate.get('status')!='pending_review':raise ValueError('candidate_must_be_unapproved')

    def complete(self,job,candidate):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=self._owned(db,job)
            source=db.execute('SELECT payload FROM documents WHERE id=? AND hash=?',(row[3],row[4])).fetchone()
            if source is None:
                db.execute("UPDATE curation_jobs SET state='stale',lease_token=NULL,lease_until=NULL WHERE id=?",(job['id'],))
                self.event(db,job['id'],'source_invalidated');return False
            document=json.loads(source[0])
            self.validate_candidate(candidate,row[3],row[4],document['text'],document['source_url'])
            db.execute("UPDATE curation_jobs SET state='prepared',result=?,lease_token=NULL,lease_until=NULL,error=NULL WHERE id=?",(json.dumps(candidate,ensure_ascii=False),job['id']))
            self.event(db,job['id'],'prepared',candidate_hash=digest(candidate))
        return True

    def fail(self,job,error_code,retryable=False):
        allowed={'invalid_output','model_unavailable','inference_error','source_error'}
        if error_code not in allowed:raise ValueError('unrecognized_error_code')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=self._owned(db,job)
            state='queued' if retryable and row[5]<self.max_attempts else 'failed'
            # Backoff is deterministic and bounded. Validation failures are terminal.
            if error_code=='invalid_output':state='failed'
            delay=min(60,2**row[5]) if state=='queued' else 0
            db.execute('UPDATE curation_jobs SET state=?,available=?,error=?,lease_token=NULL,lease_until=NULL WHERE id=?',
                       (state,self.clock()+delay,error_code,job['id']))
            self.event(db,job['id'],'failed',error=error_code,next_state=state)
        return state

    def decide(self,id,decision,reviewer,expected_revision,reason):
        if decision not in ('approved','rejected'):raise ValueError('invalid_review_decision')
        if not reviewer.strip() or not reason.strip() or len(reviewer)>100 or len(reason)>1000:
            raise ValueError('reviewer_and_reason_required')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT state,review_revision,result,document_id,source_hash FROM curation_jobs WHERE id=?',(id,)).fetchone()
            if row is None or row[0]!='prepared' or row[1]!=expected_revision:raise WorkflowConflict('review_revision_conflict')
            source=db.execute('SELECT payload FROM documents WHERE id=? AND hash=?',(row[3],row[4])).fetchone()
            if source is None:raise WorkflowConflict('review_source_changed')
            candidate=json.loads(row[2]);document=json.loads(source[0])
            self.validate_candidate(candidate,row[3],row[4],document['text'],document['source_url'])
            db.execute('UPDATE curation_jobs SET review=?,review_revision=review_revision+1 WHERE id=?',(decision,id))
            self.event(db,id,'reviewed',decision=decision,reviewer=reviewer,reason=reason,revision=expected_revision+1)
        return expected_revision+1

    def publish(self,job_ids,operator,expected_revision):
        if not operator.strip() or not job_ids or len(job_ids)!=len(set(job_ids)):
            raise ValueError('unique_reviewed_jobs_and_operator_required')
        manifest=[]
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            active=db.execute('SELECT revision FROM curation_active WHERE singleton=1').fetchone()[0]
            if active!=expected_revision:raise WorkflowConflict('release_revision_conflict')
            for id in sorted(job_ids):
                row=db.execute('SELECT review,result,document_id,source_hash,review_revision FROM curation_jobs WHERE id=?',(id,)).fetchone()
                if row is None or row[0]!='approved':raise WorkflowConflict('unapproved_candidate')
                source=db.execute('SELECT payload FROM documents WHERE id=? AND hash=?',(row[2],row[3])).fetchone()
                if source is None:raise WorkflowConflict('release_source_changed')
                candidate=json.loads(row[1]);document=json.loads(source[0])
                self.validate_candidate(candidate,row[2],row[3],document['text'],document['source_url'])
                manifest.append({'job_id':id,'source_id':row[2],'source_hash':row[3],
                                 'candidate_hash':digest(candidate),'review_revision':row[4]})
            release_id=digest(manifest)
            db.execute('INSERT OR IGNORE INTO curation_releases VALUES(?,?,?,?)',
                       (release_id,json.dumps(manifest,sort_keys=True),self.clock(),operator))
            db.execute('UPDATE curation_active SET revision=revision+1,release_id=? WHERE singleton=1',(release_id,))
            self.event(db,None,'published',release_id=release_id,revision=active+1,operator=operator)
        return {'id':release_id,'revision':active+1,'manifest':manifest}

    def active(self):
        with self.store.connect() as db:
            db.execute('BEGIN')
            revision,id=db.execute('SELECT revision,release_id FROM curation_active WHERE singleton=1').fetchone()
            manifest=json.loads(db.execute('SELECT manifest FROM curation_releases WHERE id=?',(id,)).fetchone()[0]) if id else []
            current={id:hash for id,hash in db.execute('SELECT id,hash FROM documents')}
            valid=all(current.get(m['source_id'])==m['source_hash'] and
                      (review:=db.execute('SELECT review,review_revision,result FROM curation_jobs WHERE id=?',(m['job_id'],)).fetchone()) and
                      review[0]=='approved' and review[1]==m['review_revision'] and digest(json.loads(review[2]))==m['candidate_hash'] for m in manifest)
        return {'id':id,'revision':revision,'valid':bool(id) and valid,'manifest':manifest if valid else []}

    def activate(self,release_id,operator,expected_revision):
        """Rollback an explicit reviewed snapshot, rejecting revoked/stale material."""
        if not operator.strip():raise ValueError('operator_required')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            active=db.execute('SELECT revision FROM curation_active WHERE singleton=1').fetchone()[0]
            if active!=expected_revision:raise WorkflowConflict('release_revision_conflict')
            release=db.execute('SELECT manifest FROM curation_releases WHERE id=?',(release_id,)).fetchone()
            if release is None:raise WorkflowConflict('unknown_release')
            manifest=json.loads(release[0])
            for item in manifest:
                row=db.execute('SELECT review,review_revision,result FROM curation_jobs WHERE id=?',(item['job_id'],)).fetchone()
                if (row is None or row[0]!='approved' or row[1]!=item['review_revision']
                    or digest(json.loads(row[2]))!=item['candidate_hash']):
                    raise WorkflowConflict('release_review_changed')
                if db.execute('SELECT 1 FROM documents WHERE id=? AND hash=?',
                              (item['source_id'],item['source_hash'])).fetchone() is None:
                    raise WorkflowConflict('release_source_changed')
            db.execute('UPDATE curation_active SET revision=revision+1,release_id=? WHERE singleton=1',(release_id,))
            self.event(db,None,'activated',release_id=release_id,revision=active+1,operator=operator)
        return {'id':release_id,'revision':active+1,'manifest':manifest}

    def status(self):
        with self.store.connect() as db:
            states=dict(db.execute('SELECT state,COUNT(*) FROM curation_jobs GROUP BY state'))
            reviews=dict(db.execute("SELECT review,COUNT(*) FROM curation_jobs WHERE state='prepared' GROUP BY review"))
            expired=db.execute("SELECT COUNT(*) FROM curation_jobs WHERE state='running' AND lease_until<=?",(self.clock(),)).fetchone()[0]
            delayed=db.execute("SELECT COUNT(*) FROM curation_jobs WHERE state='queued' AND available>?",(self.clock(),)).fetchone()[0]
        return {'states':states,'reviews':reviews,'expired_leases':expired,'delayed_jobs':delayed,'active':self.active()}

    def audit(self):
        """Replay local provenance/review invariants; not a tamper-proof security log."""
        problems=[];prepared=0;stale=0
        with self.store.connect() as db:
            db.execute('BEGIN')
            rows=db.execute('SELECT id,document_id,source_hash,state,lease_token,lease_until,result,review,review_revision FROM curation_jobs ORDER BY id').fetchall()
            for id,document_id,source_hash,state,token,until,result,review,revision in rows:
                if (state=='running')!=(token is not None and until is not None):
                    problems.append({'id':id,'reason':'lease_state_mismatch'})
                if state!='prepared':continue
                prepared+=1
                source=db.execute('SELECT payload FROM versions WHERE id=? AND hash=?',(document_id,source_hash)).fetchone()
                try:
                    if source is None or hashlib.sha256(source[0].encode()).hexdigest()!=source_hash:
                        raise ValueError('source_version_invalid')
                    d=json.loads(source[0]);self.validate_candidate(json.loads(result),document_id,source_hash,d['text'],d['source_url'])
                except (ValueError,TypeError,KeyError):problems.append({'id':id,'reason':'candidate_provenance_invalid'})
                current=db.execute('SELECT hash FROM documents WHERE id=?',(document_id,)).fetchone()
                stale+=current is None or current[0]!=source_hash
                history=[json.loads(d) for (d,) in db.execute("SELECT details FROM curation_events WHERE job_id=? AND kind='reviewed' ORDER BY seq",(id,))]
                if ([h.get('revision') for h in history]!=list(range(1,revision+1)) or
                    (history and history[-1].get('decision')!=review) or (not history and review!='pending')):
                    problems.append({'id':id,'reason':'review_history_mismatch'})
            events=db.execute('SELECT COUNT(*) FROM curation_events').fetchone()[0]
        return {'valid':not problems,'jobs':len(rows),'prepared_candidates':prepared,'historical_candidates':stale,
                'events':events,'problems':problems,'scope':'Local provenance and state replay; no semantic correctness or tamper-proof claim.'}

    def search_reviewed(self,question,kind='abstract',limit=3,reranker=None):
        """Search approved quote cards, without calling a reviewed whole document true."""
        if kind not in ('abstract','financial_summary') or not 1<=limit<=5:raise ValueError('invalid_reviewed_search_scope')
        snapshot=self.active()
        if not snapshot['valid']:return {'status':'unavailable','cards':[],'release_revision':snapshot['revision']}
        cards=[]
        with self.store.connect() as db:
            db.execute('BEGIN')
            for item in snapshot['manifest']:
                row=db.execute('SELECT result FROM curation_jobs WHERE id=?',(item['job_id'],)).fetchone()
                source=db.execute('SELECT payload FROM documents WHERE id=? AND hash=?',(item['source_id'],item['source_hash'])).fetchone()
                if not row or not source:continue
                document=json.loads(source[0]);candidate=json.loads(row[0])
                if document['kind']!=kind:continue
                self.validate_candidate(candidate,item['source_id'],item['source_hash'],document['text'],document['source_url'])
                cards.append({**candidate,'status':'reviewed_card','title':document['title'],
                              'job_id':item['job_id'],'review_revision':item['review_revision']})
        tokens=set(re.findall(r'\w+',question.lower()))
        overlap=lambda c:len(tokens&set(re.findall(r'\w+',c['title'].lower()+' '+c['quote'].lower())))
        cards=sorted(cards,key=lambda c:(-overlap(c),c['job_id']))[:20]
        scores=reranker.score_pairs([(question,c['title']+'\n'+c['quote']) for c in cards]) if reranker else [float(overlap(c)) for c in cards]
        if len(scores)!=len(cards) or not all(math.isfinite(s) for s in scores):raise ValueError('invalid_reviewed_scores')
        ranked=sorted(zip(cards,scores),key=lambda cs:(-cs[1],cs[0]['job_id']))
        current=self.active()
        if not current['valid'] or (current['id'],current['revision'])!=(snapshot['id'],snapshot['revision']):
            return {'status':'stale_release','cards':[],'release_revision':current['revision']}
        selected=[dict(c,score=score) for c,score in ranked if reranker or score>0][:limit]
        return {'status':'ok','cards':selected,'release_id':snapshot['id'],'release_revision':snapshot['revision'],
                'scope':'Explicitly approved quote cards. Approval is not proof of scientific truth or current financial eligibility.'}
