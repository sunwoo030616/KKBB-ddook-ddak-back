import unittest,itertools
from run import chunks,pool_from,payload
from set_selection import build_choice,decode
class ProtocolTest(unittest.TestCase):
 def test_all_585_once(self):
  ids=list(range(585));parts=chunks(ids);self.assertEqual(list(map(len,parts)),[80]*7+[25]);self.assertEqual(sum(parts,[]),ids)
 def test_global_threshold_and_limit(self):
  ids=[str(i) for i in range(30)];ps={i:int(i)/100 for i in ids};self.assertEqual(pool_from(ids,ps),[])
  ps={i:.9 for i in ids};self.assertEqual(pool_from(ids,ps),ids[:10])
 def test_120_unique_sets_no_labels(self):
  ids=[str(i) for i in range(10)];menus={i:{'name':'메뉴'+i,'description':'설명','select_when':['조건']} for i in ids};p,m=build_choice('질문',ids,menus,'정책');self.assertEqual(len(m),120);self.assertEqual(len(p['questions']['menu_set']['criteria']),122);self.assertEqual(set(map(tuple,m.values())),set(itertools.combinations(ids,3)));self.assertEqual(decode({'answers':{'menu_set':{'type':'choice','choice':'set_1','confidence':.01}}},m)[0],ids[:3])
if __name__=='__main__':unittest.main()
