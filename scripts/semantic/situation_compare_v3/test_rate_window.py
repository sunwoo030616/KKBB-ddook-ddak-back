"""Regression test for concurrent reservation persistence; no network or provider calls."""
import unittest,tempfile,json,subprocess,sys,os,concurrent.futures
from pathlib import Path
class SharedRateWindowTest(unittest.TestCase):
 def test_two_processes_retain_both_reservations_and_valid_json(self):
  module=Path(__file__).with_name('rate_window.py').resolve()
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'reservations.json';path.write_text(json.dumps({'not_before':0,'events':[]}))
   code="import importlib.util;from pathlib import Path;import sys;s=importlib.util.spec_from_file_location('gate',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.PATH=Path(sys.argv[2]);m.wait(10)"
   def run(_):subprocess.run([sys.executable,'-c',code,str(module),str(path)],check=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
   with concurrent.futures.ThreadPoolExecutor(2) as pool:list(pool.map(run,range(2)))
   data=json.loads(path.read_text());self.assertEqual(len(data['events']),2);self.assertEqual(sum(e[1] for e in data['events']),20)
if __name__=='__main__':unittest.main()
