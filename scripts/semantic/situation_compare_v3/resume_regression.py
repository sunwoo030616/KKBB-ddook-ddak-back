"""Resume frozen regression using the same shared OpenAI pacing as the paired run."""
from pathlib import Path
import sys
from rate_gate import wait as shared_wait
path=Path(__file__).resolve().parents[1]/'situation_v3/resume.py';sys.path.insert(0,str(path.parent));source=path.read_text()
old='last_start=[time.monotonic()-3]\\n def queue_wait():\\n  delay=max(0,3-(time.monotonic()-last_start[0]));time.sleep(delay);last_start[0]=time.monotonic();return delay*1000\\n def unused_original_queue_wait():'
new='def queue_wait():return shared_wait(21000)\\n def unused_original_queue_wait():'
assert old in source;source=source.replace(old,new)
source=source.replace("{'__file__':str(path),'__name__':'__main__'}", "{'__file__':str(path),'__name__':'__main__','shared_wait':shared_wait}")
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__','shared_wait':shared_wait})
