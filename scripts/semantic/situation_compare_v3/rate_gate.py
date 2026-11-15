"""Shared conservative OpenAI token bucket across paired and regression processes."""
import json,time,fcntl,os
from pathlib import Path
PATH=Path('/private/tmp/kkbb-gpt41-token-bucket-v3.json')
def wait(tokens=21000):
 start=time.monotonic()
 while True:
  with PATH.open('a+') as f:
   fcntl.flock(f,fcntl.LOCK_EX);f.seek(0)
   try:s=json.load(f)
   except ValueError:s={'at':time.time(),'tokens':400000}
   now=time.time();available=min(400000,s['tokens']+max(0,now-s['at'])*6500)
   if available>=tokens:
    f.seek(0);json.dump({'at':now,'tokens':available-tokens},f);f.truncate();return (time.monotonic()-start)*1000
   delay=(tokens-available)/6500
   f.seek(0);json.dump({'at':now,'tokens':available},f);f.truncate()
  time.sleep(min(5,max(.05,delay)))
