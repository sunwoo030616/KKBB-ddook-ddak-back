"""Bounded local OPUS-MT translation, not unconstrained query rewriting."""
import re
from threading import Lock
import time
import unicodedata


def english_text(text):
    value=unicodedata.normalize('NFKC',text).translate(str.maketrans({'’':"'",'‘':"'",'“':'"','”':'"','–':'-','—':'-','…':'...'})).strip()
    if not value or not value.isascii():raise ValueError('invalid_english_translation')
    return value


class LiteratureTranslator:
    def __init__(self,role='literature_translator_small'):
        import torch
        from transformers import MarianMTModel,MarianTokenizer
        from .research_models import manifest
        from .model_integrity import verify_snapshot
        path,self.identity=manifest(role)
        if self.identity.get('language')!='ko-en':raise ValueError('korean_english_translation_manifest_required')
        self.verification=verify_snapshot(path,self.identity)
        torch.set_num_threads(2)
        self.tokenizer=MarianTokenizer.from_pretrained(str(path),local_files_only=True)
        self.model=MarianMTModel.from_pretrained(str(path),local_files_only=True,
            trust_remote_code=False,weights_only=True,dtype=torch.float32,attn_implementation='eager').eval()
        self.lock=Lock()

    def translate(self,texts):
        import torch
        if not 1<=len(texts)<=3 or any(not isinstance(t,str) or not t.strip() or len(t)>500 for t in texts):
            raise ValueError('invalid_translation_input')
        started=time.perf_counter();queries=[t if re.search(r'[가-힣]',t) else english_text(t) for t in texts]
        pending=[i for i,t in enumerate(texts) if re.search(r'[가-힣]',t)]
        if pending:
            with self.lock,torch.inference_mode():
                inputs=self.tokenizer([texts[i] for i in pending],return_tensors='pt',padding=True,truncation=False)
                if inputs['input_ids'].shape[1]>256:raise ValueError('translation_source_too_long')
                for ids in inputs['input_ids'].tolist():
                    usable=[id for id in ids if id not in (self.tokenizer.pad_token_id,self.tokenizer.eos_token_id)]
                    if not usable or usable.count(self.tokenizer.unk_token_id)/len(usable)>.2:
                        raise ValueError('translation_tokenizer_unknown_ratio')
                result=self.model.generate(**inputs,max_new_tokens=128,num_beams=2,do_sample=False)
                if any(self.tokenizer.eos_token_id not in tokens[1:] for tokens in result.tolist()):
                    raise ValueError('translation_output_truncated')
                for i,translated in zip(pending,self.tokenizer.batch_decode(result,skip_special_tokens=True)):
                    queries[i]=english_text(translated)
        return queries,{'step':'translate_clauses','latency_ms':round((time.perf_counter()-started)*1000,3),
            'translated_clauses':len(pending),'model_calls':int(bool(pending)),
            'generator_calls':0,'model':self.identity,'scope':'Translation preserves clauses; semantic fidelity still requires evaluation.'}
