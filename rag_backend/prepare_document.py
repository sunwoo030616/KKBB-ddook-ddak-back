"""Prepare review candidates from a local text/PDF, preserving page provenance.

This never mutates the approved corpus. A human must check text, topics, URL,
institution, and dates before merging candidate chunks into the corpus snapshot.
"""
import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path


def normalize(text):
    return re.sub(r'[ \t]+', ' ', text.replace('\x00', '')).strip()


def chunk_text(text, size=500, overlap=80):
    if size < 50 or overlap < 0 or overlap >= size:
        raise ValueError('Require size >= 50 and 0 <= overlap < size')
    text = normalize(text)
    result = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        # Prefer a complete sentence boundary without risking a zero-step loop.
        if end < len(text):
            boundary = text.rfind('. ', start + size // 2, end)
            if boundary > start:
                end = boundary + 1
        result.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return result


def prepare(path, source_id, institution, url, title, topic, verified_at, size=500, overlap=80):
    path = Path(path)
    if path.suffix.lower() == '.pdf':
        from pypdf import PdfReader
        pages = [(i, p.extract_text() or '') for i, p in enumerate(PdfReader(path).pages, 1)]
    elif path.suffix.lower() in ('.txt', '.md'):
        pages = [(1, path.read_text(encoding='utf-8'))]
    else:
        raise ValueError('Only local .pdf, .txt, .md files are supported')
    chunks = []
    for page, text in pages:
        for i, part in enumerate(chunk_text(text, size, overlap), 1):
            if len(part) < 10:
                continue
            chunks.append({'id': f'{source_id}-p{page}-c{i}', 'source_id': source_id,
                           'institution': institution, 'title': title,
                           'section': f'page {page} / chunk {i}', 'url': url,
                           'verified_at': verified_at, 'text': part, 'topics': [topic], 'keywords': []})
    if not chunks:
        raise ValueError('No extractable text; scanned PDFs need a separately reviewed OCR step')
    return {'review_required': True, 'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'chunk_size_chars': size, 'overlap_chars': overlap, 'chunks': chunks}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('input')
    p.add_argument('--source-id', required=True)
    p.add_argument('--institution', required=True, choices=['kb_card', 'kb_securities', 'kb_bank', 'shinhan_card'])
    p.add_argument('--url', required=True)
    p.add_argument('--title', required=True)
    p.add_argument('--topic', required=True)
    p.add_argument('--verified-at', required=True, type=date.fromisoformat)
    p.add_argument('--size', type=int, default=500)
    p.add_argument('--overlap', type=int, default=80)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    result = prepare(args.input, args.source_id, args.institution, args.url, args.title,
                     args.topic, str(args.verified_at), args.size, args.overlap)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'Prepared {len(result["chunks"])} candidate chunks; manual review required.')
