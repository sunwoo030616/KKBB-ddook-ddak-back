"""Optional local neural models. Runtime reads local snapshots; no remote-code execution."""
from pathlib import Path
from threading import Lock
import os
import hashlib
import json
import math
import time

from .store import ROOT

MODEL_ROOT = ROOT / 'var' / 'research_models'


def manifest(role):
    path = MODEL_ROOT / role
    data = json.loads((path / 'manifest.local.json').read_text())
    # Weights and tokenizer/config identity are recorded by the explicit prepare command.
    return path, data


class MLXGenerator:
    def __init__(self, role='generator'):
        from mlx_lm import load
        self.path, self.identity = manifest(role)
        self.model, self.tokenizer = load(str(self.path), tokenizer_config={'trust_remote_code': False})
        os.environ.setdefault('OUTLINES_CACHE_DIR', str(ROOT / 'var' / 'outlines-cache'))
        import outlines
        outlines.disable_cache()
        self.constrained_model = outlines.from_mlxlm(self.model, self.tokenizer)
        # We already applied system/user roles and disabled thinking above. Outlines
        # otherwise wraps a str prompt in a second user chat template, losing that contract.
        self.constrained_model.type_adapter.has_chat_template = False
        self.structured_generators = {}
        self.lock = Lock()

    def complete(self, system, user, max_tokens=500, output_type=None):
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler
        prompt = self.tokenizer.apply_chat_template(
            [{'role':'system','content':system},{'role':'user','content':user}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        started = time.perf_counter()
        with self.lock:
            acquired = time.perf_counter()
            if output_type is None:
                text = generate(self.model, self.tokenizer, prompt=prompt, max_tokens=max_tokens,
                                sampler=make_sampler(temp=0), verbose=False)
            else:
                import outlines
                if output_type not in self.structured_generators:
                    # Dynamic per-request schemas must not retain unbounded generators.
                    if len(self.structured_generators)>=64:
                        self.structured_generators.pop(next(iter(self.structured_generators)))
                    self.structured_generators[output_type] = outlines.Generator(self.constrained_model, output_type)
                text = self.structured_generators[output_type](prompt, max_tokens=max_tokens,
                                                               sampler=make_sampler(temp=0), verbose=False)
        return {'text':text, 'latency_ms':round((time.perf_counter()-started)*1000,3),
                'lock_wait_ms':round((acquired-started)*1000,3),
                'prompt_tokens':len(self.tokenizer.encode(prompt)),
                'output_tokens':len(self.tokenizer.encode(text)),
                'max_tokens':max_tokens, 'constrained_decoding':output_type is not None, 'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}


class CrossEncoderReranker:
    def __init__(self):
        import torch
        from sentence_transformers import CrossEncoder
        self.path, self.identity = manifest('reranker')
        torch.set_num_threads(2)
        requested=os.getenv('RERANKER_DEVICE','auto')
        if requested not in ('cpu','mps','auto'):raise ValueError('unsupported_reranker_device')
        self.device=('mps' if torch.backends.mps.is_available() else 'cpu') if requested=='auto' else requested
        if self.device=='mps' and not torch.backends.mps.is_available():raise ValueError('mps_not_available')
        self.dtype='float16' if self.device=='mps' else 'float32'
        self.model = CrossEncoder(str(self.path), device=self.device, max_length=512,
                                  model_kwargs={'torch_dtype':getattr(torch,self.dtype)},
                                  local_files_only=True, trust_remote_code=False)
        self.lock = Lock()

    def score_pairs(self, pairs):
        if not pairs:
            return []
        with self.lock:
            values=self.model.predict(pairs,batch_size=4,show_progress_bar=False,convert_to_numpy=True)
        scores=[float(v) for v in values]
        if not all(math.isfinite(v) for v in scores):raise ValueError('nonfinite_reranker_score')
        return scores

    def rerank(self, question, hits, top_k):
        if not hits:
            return []
        values=self.score_pairs([(question, f'{h.title}\n{h.section}\n{h.text}') for h in hits])
        ranked=sorted(zip(hits,values),key=lambda item:(-float(item[1]),item[0].chunk_id))
        return [hit.model_copy(update={'score':float(score)}) for hit,score in ranked[:top_k]]
