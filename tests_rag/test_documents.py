import json
from datetime import date, timedelta

import pytest

from rag_backend.prepare_document import chunk_text, prepare
from rag_backend.store import DEFAULT_CORPUS, DocumentStore


def test_chunking_preserves_long_unicode_text_and_bounds():
    text = '가나다라마바사아자차카타파하' * 150
    chunks = chunk_text(text, size=100, overlap=20)
    assert all(0 < len(c) <= 100 for c in chunks)
    rebuilt = chunks[0] + ''.join(c[20:] for c in chunks[1:])
    assert rebuilt == text


@pytest.mark.parametrize('size,overlap', [(0, 0), (50, 50), (100, -1)])
def test_invalid_chunking_fails(size, overlap):
    with pytest.raises(ValueError):
        chunk_text('text', size, overlap)


def test_document_preparation_is_only_a_review_candidate(tmp_path):
    source = tmp_path / 'example.txt'
    source.write_text('테스트 문서입니다. 기관별로 서로 다른 안내를 검수합니다. ' * 30)
    result = prepare(source, 'sample', 'kb_card', 'https://kbthink.com/card/lost.html',
                     '검수 후보', 'report', '2026-11-02', size=100, overlap=10)
    assert result['review_required'] is True
    assert result['chunks'][0]['section'] == 'page 1 / chunk 1'
    assert len(result['input_sha256']) == 64
    assert len(result['chunks']) > 1


@pytest.mark.parametrize('kind', ['host_mismatch', 'duplicate_id', 'future_date'])
def test_invalid_snapshot_keeps_previous_snapshot(tmp_path, kind):
    store = DocumentStore(tmp_path / 'docs.db')
    version = store.ingest()
    data = json.loads(DEFAULT_CORPUS.read_text())
    if kind == 'host_mismatch':
        data['chunks'][0]['institution'] = 'fsc'
    elif kind == 'duplicate_id':
        data['chunks'].append(data['chunks'][0])
    else:
        data['chunks'][0]['verified_at'] = str(date.today() + timedelta(days=1))
    path = tmp_path / 'invalid.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        store.ingest(path)
    assert store.load()[1] == version
