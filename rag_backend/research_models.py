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


def schema_fingerprint(output_type):
    return hashlib.sha256(json.dumps(output_type.model_json_schema(),sort_keys=True).encode()).hexdigest()


def manifest(role):
    path = MODEL_ROOT / role
    data = json.loads((path / 'manifest.local.json').read_text())
    # Weights and tokenizer/config identity are recorded by the explicit prepare command.
    return path, data


class LazyMLXGenerator:
    """Unchanged curation jobs need identity checks, not GPU model loading."""
    def __init__(self,role='canvas_generator'):
        self.role=role;_,self.identity=manifest(role)
        self.generator=None;self.lock=Lock();self.loads=0

    def complete(self,*args,**kwargs):
        with self.lock:
            if self.generator is None:
                self.generator=MLXGenerator(self.role);self.loads+=1
        return self.generator.complete(*args,**kwargs)


class MLXGenerator:
    def __init__(self, role='generator'):
        import mlx.core as mx
        from mlx_lm import load
        self.path, self.identity = manifest(role)
        from .model_integrity import verify_snapshot
        from .inference_resources import configure_mlx_cache
        self.verification=verify_snapshot(self.path,self.identity)
        self.resource_policy=configure_mlx_cache(mx)
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
        self.system_prefix_cache=None
        if os.getenv('RAG_SYSTEM_PREFIX_CACHE')=='1':
            from .system_prefix_cache import SystemPrefixCache
            self.system_prefix_cache=SystemPrefixCache(self.tokenizer,self._prefill_system)

    def _prefill_system(self,tokens):
        import mlx.core as mx
        from mlx_lm.models.cache import make_prompt_cache,KVCache
        cache=make_prompt_cache(self.model)
        if any(type(layer) is not KVCache for layer in cache):raise ValueError('unsupported_system_prefix_cache_type')
        self.model(mx.array(tokens)[None],cache=cache)
        mx.eval([layer.state for layer in cache])
        # Store only system tokens, including no unused capacity or user suffix.
        for layer in cache:
            keys,values,offset=layer.state
            layer.state=(mx.asarray(keys[...,:offset,:],copy=True),mx.asarray(values[...,:offset,:],copy=True),offset)
        mx.eval([layer.state for layer in cache])
        return cache

    def complete(self, system, user, max_tokens=500, output_type=None):
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
        prompt = self.tokenizer.apply_chat_template(
            [{'role':'system','content':system},{'role':'user','content':user}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        started = time.perf_counter()
        with self.lock:
            acquired = time.perf_counter()
            schema_cache_hit=False;grammar_setup_ms=0
            prefix_started=time.perf_counter()
            generation_prompt=prompt;extras={};prefix_trace={'enabled':False,'reused_tokens':0}
            if self.system_prefix_cache is not None:
                generation_prompt,prompt_cache,prefix_trace=self.system_prefix_cache.prepare(system,prompt)
                if prompt_cache is not None:extras['prompt_cache']=prompt_cache
            prefix_setup_ms=(time.perf_counter()-prefix_started)*1000
            processors=None
            if output_type is not None:
                import outlines
                schema_key=schema_fingerprint(output_type)
                schema_cache_hit=schema_key in self.structured_generators
                setup_started=time.perf_counter()
                if not schema_cache_hit:
                    # Dynamic per-request schemas must not retain unbounded generators.
                    if len(self.structured_generators)>=64:
                        self.structured_generators.pop(next(iter(self.structured_generators)))
                    self.structured_generators[schema_key] = outlines.Generator(self.constrained_model, output_type)
                grammar_setup_ms=(time.perf_counter()-setup_started)*1000
                processor=self.structured_generators[schema_key].logits_processor
                if processor is not None:processor.reset();processors=[processor]
            # Same MLX stream used by mlx_lm.generate, with first-token and
            # prefill/decode observations instead of an opaque total only.
            generation_started=time.perf_counter();first_token_ms=None;response=None;text=''
            for response in stream_generate(self.model,self.tokenizer,prompt=generation_prompt,
                    max_tokens=max_tokens,sampler=make_sampler(temp=0),logits_processors=processors,**extras):
                if first_token_ms is None:first_token_ms=(time.perf_counter()-generation_started)*1000
                text+=response.text
            generation_ms=(time.perf_counter()-generation_started)*1000
        return {'text':text, 'latency_ms':round((time.perf_counter()-started)*1000,3),
                'lock_wait_ms':round((acquired-started)*1000,3),
                'schema_cache_hit':schema_cache_hit,'grammar_setup_ms':round(grammar_setup_ms,3),
                'prefix_setup_ms':round(prefix_setup_ms,3),'first_token_ms':round(first_token_ms,3) if first_token_ms is not None else None,
                'generation_ms':round(generation_ms,3),'prefill_ms':round(response.prompt_tokens/response.prompt_tps*1000,3) if response and response.prompt_tps>0 else None,
                'generation_tps':response.generation_tps if response else None,'finish_reason':response.finish_reason if response else None,
                'system_prefix_cache':prefix_trace,
                'prompt_tokens':len(self.tokenizer.encode(prompt)),
                'output_tokens':len(self.tokenizer.encode(text)),
                'max_tokens':max_tokens, 'constrained_decoding':output_type is not None, 'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}


class CrossEncoderReranker:
    def __init__(self):
        import torch
        from sentence_transformers import CrossEncoder
        self.path, self.identity = manifest('reranker')
        from .model_integrity import verify_snapshot
        self.verification=verify_snapshot(self.path,self.identity)
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
            from .inference_resources import release_unused_mps
            self.memory_stats=release_unused_mps(__import__('torch'),getattr(self,'device','cpu'))
        return scores

    def rerank(self, question, hits, top_k):
        if not hits:
            return []
        values=self.score_pairs([(question, f'{h.title}\n{h.section}\n{h.text}') for h in hits])
        ranked=sorted(zip(hits,values),key=lambda item:(-float(item[1]),item[0].chunk_id))
        return [hit.model_copy(update={'score':float(score)}) for hit,score in ranked[:top_k]]
