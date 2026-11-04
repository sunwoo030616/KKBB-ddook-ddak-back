"""Small CPU multilingual reranker; no translation or remote-code execution."""
import math
from threading import Lock


class MultilingualLiteratureReranker:
    def __init__(self):
        import torch
        from sentence_transformers import CrossEncoder
        from .research_models import manifest
        from .model_integrity import verify_snapshot
        path,self.identity=manifest('literature_multilingual')
        if self.identity.get('language')!='multilingual':raise ValueError('multilingual_manifest_required')
        self.verification=verify_snapshot(path,self.identity);torch.set_num_threads(2)
        self.device='cpu';self.dtype='float32';self.lock=Lock()
        self.model=CrossEncoder(str(path),device='cpu',max_length=512,
            activation_fn=torch.nn.Identity(),model_kwargs={'dtype':torch.float32},
            local_files_only=True,trust_remote_code=False)

    def score_pairs(self,pairs):
        if not pairs:return []
        with self.lock:
            scores=[float(x) for x in self.model.predict(pairs,batch_size=8,show_progress_bar=False)]
        if len(scores)!=len(pairs) or not all(math.isfinite(s) for s in scores):raise ValueError('invalid_multilingual_scores')
        return scores
