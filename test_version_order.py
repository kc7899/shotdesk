import copy,unittest
import server as m
class VersionOrder(unittest.TestCase):
 def test_mixed_versions_and_latest(self):
  p={'shots':[{'id':'s','duration':4,'image':'old','versions':[{'id':'c','kind':'image','created':30,'version':99,'url':'new'},{'id':'a','kind':'image','created':10,'version':7,'url':'old'},{'id':'d','kind':'video','created':40,'url':'video'},{'id':'b','kind':'image','created':20,'url':'mid'}]}],'assets':[]}
  m.normalize_versions(p);s=p['shots'][0]
  self.assertEqual([v['id'] for v in s['versions']],['d','c','b','a'])
  self.assertEqual([v['version'] for v in s['versions']],[1,3,2,1])
  self.assertEqual(s['latest_version_ids'],{'image':'c','video':'d','audio':None})
  self.assertEqual(s['image'],'old')
  self.assertEqual(sum(v['is_latest'] for v in s['versions']),2)
  expected=copy.deepcopy(p);m.normalize_versions(p);self.assertEqual(p,expected)
  stale=copy.deepcopy(p);stale['shots'][0]['versions'][1]['created']=1
  m.merge_save(p,stale);self.assertEqual(p['shots'][0]['versions'][1]['created'],30)
 def test_tie_and_missing_time(self):
  p={'assets':[{'versions':[{'id':'a','kind':'image','created':1},{'id':'b','kind':'image','created':1},{'id':'c','kind':'image'}]}]}
  m.normalize_versions(p);self.assertEqual([v['id'] for v in p['assets'][0]['versions']],['b','a','c'])
if __name__=='__main__':unittest.main()
