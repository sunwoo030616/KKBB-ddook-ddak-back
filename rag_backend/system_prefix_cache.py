"""Bounded system-only KV prefixes. User tokens never enter stored cache entries."""
from collections import OrderedDict
import copy
import hashlib
from threading import Lock


def encode_for_generate(tokenizer,text):
    bos=tokenizer.bos_token
    return tokenizer.encode(text,add_special_tokens=bos is None or not text.startswith(bos))


class SystemPrefixCache:
    def __init__(self,tokenizer,prefill,clone=copy.deepcopy,max_entries=4,max_bytes=192*1024*1024,max_tokens=1024):
        if min(max_entries,max_bytes,max_tokens)<1:raise ValueError('positive_prefix_cache_limits_required')
        self.tokenizer=tokenizer;self.prefill=prefill;self.clone=clone
        self.max_entries=max_entries;self.max_bytes=max_bytes;self.max_tokens=max_tokens
        self.entries=OrderedDict();self.bytes=0;self.lock=Lock()
        self.stats={'hits':0,'misses':0,'bypasses':0,'evictions':0,'reused_tokens':0}

    def prepare(self,system,full_prompt):
        prefix=self.tokenizer.apply_chat_template([{'role':'system','content':system}],
            tokenize=False,add_generation_prompt=False,enable_thinking=False)
        if not full_prompt.startswith(prefix):return self.bypass(full_prompt,'template_prefix_mismatch')
        prefix_tokens=encode_for_generate(self.tokenizer,prefix)
        full_tokens=encode_for_generate(self.tokenizer,full_prompt)
        suffix=full_prompt[len(prefix):];suffix_tokens=encode_for_generate(self.tokenizer,suffix)
        # String slicing is safe only when the exact token concatenation is identical.
        if (not prefix_tokens or len(prefix_tokens)>self.max_tokens or not suffix_tokens or
            prefix_tokens+suffix_tokens!=full_tokens):return self.bypass(full_prompt,'token_prefix_mismatch_or_budget')
        key=hashlib.sha256(prefix.encode()).hexdigest()
        with self.lock:
            hit=key in self.entries
            if hit:
                cache,size=self.entries[key];self.entries.move_to_end(key)
                self.stats['hits']+=1;self.stats['reused_tokens']+=len(prefix_tokens)
            else:
                cache=self.prefill(prefix_tokens);size=sum(layer.nbytes for layer in cache)
                self.stats['misses']+=1
                if size<=self.max_bytes:
                    self.entries[key]=(cache,size);self.bytes+=size
                    while len(self.entries)>self.max_entries or self.bytes>self.max_bytes:
                        _,(_,removed)=self.entries.popitem(last=False)
                        self.bytes-=removed;self.stats['evictions']+=1
            # Stored objects are never passed to generation, which mutates KV layers.
            working=self.clone(cache)
        return suffix,working,{'enabled':True,'hit':hit,'prefix_tokens':len(prefix_tokens),
                               'reused_tokens':len(prefix_tokens) if hit else 0,'entry_bytes':size}

    def bypass(self,full_prompt,reason):
        with self.lock:self.stats['bypasses']+=1
        return full_prompt,None,{'enabled':True,'hit':False,'reused_tokens':0,'bypass':reason}

    def snapshot(self):
        if not self.lock.acquire(blocking=False):return {'busy':True,'scope':'Prefix preparation in progress.'}
        try:return {**self.stats,'entries':len(self.entries),'bytes':self.bytes,
                    'scope':'System-prefix KV only, in process. No user tokens or full response memoization.'}
        finally:self.lock.release()
