import tempfile,unittest,copy,json,base64
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import server as m
class CharacterAudio(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);fix=patch.object(m,'DATA',Path(self.tmp.name));fix.start();self.addCleanup(fix.stop)
  self.pid='a'*32;root=m.project(self.pid).parent;(root/'media').mkdir(parents=True);(root/'jobs').mkdir()
  self.voice=f'/media/{self.pid}/media/voice.wav';(root/'media/voice.wav').write_bytes(b'RIFFvoice')
  self.p={'id':self.pid,'name':'test','ratio':'16:9','image_model':'Flux2-Klein-4B-4step-1K','video_mode':'audio','video_model':'MiniMaxH3-RedCraft-Package-4step-AudioLip-1K','assets':[{'id':'voice','type':'音频','name':'voice','audio':self.voice,'versions':[{'id':'voice-v','kind':'audio','url':self.voice,'created':1}]},{'id':'person','type':'角色','name':'actor','image':'/face.png','voice_asset_id':'voice','default_look_id':'work','looks':[{'id':'work','name':'work','image':'/work.png','prompt':'The same person wearing a suit.','versions':[]}]}],'shots':[{'id':'s','duration':4,'image':'/still.png','asset_ids':['person'],'speaker_id':'person','dialogue':'你好，今天见到你很高兴。','speech_emotion':'自然','video_prompt':'Duration: 4s\nWave.','image_prompt':'Two people','versions':[]}]};self.persist()
 def persist(self):m.save(m.project(self.pid),self.p)
 def test_scene_ratio_is_fixed_landscape_independent_of_project(self):
  self.p['ratio']='9:16';self.p['assets'].append({'id':'scene','name':'living room','type':'场景','prompt':'A living room','image_ratio':'1:1','versions':[]});self.persist()
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j):job=m.launch(self.pid,'asset','scene','image')
  self.assertEqual(job['request']['aspect_ratio'],'16:9');self.assertEqual(job['request']['prompt'],'A living room')
 def test_character_and_look_have_independent_image_ratios(self):
  self.p['ratio']='9:16';self.p['assets'][1]['prompt']='portrait';self.persist()
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',return_value='bytes'):
   identity=m.launch(self.pid,'asset','person','image');look=m.launch(self.pid,'look','work','image');shot=m.launch(self.pid,'shot','s','image')
  self.assertEqual(identity['request']['aspect_ratio'],'1:1');self.assertEqual(look['request']['aspect_ratio'],'3:4');self.assertEqual(shot['request']['aspect_ratio'],'9:16')
 def test_explicit_character_ratio_overrides_default(self):
  self.p['assets'][1]['prompt']='portrait';self.p['assets'][1]['image_ratio']='16:9';self.persist()
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j):j=m.launch(self.pid,'asset','person','image')
  self.assertEqual(j['request']['aspect_ratio'],'16:9')
 def test_visible_requirements_compose_exactly_and_clear(self):
  a=self.p['assets'][1];a['prompt']='人物描述';a['generation_requirements']='单视图要求'
  self.assertEqual(m.asset_image_prompt(a),'人物描述\n\n单视图要求')
  a['generation_requirements']='';self.assertEqual(m.asset_image_prompt(a),'人物描述')
  del a['generation_requirements'];self.assertEqual(m.asset_image_prompt(a),'人物描述')
 def test_requirements_never_replace_character_description(self):
  with self.assertRaises(ValueError):m.asset_image_prompt({'prompt':'','generation_requirements':m.ASSET_PROMPT_PRESETS['identity']})
 def test_look_request_contains_edited_requirements(self):
  self.p['assets'][1]['looks'][0]['generation_requirements']='白色背景，单人正面';self.persist()
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',return_value='bytes'):
   j=m.launch(self.pid,'look','work','image')
  self.assertEqual(j['request']['prompt'],'The same person wearing a suit.\n\n白色背景，单人正面')
 def test_requirements_survive_save_and_do_not_modify_shot_prompts(self):
  body=copy.deepcopy(self.p);body['assets'][1]['generation_requirements']='';body['assets'][1]['looks'][0]['generation_requirements']='侧面图'
  with patch.object(m.Q,'list',return_value=[]):m.merge_save(self.p,body)
  self.assertEqual(self.p['assets'][1]['generation_requirements'],'');self.assertEqual(self.p['assets'][1]['looks'][0]['generation_requirements'],'侧面图')
  self.assertEqual(self.p['shots'][0]['image_prompt'],'Two people')
 def test_default_slots_are_stable_and_preserve_legacy_voice(self):
  a=self.p['assets'][1];a.pop('looks');a.pop('default_look_id');m.normalize_characters(self.p)
  before=copy.deepcopy(a);m.normalize_characters(self.p);self.assertEqual(a,before)
  self.assertEqual(a['voices'][0]['asset_id'],'voice')
 def test_empty_default_look_uses_identity_but_explicit_does_not(self):
  a=self.p['assets'][1];a['looks'][0].pop('image');s=self.p['shots'][0]
  ref=m.image_resources(self.p,s)[0];self.assertEqual(ref['url'],'/face.png');self.assertIsNone(ref['look_id'])
  s['character_looks']={'person':'work'}
  with self.assertRaises(ValueError):m.image_resources(self.p,s)
 def test_voice_variants_and_explicit_empty_rejected(self):
  m.normalize_characters(self.p);a=self.p['assets'][1];a['voices'].append({'id':'hoarse','name':'沙哑','asset_id':None})
  self.assertEqual(m.character_voice(self.p,a)['asset_id'],'voice')
  with self.assertRaises(ValueError):m.character_voice(self.p,a,'hoarse')
  with self.assertRaises(ValueError):m.character_voice(self.p,a,'missing')
 def test_shot_voice_must_belong_to_speaker(self):
  self.p['shots'][0]['voice_id']='missing'
  with self.assertRaises(ValueError):m.validate_resources(self.p)
 def test_look_resolution(self):
  self.assertEqual(m.image_resources(self.p,self.p['shots'][0])[0]['url'],'/work.png')
  self.p['shots'][0]['character_looks']={'person':'bad'}
  with self.assertRaises(ValueError):m.image_resources(self.p,self.p['shots'][0])
 def test_look_generation_uses_identity_and_writes_nested_version(self):
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',side_effect=lambda url:'bytes:'+url):j=m.launch(self.pid,'look','work','image')
  self.assertEqual(j['request']['prompt'],'The same person wearing a suit.');self.assertEqual(j['request']['image'],['bytes:/face.png'])
  with patch.object(m,'job_save'):m.finish_job(self.pid,j,'/new-look.png')
  look=m.load(self.pid)['assets'][1]['looks'][0];self.assertEqual(look['image'],'/new-look.png');self.assertEqual(look['versions'][0]['id'],j['id'])
 def test_audio_not_allowed_in_image_refs(self):
  self.p['shots'][0]['asset_ids']=['voice']
  with self.assertRaises(ValueError):m.validate_resources(self.p)
 def test_referenced_asset_deletion_rejected(self):
  p=copy.deepcopy(self.p);p['assets']=[a for a in p['assets'] if a['id']!='voice']
  with self.assertRaises(ValueError):m.validate_resources(p)
 def test_audio_asset_source_and_missing_no_fallback(self):
  self.assertEqual(m.resolve_audio(self.p,{'type':'asset','asset_id':'voice'})['version_id'],'voice-v')
  with self.assertRaises(ValueError):m.resolve_audio(self.p,{'type':'asset','asset_id':'missing'},self.voice)
 def test_speech_requires_person_and_snapshots_voice_text(self):
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j):j=m.launch(self.pid,'shot','s','audio')
  self.assertEqual(j['voice_input']['asset_id'],'voice');self.assertEqual(j['request']['text'],self.p['shots'][0]['dialogue']);self.assertEqual(j['speaker_id'],'person')
  self.assertTrue(j['request']['label'].endswith(j['id']))
  self.p['assets'][1].pop('voice_asset_id');self.persist()
  with self.assertRaises(ValueError):m.launch(self.pid,'shot','s','audio')
 def test_native_video_never_consumes_audio(self):
  self.p['video_mode']='first_frame';self.p['video_model']='MiniMaxH3-8step-I2V';self.p['shots'][0]['audio_source']={'type':'asset','asset_id':'voice'};self.persist()
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',return_value='image-bytes'):j=m.launch(self.pid,'shot','s','video')
  self.assertNotIn('reference_audios',j['request'].get('metadata',{}));self.assertIsNone(j['source_audio'])
 def test_audio_driver_duration_mismatch(self):
  self.p['shots'][0]['audio_source']={'type':'asset','asset_id':'voice'};self.persist()
  with patch.object(m.Q,'reject_duplicate'),patch.object(m,'reference',return_value='bytes'),patch.object(m,'audio_info',return_value={'duration':8}):
   with self.assertRaisesRegex(ValueError,'时长'):m.launch(self.pid,'shot','s','video')
 def test_audio_versions_unread_and_finish(self):
  j={'id':'b'*32,'target':'shot','target_id':'s','kind':'audio','request':{'prompt':'hello','model':'index-tts-2'},'audio_duration':4}
  with patch.object(m,'job_save'):m.finish_job(self.pid,j,self.voice)
  p=m.load(self.pid);self.assertEqual(p['shots'][0]['audio_source']['version_id'],j['id'])
  self.assertEqual(p['shots'][0]['latest_version_ids']['audio'],j['id'])
  claimed=m.read_media(self.pid,{'kind':'audio'},True);self.assertEqual(len(claimed['items']),2)
 def test_nested_generated_look_survives_stale_save(self):
  old=copy.deepcopy(self.p);old['assets'][1]['looks'][0]['image']=None
  self.p['assets'][1]['looks'][0]['versions']=[{'id':'new','kind':'image','url':'/work.png'}]
  m.merge_save(self.p,old)
  look=self.p['assets'][1]['looks'][0];self.assertEqual(look['image'],'/work.png');self.assertEqual(look['versions'][0]['id'],'new')
 def test_finished_remote_speech_is_imported_without_resubmission(self):
  import io
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j):j=m.launch_speech(self.pid,'shot','s')
  j['speech_remote_id']='existing';j['request'].pop('model',None)
  remote=[{'id':'existing','status':'complete','results':[{'file':'output.wav'}]}]
  with patch.object(m,'request',return_value=remote) as request,patch.object(m.OP,'open',return_value=io.BytesIO(b'RIFFoutput')),patch.object(m,'audio_info',return_value={'duration':3.1}):
   m.run_speech(self.pid,j)
  self.assertTrue(all('/api/generate' not in call.args[0] for call in request.call_args_list))
  self.assertEqual(j['status'],'completed');shot=m.load(self.pid)['shots'][0]
  self.assertEqual(shot['versions'][0]['model'],'index-tts-2');self.assertEqual(shot['audio_source']['version_id'],j['id'])
 def test_resume_failed_speech_reuses_original_id(self):
  jid='e'*32;j={'id':jid,'kind':'audio','target_id':'s','status':'failed','speech_remote_id':'existing','error':'download'};m.job_save(self.pid,j)
  with patch.object(m,'request',return_value=[{'id':'existing','status':'complete'}]),patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j):result=m.resume_speech(self.pid,jid)
  self.assertEqual(result['id'],jid);self.assertEqual(result['speech_remote_id'],'existing');self.assertEqual(result['status'],'queued')
 def test_cancelled_speech_holds_media_lock_until_release(self):
  from task_queue import Cancelled
  q=m.TaskQueue(m.AppContext());j={'id':'f'*32,'kind':'audio','target_id':'s','status':'running','speech_remote_id':'remote'}
  m.job_save(self.pid,j)
  def check_lease(job):self.assertTrue(q.media_lock.locked())
  with patch.object(m,'run_speech',side_effect=Cancelled()),patch.object(m,'wait_speech_release',side_effect=check_lease) as release,patch.object(m,'speech_terminal',return_value=True):q.worker(self.pid,j)
  release.assert_called_once();self.assertEqual(j['status'],'cancelled');self.assertFalse(q.media_lock.locked())
 def test_speech_cancellation_waits_for_upstream(self):
  q=m.TaskQueue(m.AppContext());j={'id':'c'*32,'kind':'audio','target_id':'s','status':'running','speech_remote_id':'remote'};m.job_save(self.pid,j)
  with patch.object(m,'speech_terminal',return_value=False),patch.object(q,'monitor_cancel') as monitor:
   result=q.cancel(self.pid,j['id']);self.assertEqual(result['status'],'cancelling');monitor.assert_called_once()
 def test_speech_resume_reuses_remote_id(self):
  q=m.TaskQueue(m.AppContext());j={'id':'d'*32,'kind':'audio','target_id':'s','status':'running','speech_remote_id':'remote'};m.job_save(self.pid,j)
  with patch.object(q,'enqueue') as enq:q.resume();self.assertEqual(enq.call_args.args[1]['speech_remote_id'],'remote')
if __name__=='__main__':unittest.main()
