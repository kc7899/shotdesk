import copy,unittest
from unittest.mock import patch
import server as m
class RetiredShotMedia(unittest.TestCase):
 def project(self):
  return {'assets':[{'id':'scene','type':'场景','name':'Room','image':'/shared.png','versions':[{'id':'asset-v','kind':'image','url':'/shared.png'}]}], 'shots':[{'id':'shot','duration':4,'video_prompt':'Duration: 4s\nA room.','asset_ids':['scene'],'versions':[],'image':None,'video':None,'image_completed':False,'video_completed':False}], 'retired_shot_media':{'shot':{'version_ids':['old-image','old-video'],'image_urls':['/shared.png'],'video_urls':['/old.mp4']}}}
 def test_stale_browser_save_cannot_restore_cleared_shot_media_or_completion(self):
  p=self.project();incoming=copy.deepcopy(p);s=incoming['shots'][0];s.update(image='/shared.png',video='/old.mp4',image_completed=True,video_completed=True,versions=[{'id':'old-image','kind':'image','url':'/shared.png'},{'id':'old-video','kind':'video','url':'/old.mp4'}]);assets=copy.deepcopy(p['assets'])
  m.merge_save(p,incoming)
  s=p['shots'][0];self.assertIsNone(s['image']);self.assertIsNone(s['video']);self.assertEqual(s['versions'],[]);self.assertFalse(s['image_completed']);self.assertFalse(s['video_completed']);self.assertEqual(p['assets'][0]['image'],assets[0]['image']);self.assertEqual(p['assets'][0]['versions'][0]['id'],'asset-v')
 def test_new_results_and_audio_survive_old_browser_save(self):
  p=self.project();old=copy.deepcopy(p);p['shots'][0].update(image='/new.png',video='/new.mp4',versions=[{'id':'new','kind':'image','url':'/new.png'},{'id':'audio','kind':'audio','url':'/voice.wav'}]);old['shots'][0].update(image='/shared.png',video='/old.mp4',versions=[{'id':'old-image','kind':'image','url':'/shared.png'}])
  m.merge_save(p,old);s=p['shots'][0];self.assertEqual(s['image'],'/new.png');self.assertEqual(s['video'],'/new.mp4');self.assertEqual({v['id'] for v in s['versions']},{'new','audio'})
if __name__=='__main__':unittest.main()
