"""Small verified English document encoder for translated research queries."""
from threading import Lock

from .retrieval_acceleration import SpanPrefilter


class EnglishLiteratureEncoder:
    def __init__(self):
        import torch
        from sentence_transformers import SentenceTransformer
        from .research_models import manifest
        from .model_integrity import verify_snapshot
        path,self.identity=manifest('literature_encoder')
        if self.identity.get('language')!='en':raise ValueError('english_encoder_manifest_required')
        self.verification=verify_snapshot(path,self.identity)
        torch.set_num_threads(2)
        self.model=SentenceTransformer(str(path),device='cpu',local_files_only=True,trust_remote_code=False)
        self.name=self.identity['repo_id']+'@'+self.identity['revision'];self.lock=Lock()

    def encode(self,texts):
        with self.lock:
            return self.model.encode(texts,batch_size=16,normalize_embeddings=True,
                convert_to_numpy=True,show_progress_bar=False).tolist()


class DocumentPrefilter:
    def __init__(self,encoder,path,limit=10):
        if not 3<=limit<=20:raise ValueError('invalid_document_candidate_budget')
        self.base=SpanPrefilter(encoder,path);self.limit=limit;self.encoder=encoder

    def select(self,query,spans,per_document=1):
        return self.base.select(query,spans,per_document)[:self.limit]
