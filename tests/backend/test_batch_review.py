import copy,importlib.util,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('shotdesk',Path(__file__).resolve().parents[2]/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BatchReview(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.patch=patch.object(m,'DATA',Path(self.temp.name));self.patch.start();self.pid='a'*32;self.root=Path(self.temp.name)/self.pid;(self.root/'jobs').mkdir(parents=True);(self.root/'media').mkdir()
  self.p={'id':self.pid,'name':'batch','content':'','script':'','assets':[],'shots':[{'id':'s1','title':'one','image_prompt':'first','duration':4,'video_prompt':'Duration: 4s\nAct.','image':'/media/existing.png','versions':[{'id':'v1','kind':'image','url':'/media/existing.png','prompt':'first'}]},{'id':'s2','title':'two','image_prompt':'second','duration':4,'video_prompt':'Duration: 4s\nAct.','versions':[]}],'image_model':'Flux2-Klein-4B-4step-1K','video_model':'MiniMaxH3-8step-I2V','ratio':'16:9'}
  m.save(self.root/'project.json',self.p);self.q=m.TaskQueue(m.AppContext());self.qpatch=patch.object(m,'Q',self.q);self.qpatch.start()
 def tearDown(self):self.qpatch.stop();self.patch.stop();self.temp.cleanup()
 def test_required_firstframes_skip_reference_but_include_audio(self):
  self.p['video_mode']='reference';self.p['video_model']=next(iter(m.REFERENCE_VIDEO_MODELS))
  self.p['shots'][1]['video_override']={'mode':'audio','model':m.VIDEO_STRATEGIES['audio']['models'][0]};m.save(self.root/'project.json',self.p)
  with patch.object(m.threading,'Thread'):r=m.launch_batch(self.pid,'image',required_only=True)
  self.assertEqual([j['target_id'] for j in r['jobs']],['s2']);self.assertIn('不需要首帧',r['skipped'][0]['reason'])
 def test_required_firstframes_keep_repeated_rounds(self):
  with patch.object(m.threading,'Thread'):rounds=[m.launch_batch(self.pid,'image',required_only=True) for _ in range(2)]
  self.assertEqual([len(r['jobs']) for r in rounds],[2,2])
 def test_all_in_order_and_preserve_versions(self):
  original_versions=m.load(self.pid)['shots'][0]['versions']
  with patch.object(m.threading,'Thread'):
   result=m.launch_batch(self.pid,'image')
  self.assertEqual([j['target_id'] for j in result['jobs']],['s1','s2']);self.assertEqual(len({j['batch_id'] for j in result['jobs']}),1);self.assertEqual(m.load(self.pid)['shots'][0]['versions'],original_versions)
  self.assertEqual([j[1]['target_id'] for j in self.q.media_pending],['s1','s2'])
 def test_missing_only(self):
  with patch.object(m.threading,'Thread'):r=m.launch_batch(self.pid,'image','missing')
  self.assertEqual([j['target_id'] for j in r['jobs']],['s2']);self.assertIn('已有',r['skipped'][0]['reason'])
 def test_three_clicks_add_three_rounds_with_new_seeds(self):
  with patch.object(m.threading,'Thread'):
   rounds=[m.launch_batch(self.pid,'image') for _ in range(3)]
  self.assertEqual([len(r['jobs']) for r in rounds],[2,2,2]);self.assertEqual(len({r['batch_id'] for r in rounds}),3)
  queued=list((self.root/'jobs').glob('*.json'));self.assertEqual(len(queued),6)
  requests=[json.loads(f.read_text()) for f in queued]
  for sid in ('s1','s2'):
   self.assertEqual(len({j['request']['seed'] for j in requests if j['target_id']==sid}),3)
 def test_video_can_append_while_previous_round_is_active(self):
  with patch.object(m.threading,'Thread'),patch.object(m,'reference',return_value='data:image/png;base64,dGVzdA=='):
   a=m.launch_batch(self.pid,'video');b=m.launch_batch(self.pid,'video')
  self.assertEqual(len(a['jobs']),1);self.assertEqual(len(b['jobs']),1);self.assertNotEqual(a['jobs'][0]['id'],b['jobs'][0]['id'])
 def test_video_skips_missing_first_frame(self):
  with patch.object(m.threading,'Thread'),patch.object(m,'reference',return_value='data:image/png;base64,dGVzdA=='):r=m.launch_batch(self.pid,'video')
  self.assertEqual([j['target_id'] for j in r['jobs']],['s1']);self.assertIn('缺少首帧',r['skipped'][0]['reason'])
 def test_bad_prompt_does_not_block_other_shots(self):
  self.p['shots'][0]['image_prompt']='';m.save(self.root/'project.json',self.p)
  with patch.object(m.threading,'Thread'):r=m.launch_batch(self.pid,'image')
  self.assertEqual([j['target_id'] for j in r['jobs']],['s2'])
 def payload(self):
  item=m.REVIEWS.inputs(self.pid)['items'][0]
  return {'shot_id':item['shot_id'],'kind':item['kind'],'version_id':item['version_id'],'context_id':item['context_id'],'decision':'pass','checker':{'type':'model','model':'test-local-vision'},'checks':[{'name':'identity','status':'pass','reason':'matches reference'}]}
 def test_review_bound_to_version_and_invalidated_by_prompt_change(self):
  m.REVIEWS.record(self.pid,self.payload());self.assertEqual(m.REVIEWS.inputs(self.pid)['items'][0]['review_status'],'pass')
  m.update(self.pid,lambda p:p['shots'][0].update(image_prompt='changed'));self.assertEqual(m.REVIEWS.inputs(self.pid)['items'][0]['review_status'],'pending')
 def test_stale_review_rejected(self):
  body=self.payload();m.update(self.pid,lambda p:p['shots'][0].update(description='new action'))
  with self.assertRaises(ValueError):m.REVIEWS.record(self.pid,body)
 def test_unknown_cannot_be_approved(self):
  body=self.payload();body['checks'][0]['status']='unknown'
  with self.assertRaises(ValueError):m.REVIEWS.record(self.pid,body)
 def test_review_never_automatically_regenerates(self):
  body=self.payload();body['decision']='retry';body['checks'][0]['status']='fail';m.REVIEWS.record(self.pid,body)
  self.assertEqual(list((self.root/'jobs').glob('*.json')),[]);self.assertFalse(m.REVIEWS.inputs(self.pid)['automatic_retry_enabled'])
 def test_fifo_dispatch_runs_oldest_first(self):
  self.q.media_pending=[(self.pid,{'id':'later','created':20}),(self.pid,{'id':'first','created':10})]
  order=[]
  with patch.object(self.q,'worker',side_effect=lambda pid,j:order.append(j['id'])):self.q.drain_media()
  self.assertEqual(order,['first','later'])
 def test_reference_asset_change_invalidates_review(self):
  self.p['assets']=[{'id':'actor','name':'Actor','image':'/media/actor-v1.png'}];self.p['shots'][0]['asset_ids']=['actor'];m.save(self.root/'project.json',self.p)
  m.REVIEWS.record(self.pid,self.payload());m.update(self.pid,lambda p:p['assets'][0].update(image='/media/actor-v2.png'))
  self.assertEqual(m.REVIEWS.inputs(self.pid)['items'][0]['review_status'],'pending')
 def test_new_output_version_invalidates_review(self):
  m.REVIEWS.record(self.pid,self.payload())
  def change(p):
   shot=p['shots'][0];shot['image']='/media/new.png';shot['versions'].append({'id':'v2','kind':'image','url':shot['image']})
  m.update(self.pid,change);self.assertEqual(m.REVIEWS.inputs(self.pid)['items'][0]['review_status'],'pending')
if __name__=='__main__':unittest.main()
