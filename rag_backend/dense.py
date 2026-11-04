"""CPU multilingual embedding search; explicit opt-in, no paid API."""
import hashlib
import json
import sqlite3
from pathlib import Path
from threading import Lock

from .models import SearchHit
from .store import ROOT

MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'


class LocalEncoder:
    name = MODEL

    def __init__(self, allow_download=False):
        from fastembed import TextEmbedding
        self.model = TextEmbedding(model_name=MODEL, cache_dir=str(ROOT / 'var' / 'models'),
                                   threads=2, local_files_only=not allow_download)
        # Use the downloaded ONNX artifact hash, not only a mutable model name.
        # FastEmbed's cache is project-local. Fail closed if the artifact is absent.
        paths = sorted((ROOT / 'var' / 'models').rglob('*.onnx'))
        if len(paths) != 1:
            raise ValueError('Expected exactly one ONNX model in the project cache')
        digest = hashlib.sha256()
        with paths[0].open('rb') as model_file:
            for block in iter(lambda: model_file.read(1024 * 1024), b''):
                digest.update(block)
        self.name = MODEL + '@sha256:' + digest.hexdigest()
        self.lock = Lock()

    def encode(self, texts):
        with self.lock:
            return [v.tolist() for v in self.model.embed(texts)]


class DenseIndex:
    """Content-addressed document vector cache. Questions are never cached on disk."""

    def __init__(self, chunks, encoder, path):
        self.chunks = chunks
        self.encoder = encoder
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_hits = 0
        self.new_embeddings = 0
        self.vectors = {}
        records = []
        missing = []
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS vectors(model TEXT, hash TEXT, vector TEXT, PRIMARY KEY(model,hash))')
            for c in chunks:
                text = f'{c.title}\n{c.section}\n{c.text}'
                digest = hashlib.sha256(text.encode()).hexdigest()
                row = db.execute('SELECT vector FROM vectors WHERE model=? AND hash=?', (encoder.name, digest)).fetchone()
                if row:
                    self.vectors[c.id] = json.loads(row[0])
                    self.cache_hits += 1
                else:
                    missing.append((c.id, digest, text))
            if missing:
                vectors = encoder.encode([x[2] for x in missing])
                if len(vectors) != len(missing):
                    raise ValueError('embedding_count_mismatch')
                for (chunk_id, digest, _), vector in zip(missing, vectors):
                    self.vectors[chunk_id] = vector
                    records.append((encoder.name, digest, json.dumps(vector)))
                db.executemany('INSERT OR REPLACE INTO vectors VALUES (?,?,?)', records)
                self.new_embeddings = len(records)
        dimensions = {len(v) for v in self.vectors.values()}
        if len(dimensions) > 1 or 0 in dimensions:
            raise ValueError('inconsistent_vector_dimensions')

    def search(self, question, institution, top_k=3):
        import math
        vector = self.encoder.encode([question])[0]
        norm = math.sqrt(sum(v * v for v in vector))
        if not norm:
            return []
        hits = []
        for c in self.chunks:
            if institution and c.institution != institution:
                continue
            target = self.vectors[c.id]
            if len(vector) != len(target):
                raise ValueError('query_vector_dimension_mismatch')
            target_norm = math.sqrt(sum(v * v for v in target))
            score = sum(a * b for a, b in zip(vector, target)) / (norm * target_norm) if target_norm else 0
            hits.append(SearchHit(chunk_id=c.id, source_id=c.source_id, institution=c.institution,
                                  title=c.title, section=c.section, url=str(c.url),
                                  verified_at=str(c.verified_at), text=c.text, published_at=c.published_at, content_as_of=c.content_as_of, effective_from=c.effective_from,
                          effective_until=c.effective_until, temporal_basis=c.temporal_basis, score=score))
        return sorted(hits, key=lambda h: (-h.score, h.chunk_id))[:top_k]


def fuse_rankings(rankings, top_k):
    scores, hits = {}, {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, 1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0) + 1 / (60 + rank)
            hits[hit.chunk_id] = hit
    ids = sorted(scores, key=lambda i: (-scores[i], i))[:top_k]
    return [hits[i].model_copy(update={'score': scores[i]}) for i in ids]


if __name__ == '__main__':
    encoder = LocalEncoder(allow_download=True)
    print(f'Ready: {encoder.name}; dimension={len(encoder.encode(["금융 문서 검색"])[0])}')
