import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path

from .models import Chunk

ALLOWED_HOSTS = {'kbthink.com', 'www.kbsec.com', 'obank.kbstar.com', 'www.shinhancard.com', 'www.fsc.go.kr'}
INSTITUTION_HOSTS = {'kb_card': {'kbthink.com'}, 'kb_securities': {'www.kbsec.com'},
                     'kb_bank': {'obank.kbstar.com', 'kbthink.com'}, 'shinhan_card': {'www.shinhancard.com'}, 'fsc': {'www.fsc.go.kr'}}
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / 'data' / 'financial_guides.json'


class DocumentStore:
    """Local, atomic corpus snapshots. No public arbitrary-URL ingestion endpoint."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS corpus_snapshots(
                    version TEXT PRIMARY KEY, bundle TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS requests(
                    request_id TEXT PRIMARY KEY, status TEXT NOT NULL,
                    reason TEXT NOT NULL, latency_ms REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            ''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def ingest(self, path: Path = DEFAULT_CORPUS):
        raw = Path(path).read_bytes()
        return self._ingest_raw(raw)

    def restore(self, version):
        with self.connect() as db:
            row=db.execute('SELECT bundle FROM corpus_snapshots WHERE version=?',(version,)).fetchone()
        if row is None:raise ValueError('Unknown corpus snapshot')
        return self._ingest_raw(row[0].encode('utf-8'))

    def _ingest_raw(self, raw):
        bundle = json.loads(raw)
        chunks = [Chunk.model_validate(item) for item in bundle['chunks']]
        if not chunks or len({c.id for c in chunks}) != len(chunks):
            raise ValueError('Corpus must contain unique chunk IDs.')
        for c in chunks:
            if c.url.scheme != 'https' or c.url.host not in ALLOWED_HOSTS:
                raise ValueError('Unapproved source URL')
            if c.url.host not in INSTITUTION_HOSTS[c.institution]:
                raise ValueError('Institution and source host do not match')
            if c.verified_at > date.today():
                raise ValueError('Source verification date cannot be in the future')
        version = hashlib.sha256(raw).hexdigest()[:16]
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO corpus_snapshots(version,bundle) VALUES(?,?)',
                       (version,raw.decode('utf-8')))
            db.execute('DELETE FROM chunks')
            db.executemany('INSERT INTO chunks VALUES (?, ?)',
                           [(c.id, c.model_dump_json()) for c in chunks])
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?)', ('version', version))
        return version

    def load(self):
        with self.connect() as db:
            rows = db.execute('SELECT payload FROM chunks ORDER BY id').fetchall()
            version = db.execute("SELECT value FROM metadata WHERE key='version'").fetchone()
        return [Chunk.model_validate_json(row[0]) for row in rows], version[0] if version else 'empty'

    def audit(self, request_id, status, reason, latency_ms):
        # Intentionally exclude raw questions, answers, headers, and model responses.
        with self.connect() as db:
            db.execute('INSERT INTO requests(request_id,status,reason,latency_ms) VALUES (?,?,?,?)',
                       (request_id, status, reason, latency_ms))
