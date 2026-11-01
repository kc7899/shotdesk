"""New segment policy; historical coverage tests stay frozen separately."""
import copy,json,unittest
from unittest.mock import patch
from tests.legacy import test_coverage_director as old
import coverage_director as d
import storyboard as b
from tests.backend import test_queue

# Legacy scheme tests: pin the pre-h3-structured-v2 default so they keep exercising the old pipeline.
import storyboard as _legacy_scheme_storyboard
_legacy_scheme_default=_legacy_scheme_storyboard.DEFAULT_SCHEME
def setUpModule():_legacy_scheme_storyboard.DEFAULT_SCHEME='huobao-native-v1'
def tearDownModule():_legacy_scheme_storyboard.DEFAULT_SCHEME=_legacy_scheme_default

m=test_queue.m

class SegmentDirector(unittest.TestCase):
 def setUp(self):
  test_queue.QueueContracts.setUp(self)
  def frozen(p):
   raw=(m.ROOT/'docs/skills/shotdesk-storyboard/references/segment-2026-10-31.1.md').read_text()
   with patch.object(m,'prompt_skill_bundle',return_value={'text':raw,'version':'2026-10-31.1'}):return b.skill_bundle(m.AppContext(),p)
  guard=patch.object(m,'storyboard_skill_bundle',side_effect=frozen);guard.start();self.addCleanup(guard.stop)
 tearDown=test_queue.QueueContracts.tearDown
 prepare=old.CoverageDirector.prepare
 project=old.CoverageDirector.project
 def task(self):return {'id':m.uid(),'model':'local','storyboard_stage':'all','storyboard_skill':{'director_format':'coverage-v1','segment_director':True},'storyboard_skill_text':'完整片段导演'}
 def response(self,body,job):
  payload=json.loads(body['messages'][1]['content'])
  if payload.get('phase')!='segment_direction':return old.CoverageDirector.response(self,body,job)
  rows={}
  for seg in payload['segments']:
   cuts={}
   for cut in seg['cuts']:
    cuts[cut['id']]={'visible':cut['visible'],'view':'相机在客厅南侧，平视中景。'+'；'.join('@'+k+' 位于椅子旁，面对交谈对象' for k in cut['visible']), 'before_text':' '.join(e['text'].replace('林岚','@A1').replace('周明','@A3') for e in cut['before']), 'after_text':' '.join(e['text'].replace('林岚','@A1').replace('周明','@A3') for e in cut['after'])}
   rows[seg['id']]={'title':'见面交谈','summary':'两人见面后交谈。','cuts':cuts}
  return {'choices':[{'message':{'content':json.dumps({'segments':rows},ensure_ascii=False)}}]}
 def test_complete_exchange_is_one_video_with_exact_multiple_speakers(self):
  p=self.project();before=copy.deepcopy(p)
  with patch.object(self.q,'text_request',side_effect=self.response):result=d.plan(m.AppContext(),p,self.task())
  self.assertEqual(p,before);shots=result['shots'];self.assertEqual(len(shots),1)
  shot=shots[0];self.assertEqual([x['text'] for x in shot['dialogue']],['您好。','你好。','请坐。'])
  self.assertIn('(S1)',shot['video_prompt']);self.assertIn('(S2)',shot['video_prompt']);self.assertIn('At ',shot['video_prompt']);self.assertIn('相机在客厅南侧',shot['video_prompt']);self.assertFalse(shot['director_plan']['review_required'])
  self.assertEqual(shot['director_plan']['pipeline_revision'],'segment-director-v1');self.assertNotIn('黑色外套',shot['video_prompt'])
 def test_exact_public_labels_are_accepted_without_guessing_resource_ids(self):
  p=self.project();task=self.task()
  def public(body,job):
   result=self.response(body,job)
   if json.loads(body['messages'][1]['content']).get('phase')=='segment_direction':
    raw=result['choices'][0]['message']['content'].replace('@A1','@林岚·日常').replace('@A3','@周明·外套');result['choices'][0]['message']['content']=raw
   return result
  with patch.object(self.q,'text_request',side_effect=public):out=d.plan(m.AppContext(),p,task)
  self.assertFalse(out['shots'][0]['director_plan']['review_required']);self.assertIn('@周明·外套',out['shots'][0]['video_prompt'])
 def test_director_cannot_overwrite_source_actions_with_a_different_actor(self):
  p=self.project();calls=[]
  def wrong(body,job):
   result=self.response(body,job)
   if json.loads(body['messages'][1]['content']).get('phase')=='segment_direction':
    obj=json.loads(result['choices'][0]['message']['content']);calls.append(obj)
    for seg in obj['segments'].values():
     for cut in seg['cuts'].values():cut['before_text']=cut['before_text'].replace('@A3','@A1');cut['after_text']=cut['after_text'].replace('@A3','@A1')
    result['choices'][0]['message']['content']=json.dumps(obj,ensure_ascii=False)
   return result
  with patch.object(self.q,'text_request',side_effect=wrong):out=d.plan(m.AppContext(),p,self.task())
  self.assertEqual(len(calls),1);self.assertFalse(out['shots'][0]['director_plan']['review_required']);self.assertIn('@周明·外套坐下',out['shots'][0]['video_prompt'])
 def test_first_frame_mode_keeps_official_alignment_without_extra_generation(self):
  p=self.project();p['video_mode']='first_frame';p['video_model']='MiniMaxH3-8step-I2V'
  with patch.object(self.q,'text_request',side_effect=self.response):shot=d.plan(m.AppContext(),p,self.task())['shots'][0]
  self.assertEqual(shot['prompt_video_mode'],'first_frame');self.assertIn(b.FIRST_FRAME,shot['video_prompt']);self.assertEqual(shot['versions'],[])
 def test_director_visible_listener_gets_reference_in_same_plan(self):
  p=self.project();p['script']='场景 1\n客厅\n林岚坐在左侧。\n周明站在右侧。\n林岚：您好。'
  def listener(body,job):
   result=self.response(body,job)
   if json.loads(body['messages'][1]['content']).get('phase')=='segment_direction':
    obj=json.loads(result['choices'][0]['message']['content'])
    for segment in obj['segments'].values():
     for cut in segment['cuts'].values():
      cut['view']+='；周明在右侧倾听。';cut['visible']=list(dict.fromkeys(cut['visible']+['A3']))
    result['choices'][0]['message']['content']=json.dumps(obj,ensure_ascii=False)
   return result
  with patch.object(self.q,'text_request',side_effect=listener):shot=d.plan(m.AppContext(),p,self.task())['shots'][0]
  self.assertIn('man',shot['asset_ids']);self.assertEqual(shot['character_looks']['man'],'coat');self.assertIn('A3',shot['director_plan']['cuts'][-1]['visible'])
 def test_director_receives_scene_context_without_old_camera_templates(self):
  p=self.project();calls=[]
  def capture(body,job):
   payload=json.loads(body['messages'][1]['content'])
   if payload.get('phase')=='segment_direction':calls.append(payload)
   return self.response(body,job)
  with patch.object(self.q,'text_request',side_effect=capture):d.plan(m.AppContext(),p,self.task())
  self.assertTrue(calls[0]['scene_context']);self.assertTrue(all('camera' not in state for state in calls[0]['cast'].values()))
 def test_plain_name_followed_by_alias_does_not_form_a_broken_mention(self):
  p=self.project()
  def annotated(body,job):
   result=self.response(body,job)
   if json.loads(body['messages'][1]['content']).get('phase')=='segment_direction':
    obj=json.loads(result['choices'][0]['message']['content'])
    for segment in obj['segments'].values():
     for cut in segment['cuts'].values():cut['view']=cut['view'].replace('@A3','周明A3')
    result['choices'][0]['message']['content']=json.dumps(obj,ensure_ascii=False)
   return result
  with patch.object(self.q,'text_request',side_effect=annotated):shot=d.plan(m.AppContext(),p,self.task())['shots'][0]
  self.assertNotIn('A3A3',shot['video_prompt']);self.assertIn('@周明·外套',shot['video_prompt']);self.assertFalse(shot['director_plan']['review_required'])
 def test_camera_target_cannot_replace_the_current_speaker(self):
  p=self.project()
  def wrong(body,job):
   result=self.response(body,job)
   if json.loads(body['messages'][1]['content']).get('phase')=='segment_direction':
    obj=json.loads(result['choices'][0]['message']['content'])
    for segment in obj['segments'].values():
     for cut in segment['cuts'].values():cut['view']+='。相机正对@A3，拍摄他的特写。'
    result['choices'][0]['message']['content']=json.dumps(obj,ensure_ascii=False)
   return result
  with patch.object(self.q,'text_request',side_effect=wrong):shot=d.plan(m.AppContext(),p,self.task())['shots'][0]
  self.assertTrue(shot['director_plan']['review_required']);self.assertNotIn('拍摄他的特写',shot['video_prompt'])
 def test_looking_at_an_offscreen_partner_does_not_require_his_image_in_the_cut(self):
  p=self.project()
  def gaze(body,job):
   result=self.response(body,job)
   if json.loads(body['messages'][1]['content']).get('phase')=='segment_direction':
    obj=json.loads(result['choices'][0]['message']['content'])
    for segment in obj['segments'].values():
     for cut in segment['cuts'].values():
      if cut['visible']==['A1']:cut['view']+='，看向@A3。'
    result['choices'][0]['message']['content']=json.dumps(obj,ensure_ascii=False)
   return result
  with patch.object(self.q,'text_request',side_effect=gaze):shot=d.plan(m.AppContext(),p,self.task())['shots'][0]
  self.assertFalse(shot['director_plan']['review_required'])
 def test_compile_failure_recovers_source_draft_without_losing_the_exchange(self):
  p=self.project();original=d.compile_shot;calls=[]
  def fail_once(*args):
   calls.append(1)
   if len(calls)==1:raise ValueError('malformed director mention')
   return original(*args)
  with patch.object(self.q,'text_request',side_effect=self.response),patch.object(d,'compile_shot',side_effect=fail_once):shot=d.plan(m.AppContext(),p,self.task())['shots'][0]
  self.assertEqual(len(calls),2);self.assertTrue(shot['director_plan']['review_required']);self.assertEqual([l['text'] for l in shot['dialogue']],['您好。','你好。','请坐。']);self.assertIn('<d>[Chinese] 您好。</d>',shot['video_prompt'])
 def test_reordering_assets_cannot_rebind_an_existing_director_to_another_person(self):
  p=self.project()
  with patch.object(self.q,'text_request',side_effect=self.response):shot=d.plan(m.AppContext(),p,self.task())['shots'][0]
  before=shot['video_prompt'];p['assets']=list(reversed(p['assets']));d.compile_shot(m.AppContext(),p,shot)
  self.assertEqual(shot['video_prompt'],before);self.assertEqual(shot['character_looks']['man'],'coat')
 def test_public_queue_freezes_and_executes_new_default(self):
  p=self.project();m.save(self.root/'project.json',p);p=m.load(self.pid)
  with patch.object(self.q,'enqueue',side_effect=lambda pid,j:j):job=self.q.start_storyboard(self.pid)
  self.assertTrue(job['storyboard_skill']['segment_director'])
  with patch.object(self.q,'text_request',side_effect=self.response):self.q.worker(self.pid,job)
  stored=json.loads(m.job_path(self.pid,job['id']).read_text());self.assertEqual(stored['status'],'completed',stored.get('error'));saved=m.load(self.pid);self.assertEqual(saved['assets'],p['assets']);self.assertEqual(len(saved['shots']),1)
 def test_broken_director_is_bounded_and_not_mislabelled_as_passed(self):
  p=self.project();task=self.task();calls=[]
  def response(body,job):
   payload=json.loads(body['messages'][1]['content'])
   if payload.get('phase')=='segment_direction':calls.append(payload);return {'choices':[{'message':{'content':'{}'}}]}
   return self.response(body,job)
  with patch.object(self.q,'text_request',side_effect=response):result=d.plan(m.AppContext(),p,task)
  self.assertEqual(len(calls),2);self.assertTrue(result['shots'][0]['director_plan']['review_required']);self.assertTrue(task['storyboard_quality_notes']);self.assertTrue(result['shots'][0]['review_warnings'])
 def test_new_compiler_does_not_force_four_seconds_or_rewrite_media(self):
  p=self.project()
  with patch.object(self.q,'text_request',side_effect=self.response):shot=d.plan(m.AppContext(),p,self.task())['shots'][0]
  shot['dialogue']=[];shot['director_plan']['cuts']=[dict(shot['director_plan']['cuts'][0],line=None,seconds=1.5,speaker_keys=[])];shot['duration']=1.75;shot['versions']=[{'id':'old','url':'/old.mp4'}]
  d.compile_shot(m.AppContext(),p,shot);self.assertLess(shot['duration'],4);self.assertEqual(shot['versions'][0]['id'],'old')

if __name__=='__main__':unittest.main()
