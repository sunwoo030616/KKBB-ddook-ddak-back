"""Bounded PDF enrichment; offsets refer to normalized extracted text, not PDF bytes."""
import hashlib
from io import BytesIO
import re
import unicodedata

MAX_PDF_BYTES=5_000_000
MAX_PAGES=3
MAX_PAGE_CHARS=12_000


def enrich_document(document,pdf_bytes,source_url):
    from pypdf import PdfReader
    if not source_url.startswith('https://') or len(pdf_bytes)>MAX_PDF_BYTES:
        raise ValueError('fulltext_source_budget')
    reader=PdfReader(BytesIO(pdf_bytes))
    abstract=document.get('abstract_text',document['text'])
    text=abstract;pages=[]
    for index,page in enumerate(reader.pages[:MAX_PAGES]):
        extracted=page.extract_text() or ''
        extracted=re.sub(r'\s+',' ',unicodedata.normalize('NFKC',extracted)).strip()
        if not extracted:continue
        if len(extracted)>MAX_PAGE_CHARS:raise ValueError('fulltext_page_budget')
        text+='\n\n';start=len(text);text+=extracted
        pages.append({'page':index+1,'start':start,'end':len(text),
            'text_sha256':hashlib.sha256(extracted.encode()).hexdigest(),'url':source_url+f'#page={index+1}'})
    if not pages:raise ValueError('fulltext_empty')
    return {k:v for k,v in document.items() if k!='content_hash'}|{
        'text':text,'abstract_text':abstract,'fulltext':{'url':source_url,
        'pdf_sha256':hashlib.sha256(pdf_bytes).hexdigest(),'extraction':'pypdf-nfkc-whitespace-v1',
        'extractor_version':__import__('pypdf').__version__,'scope':'First three pages only; normalized extraction, not complete PDF or byte offsets.',
        'pages':pages}}


def document_passages(document,max_chars=480):
    """Keep page boundaries and abstract offsets; no cross-page invented quote."""
    from .research_passages import context_passages,contribution_passages
    abstract=document.get('abstract_text',document['text'])
    result={f'a:{key}':span for key,span in contribution_passages(abstract,max_chars).items()}
    # Include complete sentence contexts even when a long author claim is split
    # before a qualifier. The verifier must check the complete evidence bundle.
    for key,span in context_passages(abstract,max_chars).items():
        result.setdefault(f's:{key}',{**span,'evidence_role':'abstract_context'})
    for page in document.get('fulltext',{}).get('pages',[]):
        start,end=page['start'],page['end']
        if not 0<=start<end<=len(document['text']):raise ValueError('invalid_fulltext_offsets')
        extracted=document['text'][start:end]
        if hashlib.sha256(extracted.encode()).hexdigest()!=page['text_sha256']:raise ValueError('invalid_fulltext_hash')
        for key,span in context_passages(extracted,max_chars).items():
            result[f'b{page["page"]}:{key}']={**span,'start':start+span['start'],'end':start+span['end'],
                'evidence_role':'paper_body_context','page':page['page'],'citation_url':page['url']}
    # Three pages have bounded bytes, but exceptionally fragmented text must
    # fail explicitly instead of silently losing arbitrary middle passages.
    if len(result)>160:raise ValueError('fulltext_passage_budget')
    return result
