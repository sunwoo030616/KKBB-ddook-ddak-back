import os
from typing import Literal
from pathlib import Path
from contextlib import asynccontextmanager
from pydantic import BaseModel, ConfigDict, Field

from .canvas import ComposeRequest

class JobSubmission(BaseModel):
    model_config=ConfigDict(extra="forbid")
    request: ComposeRequest
    client_request_id: str = Field(pattern=r"^[a-f0-9-]{36}$")


from fastapi import FastAPI, HTTPException

from .finance import CalculationRequest, FinanceRequest, FinanceResponse, analyze, calculate
from .models import AskRequest, AskResponse
from .pipeline import Pipeline
from .retrieval import institutions_for
from .store import DocumentStore, ROOT


def create_app(db_path=None, generator=None, enable_dense=None, enable_research=None, enable_canvas=None):
    store = DocumentStore(Path(db_path or os.getenv('RAG_DB_PATH', str(ROOT / 'var' / 'rag.sqlite3'))))
    with store.connect() as db:
        archived=db.execute('SELECT COUNT(*) FROM corpus_snapshots').fetchone()[0]
    if not store.load()[0] or not archived or os.getenv('RAG_REFRESH_CORPUS')=='1':store.ingest()
    import hashlib
    runtime_sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (ROOT/'rag_backend').glob('*.py')}
    dense_index = None
    if enable_dense or (enable_dense is None and os.getenv('RAG_ENABLE_DENSE') == '1'):
        from .dense import DenseIndex, LocalEncoder
        dense_index = DenseIndex(store.load()[0], LocalEncoder(), store.path.with_suffix('.vectors.db'))
    pipeline = Pipeline(store, generator, dense_index)
    @asynccontextmanager
    async def lifespan(application):
        yield
        if application.state.canvas_jobs is not None:application.state.canvas_jobs.close()

    app = FastAPI(title='깨비뚝딱 Generative UI 서비스', version='0.3.0', lifespan=lifespan,
                  description='채팅 맥락을 금융 위젯 화면으로 변환합니다. 구성 작업·상태·근거 검색·계산을 서버에서 검증합니다.')
    app.state.pipeline = pipeline

    @app.get('/health')
    def health():
        active_generator=getattr(app.state.composer,'generator',None)
        base_generator=getattr(active_generator,'generator',active_generator)
        prefix_cache=getattr(base_generator,'system_prefix_cache',None)
        return {'status': 'ok', 'chunks': len(pipeline.chunks), 'corpus_version': pipeline.version,
                'runtime_source_sha256':runtime_sources,
                'llm_configured': pipeline.generator.configured,
                'retrievers': ['bm25', 'hybrid'] + (['dense', 'fusion'] if dense_index else []),
                'embedding_model': dense_index.encoder.name if dense_index else None,
                'default_generation': 'extractive',
                'research_configured': app.state.research is not None,
                'canvas_configured': app.state.composer is not None,
                'system_prefix_cache':prefix_cache.snapshot() if prefix_cache else None,
                'model_integrity':getattr(base_generator,'verification',None),
                'inference_cache':(app.state.composer.generator.snapshot() if app.state.composer is not None
                                   and hasattr(app.state.composer.generator,'snapshot') else None),
                'reranker_execution':({'device':getattr(app.state.composer.component_ranker,'device','unknown'),
                                       'dtype':getattr(app.state.composer.component_ranker,'dtype','unknown')}
                                      if app.state.composer is not None else None)}

    @app.get('/sources')
    def sources():
        sources = {}
        for c in pipeline.chunks:
            sources.setdefault(c.source_id, {'source_id': c.source_id, 'institution': c.institution,
                                    'title': c.title, 'url': str(c.url), 'verified_at': str(c.verified_at), 'records': []})
            sources[c.source_id]['records'].append({'chunk_id':c.id, 'section':c.section,
                 'published_at':c.published_at, 'content_as_of':c.content_as_of, 'effective_from':c.effective_from,
                 'effective_until':c.effective_until, 'temporal_basis':c.temporal_basis})
        return list(sources.values())

    @app.post('/search')
    def search(req: AskRequest):
        institutions = institutions_for(req.question)
        if len(institutions) > 1 or (req.institution and institutions and institutions != {req.institution}):
            raise HTTPException(422, '질문과 기관 범위가 충돌합니다.')
        institution = req.institution or next(iter(institutions), None)
        if not institution:
            raise HTTPException(422, '기관을 지정해주세요.')
        try:
            hits = pipeline.search(req.question, institution, req.retriever, req.top_k, req.as_of)
        except ValueError as e:
            if str(e) == 'dense_not_configured':
                raise HTTPException(503, '로컬 모델 준비 후 RAG_ENABLE_DENSE=1로 실행해주세요.') from None
            raise
        return {'corpus_version': pipeline.version, 'hits': hits}

    @app.post('/ask', response_model=AskResponse)
    def ask(req: AskRequest):
        try:
            return pipeline.ask(req)
        except ValueError as e:
            if str(e) == 'llm_not_configured':
                raise HTTPException(503, 'LLM 모드에는 서버의 OPENAI_API_KEY 설정이 필요합니다.') from None
            if str(e) == 'dense_not_configured':
                raise HTTPException(503, '로컬 모델 준비 후 RAG_ENABLE_DENSE=1로 실행해주세요.') from None
            raise

    @app.post('/finance/calculate')
    def financial_calculate(req: CalculationRequest):
        return calculate(req.calculation)

    @app.post('/finance/analyze', response_model=FinanceResponse)
    def financial_analyze(req: FinanceRequest):
        try:
            return analyze(pipeline, req)
        except ValueError as e:
            if str(e) == 'dense_not_configured':
                raise HTTPException(503, '로컬 의미 검색 모델이 설정되지 않았습니다.') from None
            raise

    from .research import ResearchRequest
    local_generator = None
    def get_local_generator():
        nonlocal local_generator
        if local_generator is None:
            from .research_models import MLXGenerator
            local_generator = MLXGenerator()
        return local_generator
    research_engine = None
    if enable_research or (enable_research is None and os.getenv('RAG_ENABLE_RESEARCH') == '1'):
        from .research import ResearchPipeline
        from .research_models import MLXGenerator, CrossEncoderReranker
        research_engine = ResearchPipeline(pipeline, get_local_generator(), CrossEncoderReranker())
    app.state.research = research_engine

    @app.post('/research/ask')
    def research_ask(req: ResearchRequest):
        if research_engine is None:
            raise HTTPException(503, '로컬 연구 모델을 준비하고 RAG_ENABLE_RESEARCH=1로 실행해주세요.')
        return research_engine.ask(req)

    @app.post('/research/papers')
    def paper_research(req: AskRequest):
        if app.state.composer is None:raise HTTPException(503, '로컬 모델이 활성화되지 않았습니다.')
        import json
        from .paper_agent import PaperAgent
        path=ROOT/'data/paper_metadata.json'
        if not path.exists():raise HTTPException(503, '논문 메타데이터 스냅샷이 없습니다.')
        return PaperAgent(json.loads(path.read_text())['records'],app.state.composer.generator).run(req.question)

    from .canvas import CanvasComposer, ComposeRequest, ComposeConflict
    composer = None
    if enable_canvas or (enable_canvas is None and os.getenv('RAG_ENABLE_CANVAS') == '1'):
        from .research_models import MLXGenerator
        from .research_models import CrossEncoderReranker
        from .semantic_review import SemanticReviewer
        from .intent_contract import IntentInterpreter
        canvas_generator=MLXGenerator(role=os.getenv('CANVAS_MODEL_ROLE','canvas_generator'))
        if os.getenv('RAG_EXACT_CACHE')=='1':
            from .inference_cache import MemoizedGenerator
            canvas_generator=MemoizedGenerator(canvas_generator)
        composer = CanvasComposer(pipeline, canvas_generator,
                                  str(store.path.with_suffix('.screens.db')), component_ranker=CrossEncoderReranker(),
                                  semantic_reviewer=SemanticReviewer(canvas_generator),
                                  intent_interpreter=IntentInterpreter(canvas_generator))
    app.state.composer = composer
    knowledge_path=Path(os.getenv('KNOWLEDGE_DB_PATH',str(ROOT/'var/knowledge.sqlite3')))

    @app.get('/knowledge/status')
    def knowledge_status():
        from .knowledge_lab import KnowledgeStore
        kb=KnowledgeStore(knowledge_path)
        return {'documents':len(kb.documents()),'candidate_notes':len(kb.notes()),
                'notes_are_approved':False}

    class KnowledgeQuery(BaseModel):
        model_config=ConfigDict(extra='forbid')
        question:str=Field(min_length=2,max_length=500,pattern=r'\S')
        kind:Literal['abstract','financial_summary']='abstract'
        mode:Literal['lexical','neural']='neural'
        limit:int=Field(default=3,ge=1,le=5)

    @app.post('/knowledge/search')
    def knowledge_search(req:KnowledgeQuery):
        from .knowledge_lab import KnowledgeStore
        if req.mode=='neural' and composer is None:raise HTTPException(503,'로컬 검색 모델이 활성화되지 않았습니다.')
        kb=KnowledgeStore(knowledge_path)
        return {'hits':kb.search(req.question,req.kind,req.limit,
                composer.component_ranker if req.mode=='neural' else None),
                'scope':'Local curation corpus; abstracts and financial summaries are separate.'}

    def curation_workflow():
        from .knowledge_lab import KnowledgeStore
        from .curation_workflow import CurationWorkflow
        return CurationWorkflow(KnowledgeStore(knowledge_path))

    @app.get('/knowledge/curation/status')
    def curation_status():return curation_workflow().status()

    @app.get('/knowledge/curation/audit')
    def curation_audit():return curation_workflow().audit()

    @app.post('/knowledge/reviewed-search')
    def reviewed_search(req:KnowledgeQuery):
        if req.mode=='neural' and composer is None:raise HTTPException(503,'로컬 검색 모델이 활성화되지 않았습니다.')
        return curation_workflow().search_reviewed(req.question,req.kind,req.limit,
            composer.component_ranker if req.mode=='neural' else None)

    @app.get('/canvas/catalog')
    def canvas_catalog():
        from .canvas import REGISTRY
        active, version = composer.registry.snapshot() if composer else (REGISTRY, 'builtin')
        return {'version':version, 'widgets':[{'type':k,**v} for k,v in active.items()]}

    class LiteratureResearch(BaseModel):
        model_config=ConfigDict(extra='forbid')
        question:str=Field(min_length=2,max_length=500,pattern=r'\S')
        mode:Literal['single','decompose','compact','fast','contextual','anchored']='single'

    from threading import Lock
    literature_lock=Lock()
    literature_resources={}

    def get_literature_resources(fast=False,english=False,translated=False):
        # Reuse bounded score caches across requests. Lazy embedding load leaves
        # the existing financial screen startup path unchanged.
        from .retrieval_acceleration import CachedReranker,SpanPrefilter
        with literature_lock:
            key='english_reranker' if english else 'reranker'
            if key not in literature_resources:
                if english:
                    from .literature_reranker import EnglishLiteratureReranker
                    literature_resources[key]=CachedReranker(EnglishLiteratureReranker())
                else:literature_resources[key]=CachedReranker(composer.component_ranker)
            if fast and 'prefilter' not in literature_resources:
                from .dense import LocalEncoder
                literature_resources['prefilter']=SpanPrefilter(LocalEncoder(),knowledge_path.with_suffix('.spans.db'))
            pool=int(os.getenv('LITERATURE_DENSE_POOL','0')) if translated else 0
            if pool and not 3<=pool<=20:raise ValueError('invalid_literature_pool_budget')
            if pool:
                from .literature_encoder import EnglishLiteratureEncoder,DocumentPrefilter
                if 'english_encoder' not in literature_resources:literature_resources['english_encoder']=EnglishLiteratureEncoder()
                if 'document_prefilter' not in literature_resources:
                    literature_resources['document_prefilter']=DocumentPrefilter(literature_resources['english_encoder'],knowledge_path.with_suffix('.english-vectors.db'),limit=pool)
            return dict(literature_resources)

    @app.post('/knowledge/research')
    def literature_research(req:LiteratureResearch):
        if composer is None:raise HTTPException(503,'로컬 모델이 활성화되지 않았습니다.')
        from .knowledge_lab import KnowledgeStore
        from .evidence_graph import EvidenceGraph
        profile=os.getenv('LITERATURE_RERANKER','bge')
        if profile not in ('bge','tiny'):raise HTTPException(503,'문헌 재평가 모델 설정을 확인해주세요.')
        english=profile=='tiny' and req.mode in ('compact','fast','contextual','anchored')
        translated=req.mode in ('compact','fast','contextual','anchored')
        try:resources=get_literature_resources(req.mode=='fast',english,translated)
        except (FileNotFoundError,ValueError):raise HTTPException(503,'로컬 문헌 모델과 후보 예산 설정을 확인해주세요.') from None
        return EvidenceGraph(KnowledgeStore(knowledge_path),composer.generator,resources['english_reranker' if english else 'reranker'],
                             prefilter=resources.get('prefilter'),document_prefilter=resources.get('document_prefilter') if translated else None).build(req.question,req.mode)

    @app.post('/canvas/compose')
    def canvas_compose(req: ComposeRequest):
        if composer is None:
            raise HTTPException(503, 'RAG_ENABLE_CANVAS=1로 로컬 화면 설계 모델을 활성화해주세요.')
        try:
            return composer.compose(req)
        except ComposeConflict as e:
            raise HTTPException(409, str(e)) from None

    @app.post('/canvas/evidence')
    def screen_evidence(req: ComposeRequest):
        """Read-only evidence preview using the same bounded tool as screen composition."""
        if composer is None:raise HTTPException(503, '로컬 모델이 활성화되지 않았습니다.')
        from .evidence_agent import EvidenceAgent
        return EvidenceAgent(pipeline,composer.generator,composer.component_ranker).run(
            req.message,req.supported_widgets or [],req.institution,req.as_of,
            'adaptive' if req.evidence_mode=='adaptive' else 'once')

    from fastapi.responses import FileResponse
    @app.get('/canvas/preview', include_in_schema=False)
    def canvas_preview():
        return FileResponse(ROOT / 'rag_backend' / 'canvas_preview.html')

    from .canvas_jobs import CanvasJobs, QueueFull, RequestConflict
    jobs = CanvasJobs(composer,path=store.path.with_suffix('.jobs.db')) if composer else None
    app.state.canvas_jobs = jobs

    @app.post('/canvas/jobs', status_code=202)
    def submit_canvas_job(body: JobSubmission):
        if jobs is None:raise HTTPException(503, '로컬 화면 모델이 활성화되지 않았습니다.')
        try:return jobs.submit(body.request, body.client_request_id)
        except QueueFull as e:raise HTTPException(429, str(e)) from None
        except RequestConflict as e:raise HTTPException(409, str(e)) from None

    @app.get('/canvas/jobs/{job_id}')
    def read_canvas_job(job_id: str):
        if jobs is None:raise HTTPException(503, '로컬 화면 모델이 활성화되지 않았습니다.')
        result=jobs.get(job_id)
        if result is None:raise HTTPException(404, '작업이 없거나 만료되었습니다.')
        return result

    return app
