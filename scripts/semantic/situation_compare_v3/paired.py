# coding: utf-8
"""Paired actual comparison; frozen hybrid inference unchanged, strong compact direct baseline."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent;BASE=HERE.parent/'situation_v3';sys.path.insert(0,str(BASE))
path=BASE/'run.py';source=path.read_text()
source=source.replace("'llm_full_catalog':'gpt-4o-mini-2024-07-18'", "'llm_full_catalog':'gpt-4.1-2025-04-14'")
source=source.replace("choices=['hybrid'],default=['hybrid']", "choices=['hybrid','llm_full_catalog'],default=['hybrid','llm_full_catalog']")
start=source.index("    elif self.path=='/plain':");end=source.index('    else:self.respond(404,{})',start)
source=source[:start]+(HERE/'plain-adapter.txt').read_text()+source[end:]
old="selection_policy=re.search(r'static final String POLICY=\"\"\"(.*?)\"\"\";',policy_source,re.S).group(1).strip()"
assert old in source;source=source.replace(old,"selection_policy=Path("+repr(str(HERE/'baseline-policy.txt'))+").read_text()")
source=source.replace("model=body.get('model'),planner_content=", "model=body.get('model'),baseline_content=body.get('choices',[{}])[0].get('message',{}).get('content') if provider=='llm_full_catalog' else None,planner_content=")
source=source.replace("queued=queue_wait() if provider=='llm_full_catalog' else 0;", "queued=shared_wait(28000 if provider=='llm_full_catalog' else 21000);")
# Safe typed provider diagnostics; no key values or response headers containing credentials.
old="except urllib.error.HTTPError as e:record.update(error='HTTP '+str(e.code),http_status=e.code);raise"
new="except urllib.error.HTTPError as e:\n   record.update(error='HTTP '+str(e.code),http_status=e.code)\n   try:\n    detail=json.loads(e.read()).get('error',{});record['error_detail']={k:detail.get(k) for k in ['code','type','param']}\n   except Exception:pass\n   raise"
assert old in source;source=source.replace(old,new)
source=source.replace('from common import sha,load_keys,usage_counts','from common import sha,load_keys,usage_counts\nfrom rate_gate import wait as shared_wait')
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
