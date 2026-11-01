import unittest,tempfile,copy
from pathlib import Path
from unittest.mock import patch
import server as m
class VideoResolution(unittest.TestCase):
 def setUp(self):
  from tests.support import legacy_engine
  guard=patch.object(m.Q,'engine',return_value=legacy_engine(m));guard.start();self.addCleanup(guard.stop)
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);fix=patch.object(m,'DATA',Path(t.name));fix.start();self.addCleanup(fix.stop);self.pid='a'*32;m.project(self.pid).parent.mkdir()
  self.p={'id':self.pid,'ratio':'16:9','image_model':'Flux2-Klein-4B-4step-1K','video_mode':'reference','video_model':'MiniMaxH3-RedCraft-A2A-beta1-8step-R2V-2K','assets':[{'id':'a','type':'场景','image':'/room.png'}],'shots':[{'id':'s','duration':4,'video_prompt':'Duration: 4s\nA quiet room.','image_prompt':'A room.','asset_ids':['a'],'versions':[]}]}
 def launch(self,kind='video'):
  m.save(m.project(self.pid),self.p)
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',return_value='bytes'):return m.launch(self.pid,'shot','s',kind)
 def test_project_preset_and_task_snapshot(self):
  self.p['video_resolution']={'preset':'480p'};j=self.launch();self.assertEqual(j['request']['video_size'],{'width':848,'height':480});self.assertEqual(j['video_resolution']['source'],'project')
  self.p['video_resolution']={'preset':'2k'};self.assertEqual(j['request']['video_size']['width'],848)
 def test_portrait_tier_and_custom_literal_dimensions(self):
  self.p.update(ratio='9:16',video_resolution={'preset':'720p'});self.assertEqual(self.launch()['request']['video_size'],{'width':720,'height':1280})
  self.p['video_resolution']={'preset':'custom','width':720,'height':480};self.assertEqual(self.launch()['request']['video_size'],{'width':720,'height':480})
 def test_shot_resolution_is_independent_of_route_override(self):
  self.p['video_resolution']={'preset':'2k'};self.p['shots'][0]['video_resolution']={'preset':'240p'};j=self.launch();self.assertEqual(j['request']['video_size'],{'width':432,'height':240});self.assertEqual(j['video_resolution']['source'],'shot');self.assertNotIn('video_override',self.p['shots'][0])
  self.p['shots'][0]['video_resolution']=None;self.assertEqual(self.launch()['request']['video_size']['width'],2048)
 def test_legacy_alias_is_preserved_until_resolution_selected(self):
  alias='MiniMaxH3-RedCraft-A2A-beta1-8step-R2V-480P-Preview';self.p['video_model']=alias;j=self.launch();self.assertEqual(j['request']['model'],alias);self.assertNotIn('video_size',j['request'])
  self.p['video_resolution']={'preset':'1080p'};j=self.launch();self.assertEqual(j['request']['model'],m.VIDEO_MODEL_ALIASES[alias][0]);self.assertEqual(j['request']['video_size'],{'width':1920,'height':1080})
 def test_invalid_custom_and_preset_rejected(self):
  for config in [{'preset':'bad'},'480p',{'preset':'custom','width':721,'height':480},{'preset':'custom','width':True,'height':480},{'preset':'custom','width':64,'height':480},{'preset':'custom','width':4096,'height':4096}]:
   with self.subTest(config=config),self.assertRaises(ValueError):m.merge_save(copy.deepcopy(self.p),{'video_resolution':config})
 def test_save_keeps_project_and_shot_resolution(self):
  q=copy.deepcopy(self.p);q['shots'][0]['video_resolution']={'preset':'360p'};m.merge_save(self.p,{'video_resolution':{'preset':'720p'},'shots':q['shots']});self.assertEqual(self.p['video_resolution']['preset'],'720p');self.assertEqual(self.p['shots'][0]['video_resolution']['preset'],'360p')
 def test_images_are_not_affected(self):
  self.p['video_resolution']={'preset':'240p'};j=self.launch('image');self.assertNotIn('video_size',j['request']);self.assertEqual(j['request']['aspect_ratio'],'16:9')
 def test_version_carries_actual_resolution(self):
  self.p['video_resolution']={'preset':'custom','width':720,'height':480};j=self.launch()
  with patch.object(m,'job_save'):m.finish_job(self.pid,j,'/result.mp4')
  self.assertEqual(m.load(self.pid)['shots'][0]['versions'][0]['video_resolution']['width'],720)
 def test_catalog_exposes_aliases_and_capability(self):
  c=m.model_catalog();alias=next(v for v in c['videos'] if v['id'].endswith('R2V-480P-Preview'));self.assertEqual(alias['legacy_resolution'],'480p');self.assertTrue(alias['supports_resolution']);self.assertIn('2K',alias['canonical_model']);self.assertEqual(c['video_resolutions']['240p'],[432,240])
if __name__=='__main__':unittest.main()
