import tempfile,unittest,copy
from pathlib import Path
from unittest.mock import patch
import server as m
class VideoModes(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  patcher=patch.object(m,'DATA',Path(self.tmp.name));patcher.start();self.addCleanup(patcher.stop)
  self.pid='a'*32;m.project(self.pid).parent.mkdir()
  self.p={'ratio':'16:9','image_model':'Flux2-Klein-4B-4step-1K','video_model':'MiniMaxH3-8step-I2V','assets':[{'id':'a','image':'/a.png'},{'id':'b','image':'/b.png'}],'shots':[{'id':'s','duration':4,'video_prompt':'Duration: 4s\nTwo people greet.','asset_ids':['b','a'],'video_mode':'reference','video_model':'MiniMaxH3-RedCraft-Package-4step-R2V-1K','versions':[]}]}
  self.persist()
 def persist(self):m.save(m.project(self.pid),self.p)
 def launch(self):
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',side_effect=lambda url:'bytes:'+url):return m.launch(self.pid,'shot','s','video')
 def test_reference_uses_assets_in_declared_order_without_first_frame(self):
  j=self.launch();self.assertEqual(j['request']['image'],['bytes:/b.png','bytes:/a.png'])
  self.assertNotIn('first_frame_image',j['request']);self.assertIsNone(j['source_image']);self.assertEqual(j['source_images'],['/b.png','/a.png'])
  self.assertEqual(j['request']['metadata']['gen_mode'],'imageReference')
 def test_reference_does_not_silently_omit_missing_assets(self):
  self.p['assets'][0].pop('image');self.persist()
  with self.assertRaises(ValueError):self.launch()
 def test_wrong_model_and_too_many_assets(self):
  self.p['shots'][0]['video_model']='MiniMaxH3-8step-I2V';self.persist()
  with self.assertRaises(ValueError):self.launch()
  self.p['shots'][0]['video_model']='MiniMaxH3-RedCraft-Package-4step-R2V-1K'
  self.p['assets']=[{'id':str(i),'image':'/'+str(i)+'.png'} for i in range(5)]
  self.p['shots'][0]['asset_ids']=[a['id'] for a in self.p['assets']];self.persist()
  with self.assertRaises(ValueError):self.launch()
 def test_legacy_first_frame(self):
  shot=self.p['shots'][0];shot.pop('video_mode');shot.pop('video_model');shot['image']='/still.png';self.persist()
  j=self.launch();self.assertEqual(j['request']['first_frame_image'],'bytes:/still.png');self.assertNotIn('image',j['request']);self.assertEqual(j['video_mode'],'first_frame')
 def test_batch_reference_does_not_require_first_frame(self):
  with patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',side_effect=lambda url:'bytes:'+url):result=m.launch_batch(self.pid,'video')
  self.assertEqual(len(result['jobs']),1);self.assertEqual(result['skipped'],[])
 def test_video_history_keeps_input_snapshots(self):
  j=self.launch()
  with patch.object(m,'job_save'):m.finish_job(self.pid,j,'/result.mp4')
  v=m.load(self.pid)['shots'][0]['versions'][0]
  self.assertEqual(v['video_mode'],'reference');self.assertEqual(v['source_images'],['/b.png','/a.png'])
 def test_project_mode_and_model_override_legacy_shot_settings(self):
  self.p['video_mode']='reference';self.p['video_model']='MiniMaxH3-RedCraft-Package-4step-R2V-1K'
  self.p['shots'][0]['video_mode']='first_frame';self.p['shots'][0]['video_model']='MiniMaxH3-8step-I2V';self.persist()
  j=self.launch();self.assertEqual(j['video_mode'],'reference');self.assertEqual(j['request']['model'],self.p['video_model']);self.assertNotIn('first_frame_image',j['request'])
  self.p['video_mode']='first_frame';self.p['video_model']='MiniMaxH3-8step-I2V';self.p['shots'][0]['image']='/still.png';self.p['shots'][0]['video_mode']='reference';self.persist()
  j=self.launch();self.assertEqual(j['video_mode'],'first_frame');self.assertIn('first_frame_image',j['request'])
 def test_project_mode_persists_and_rejects_invalid_value(self):
  m.update(self.pid,lambda p:m.merge_save(p,{'video_mode':'reference'}));self.assertEqual(m.load(self.pid)['video_mode'],'reference')
  with self.assertRaises(ValueError):m.merge_save(self.p,{'video_mode':'invalid'})
 def test_explicit_override_and_restore_inheritance(self):
  self.p['video_mode']='reference';self.p['video_model']='MiniMaxH3-RedCraft-Package-4step-R2V-1K'
  shot=self.p['shots'][0];shot['image']='/still.png';shot['video_override']={'mode':'first_frame','model':'MiniMaxH3-8step-I2V'};self.persist()
  j=self.launch();self.assertEqual(j['video_mode'],'first_frame');self.assertEqual(j['request']['model'],'MiniMaxH3-8step-I2V');self.assertIn('first_frame_image',j['request'])
  m.update(self.pid,lambda p:m.merge_save(p,{'video_model':'MiniMaxH3-R2V-20step-2K'}))
  self.assertEqual(self.launch()['request']['model'],'MiniMaxH3-8step-I2V')
  latest=m.load(self.pid);latest['shots'][0]['video_override']=None
  m.update(self.pid,lambda p:m.merge_save(p,latest));j=self.launch()
  self.assertEqual(j['video_mode'],'reference');self.assertEqual(j['request']['model'],'MiniMaxH3-R2V-20step-2K')
 def test_mixed_batch_resolves_each_shot(self):
  self.p['video_mode']='reference';self.p['video_model']='MiniMaxH3-RedCraft-Package-4step-R2V-1K'
  self.p['shots'].append({'id':'s2','duration':4,'video_prompt':'Duration: 4s\nWave.','image':'/still.png','video_override':{'mode':'first_frame','model':'MiniMaxH3-8step-I2V'}});self.persist()
  with patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',side_effect=lambda url:'bytes:'+url):result=m.launch_batch(self.pid,'video')
  self.assertEqual([j['video_mode'] for j in result['jobs']],['reference','first_frame']);self.assertEqual(result['skipped'],[])
 def test_invalid_override_rejected(self):
  for override in ['bad',{'mode':'last_frame'},{'mode':'reference','model':''}]:
   with self.subTest(override=override),self.assertRaises(ValueError):m.merge_save(self.p,{'shots':[dict(self.p['shots'][0],video_override=override)]})
 def test_invalid_mode_rejected_on_save(self):
  body=copy.deepcopy(self.p);body['shots'][0]['video_mode']='bad'
  with self.assertRaises(ValueError):m.merge_save(self.p,body)
if __name__=='__main__':unittest.main()
