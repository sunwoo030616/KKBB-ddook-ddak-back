"""Small CPU reranker for explicitly English research queries, never financial Korean routing."""
import math
from threading import Lock


class EnglishLiteratureReranker:
    def __init__(self):
        import torch
        from sentence_transformers import CrossEncoder
        from .research_models import manifest
        path,self.identity=manifest('literature_reranker')
        if self.identity.get('language')!='en':raise ValueError('english_model_manifest_required')
        from .model_integrity import verify_snapshot
        self.verification=verify_snapshot(path,self.identity)
        torch.set_num_threads(2)
        self.device='cpu';self.dtype='float32';self.lock=Lock()
        self.model=CrossEncoder(str(path),device='cpu',max_length=512,
            model_kwargs={'torch_dtype':torch.float32},local_files_only=True,trust_remote_code=False)

    def score_pairs(self,pairs):
        if not pairs:return []
        if any(not q.isascii() for q,text in pairs):raise ValueError('english_ascii_research_query_required')
        with self.lock:
            scores=[float(x) for x in self.model.predict(pairs,batch_size=16,
                show_progress_bar=False,convert_to_numpy=True)]
        if len(scores)!=len(pairs) or not all(math.isfinite(s) for s in scores):
            raise ValueError('invalid_literature_reranker_scores')
        return scores
