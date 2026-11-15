"""Conservative shared rolling-minute quota, including reservations by both processes."""
import json,time,fcntl
from pathlib import Path
PATH=Path('/private/tmp/kkbb-gpt41-rolling-minute-v3.json')
def wait(tokens=24000):
 start=time.monotonic()
 while True:
  PATH.touch(exist_ok=True)
  with PATH.open('r+') as f:
   fcntl.flock(f,fcntl.LOCK_EX);f.seek(0)
   try:s=json.load(f)
   except ValueError:s={'not_before':time.time()+65,'events':[]}
   now=time.time();s['events']=[e for e in s['events'] if now-e[0]<65]
   total=sum(e[1] for e in s['events']);delay=max(0,s['not_before']-now)
   if not delay and total+tokens<=330000:
    s['events'].append([now,tokens]);f.seek(0);json.dump(s,f);f.truncate();return (time.monotonic()-start)*1000
   if not delay:delay=max(.1,65-(now-s['events'][0][0]))
   f.seek(0);json.dump(s,f);f.truncate()
  time.sleep(min(5,delay))
