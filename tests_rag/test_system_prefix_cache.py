from rag_backend.system_prefix_cache import SystemPrefixCache


class Tokenizer:
    bos_token=None
    def apply_chat_template(self,messages,**kwargs):return 'SYS:'+messages[0]['content']+'|'
    def encode(self,text,**kwargs):return list(text.encode())


class Layer:
    nbytes=16
    def __init__(self,tokens):self.tokens=list(tokens)


def test_user_suffix_is_never_stored_and_working_copy_cannot_mutate_system_prefix():
    calls=[]
    def prefill(tokens):calls.append(tokens);return [Layer(tokens)]
    cache=SystemPrefixCache(Tokenizer(),prefill)
    suffix,working,trace=cache.prepare('rules','SYS:rules|USER:alpha')
    assert suffix=='USER:alpha' and trace['hit'] is False
    working[0].tokens.append(999)
    suffix,second,trace=cache.prepare('rules','SYS:rules|USER:beta')
    assert suffix=='USER:beta' and trace['hit']
    assert second[0].tokens==list(b'SYS:rules|') and len(calls)==1


def test_changed_system_and_lru_byte_budget_invalidate_reuse():
    cache=SystemPrefixCache(Tokenizer(),lambda tokens:[Layer(tokens)],max_entries=2,max_bytes=20)
    cache.prepare('a','SYS:a|USER:x');cache.prepare('b','SYS:b|USER:x')
    assert cache.snapshot()['entries']==1 and cache.snapshot()['evictions']==1
    assert not cache.prepare('a','SYS:a|USER:y')[2]['hit']


def test_non_roundtripping_boundary_bypasses_without_prefill():
    class BOS(Tokenizer):
        def encode(self,text,**kwargs):return [999]+super().encode(text,**kwargs)
    def never(tokens):raise AssertionError('unsafe token boundary must bypass')
    cache=SystemPrefixCache(BOS(),never)
    prompt,working,trace=cache.prepare('rules','SYS:rules|USER:x')
    assert prompt=='SYS:rules|USER:x' and working is None and 'bypass' in trace
