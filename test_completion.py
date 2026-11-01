import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import server as m
class Completion(unittest.TestCase):
 def test_independent_persistent_and_stale_save(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'DATA',Path(d)):
   pid='a'*32;m.project(pid).parent.mkdir();m.save(m.project(pid),{'assets':[],'shots':[{'id':'s','duration':4,'versions':[]}]})
   stale=m.load(pid);self.assertFalse(stale['shots'][0]['image_completed'])
   result=m.set_shot_completion(pid,{'shot_id':'s','kind':'image','completed':True})
   self.assertTrue(result['image_completed']);self.assertFalse(result['video_completed'])
   m.update(pid,lambda p:m.merge_save(p,stale));self.assertTrue(m.load(pid)['shots'][0]['image_completed'])
   m.read_media(pid,{'version_ids':[]});self.assertTrue(m.load(pid)['shots'][0]['image_completed'])
   m.set_shot_completion(pid,{'shot_id':'s','kind':'video','completed':True})
   m.set_shot_completion(pid,{'shot_id':'s','kind':'image','completed':False})
   shot=m.load(pid)['shots'][0];self.assertTrue(shot['video_completed']);self.assertFalse(shot['image_completed'])
   self.assertIsNone(shot['image_completed_at'])
   for body in [{'shot_id':'s','kind':'image','completed':'true'},{'shot_id':'bad','kind':'image','completed':True}]:
    with self.assertRaises(ValueError):m.set_shot_completion(pid,body)
if __name__=='__main__':unittest.main()
