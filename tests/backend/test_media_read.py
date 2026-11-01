import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import server as m
class SharedRead(unittest.TestCase):
 def test_shared_state(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'DATA',Path(d)):
   pid='a'*32;m.project(pid).parent.mkdir()
   m.save(m.project(pid),{'assets':[],'shots':[{'id':'s','duration':4,'versions':[{'id':'v1','kind':'image','url':'/one'},{'id':'v2','kind':'video','url':'/two'}]}]})
   stale=m.load(pid)
   self.assertEqual(len(m.read_media(pid,{'kind':'image'},True)['items']),1)
   self.assertEqual(m.read_media(pid,{'kind':'image'},True)['items'],[])
   m.update(pid,lambda p:m.merge_save(p,stale))
   self.assertIn('v1',m.load(pid)['media_read'])
   m.update(pid,lambda p:p['shots'][0]['versions'].append({'id':'v3','kind':'image','url':'/three'}))
   m.read_media(pid,{'version_ids':['v1','v2']})
   self.assertEqual([v['version_id'] for v in m.media_items(m.load(pid)) if not v['read']],['v3'])
   with self.assertRaises(ValueError):m.read_media(pid,{'version_ids':['v3','bad']})
   self.assertNotIn('v3',m.load(pid)['media_read'])
   self.assertEqual(len(m.read_media(pid,{'limit':1},True)['items']),1)
   self.assertEqual(len(m.read_media(pid,{'include_read':True},True)['items']),3)
   self.assertEqual(len(json.loads(m.project(pid).read_text())['media_read']),3)
if __name__=='__main__':unittest.main()
