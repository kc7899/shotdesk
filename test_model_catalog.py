import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import server as m
class AllModels(unittest.TestCase):
 def setUp(self):
  from test_support import legacy_engine
  guard=patch.object(m.Q,'engine',return_value=legacy_engine(m));guard.start();self.addCleanup(guard.stop)
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  fix=patch.object(m,'DATA',Path(self.tmp.name));fix.start();self.addCleanup(fix.stop)
  self.pid='a'*32;(Path(self.tmp.name)/self.pid/'media').mkdir(parents=True)
  self.p={'ratio':'16:9','image_model':'Flux2-Klein-4B-4step-1K','video_mode':'text','video_model':'MiniMaxH3-8step-T2V-2K','assets':[{'id':'a','image':'/asset.png'}],'shots':[{'id':'s','duration':4,'video_prompt':'Duration: 4s\nWave.','image_prompt':'portrait','asset_ids':['a'],'image':'/still.png','video':'/current.mp4','reference_audio':'/guide.wav','reference_video':'/guide.mp4','versions':[]}]}
 def launch(self,mode,model):
  self.p['video_mode']=mode;self.p['video_model']=model;m.save(m.project(self.pid),self.p)
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',side_effect=lambda url:'bytes:'+url):return m.launch(self.pid,'shot','s','video')
 def test_all_registered_models_are_mapped(self):
  catalog=m.model_catalog();self.assertEqual(catalog['unmapped_videos'],[])
  self.assertTrue(all(v['modes'] for v in catalog['videos']))
  self.assertTrue(any(v['operation']=='enhance' for v in catalog['images']))
 def test_text_does_not_send_images(self):
  j=self.launch('text','MiniMaxH3-8step-T2V-2K');self.assertNotIn('image',j['request']);self.assertNotIn('first_frame_image',j['request']);self.assertEqual(j['request']['metadata']['gen_mode'],'textToVideo')
 def test_audio_and_music_inputs(self):
  for mode,model in [('audio','MiniMaxH3-RedCraft-Package-4step-AudioLip-1K'),('music','MiniMaxH3-RedCraft-Package-4step-MusicVideo-1K')]:
   j=self.launch(mode,model);self.assertEqual(j['request']['metadata']['reference_audios'],['bytes:/guide.wav']);self.assertEqual(j['request']['first_frame_image'],'bytes:/still.png');self.assertEqual(j['source_audio'],'/guide.wav')
 def test_reference_video_inputs(self):
  j=self.launch('video_reference','MiniMaxH3-RedCraft-Package-4step-ImageVideo-1K');self.assertEqual(j['request']['image'],['bytes:/asset.png']);self.assertEqual(j['request']['metadata']['reference_videos'],['bytes:/guide.mp4'])
 def test_enhancement_does_not_pass_image(self):
  for mode,model in [('upscale','RedCraft-Package-FlashVSR-Video-2x'),('interpolate','RedCraft-Package-RIFE-Video-2xFPS')]:
   self.p['shots'][0].pop('reference_video',None);j=self.launch(mode,model);self.assertNotIn('image',j['request']);self.assertNotIn('first_frame_image',j['request']);self.assertEqual(j['source_video'],'/current.mp4')
 def test_missing_audio_rejected_before_enqueue(self):
  self.p['shots'][0].pop('reference_audio')
  with self.assertRaisesRegex(ValueError,'音频'):self.launch('audio','MiniMaxH3-AudioGuide-20step-2K')
 def test_image_enhancement_uses_current_image(self):
  self.p['image_model']='RedCraft-Package-ClearReality-Image-4x';m.save(m.project(self.pid),self.p)
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',side_effect=lambda url:'bytes:'+url):j=m.launch(self.pid,'shot','s','image')
  self.assertEqual(j['request']['image'],['bytes:/still.png'])
 def test_upload_rejects_wrong_stream_and_cleans_file(self):
  import base64
  m.save(m.project(self.pid),self.p)
  body={'kind':'video','data':'data:audio/wav;base64,'+base64.b64encode(b'RIFF1234WAVEtest').decode()}
  with patch.object(m.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps({'streams':[{'codec_type':'audio'}]}))):
   with self.assertRaises(ValueError):m.upload_guide(self.pid,body)
  self.assertEqual(list((m.project(self.pid).parent/'media').iterdir()),[])
if __name__=='__main__':unittest.main()
