import copy,json,unittest
from unittest.mock import patch
import test_queue
import test_storyboard_official as fixtures
import storyboard as b

# Legacy scheme tests: pin the pre-h3-structured-v2 default so they keep exercising the old pipeline.
import storyboard as _legacy_scheme_storyboard
_legacy_scheme_default=_legacy_scheme_storyboard.DEFAULT_SCHEME
def setUpModule():_legacy_scheme_storyboard.DEFAULT_SCHEME='huobao-native-v1'
def tearDownModule():_legacy_scheme_storyboard.DEFAULT_SCHEME=_legacy_scheme_default

m=test_queue.m

class StoryboardStages(unittest.TestCase):
 setUp=fixtures.legacy_setup
 tearDown=test_queue.QueueContracts.tearDown
 prepare=fixtures.OfficialStoryboard.prepare
 row=fixtures.OfficialStoryboard.row
 response=fixtures.OfficialStoryboard.response
 def start(self,stage,**kw):
  with patch.object(m,'storyboard_skill_bundle',side_effect=lambda p:dict(fixtures.legacy_bundle(p),h3_dialogue_slots=False,resilient_storyboard=False)),patch('task_queue.threading.Thread'):return self.q.start_storyboard(self.pid,stage=stage,**kw)
 def stored(self,j):return json.loads(m.job_path(self.pid,j['id']).read_text())
 def fixture_shot(self):
  return dict(self.row(),id='stable',duration=6,versions=[{'id':'old','kind':'video','url':'/existing.mp4'}],video='/existing.mp4',video_completed=True,video_prompt='',video_override=None)
 def prompt_response(self):
  return self.response({'prompts':[{'index':0,'summary':'问候','events':[{'visual':'@林岚·日常 走入 @客厅，抬眼问候。','dialogue_indices':[0],'cut_at':None}],'overall_soundscape':'室内环境声。','non_diegetic_music':'N/A'}]})
 def test_planning_stops_before_prompt_model_and_saves_reviewable_shots(self):
  before=self.prepare();j=self.start('planning');stored=self.stored(j)
  with patch.object(b,'plan_in_parts',return_value={'shots':[self.row()]}),patch.object(self.q,'text_request') as request:self.q.worker(self.pid,stored)
  request.assert_not_called();p=m.load(self.pid);self.assertEqual(len(p['shots']),1);self.assertTrue(b.prompt_is_missing(m.AppContext(),p['shots'][0]));self.assertEqual(p['assets'],before['assets']);self.assertEqual(self.stored(j)['status'],'completed')
 def test_prompt_only_preserves_approved_plan_ids_and_media(self):
  self.prepare();shot=self.fixture_shot();m.update(self.pid,lambda p:p.update(shots=[shot]));before=m.load(self.pid);j=self.start('prompts')
  with patch.object(b,'plan_in_parts',side_effect=AssertionError('must not replan')),patch.object(self.q,'text_request',return_value=self.prompt_response()):self.q.worker(self.pid,self.stored(j))
  after=m.load(self.pid);self.assertEqual(self.stored(j)['status'],'completed');actual=after['shots'][0]
  for key in ('id','title','description','dialogue','duration','asset_ids','character_looks','versions','video','video_completed'):self.assertEqual(actual[key],before['shots'][0][key],key)
  self.assertIn('<d>[Chinese] 您好。</d>',actual['video_prompt'])
 def test_missing_scope_skips_existing_and_single_scope_targets_one(self):
  self.prepare();a=self.fixture_shot();a['video_prompt']='已有提示词';c=dict(self.fixture_shot(),id='second');m.update(self.pid,lambda p:p.update(shots=[a,c]));j=self.start('prompts')
  self.assertEqual(self.stored(j)['storyboard_shot_ids'],['second'])
  m.job_save(self.pid,dict(self.stored(j),status='cancelled'))
  j=self.start('prompts',scope='all',shot_id='stable');self.assertEqual(self.stored(j)['storyboard_shot_ids'],['stable'])
 def test_prompt_failure_preserves_project_and_checkpoint_reuses_completed_shot(self):
  self.prepare();a=self.fixture_shot();c=dict(self.fixture_shot(),id='second');m.update(self.pid,lambda p:p.update(shots=[a,c]));before=m.load(self.pid);j=self.start('prompts')
  with patch.object(self.q,'text_request',side_effect=[self.prompt_response(),RuntimeError('model unavailable')]):self.q.worker(self.pid,self.stored(j))
  self.assertEqual(m.load(self.pid)['shots'],before['shots']);self.assertEqual(self.stored(j)['status'],'failed');self.assertEqual(len(self.stored(j)['storyboard_prompt_parts']),1)
  retry=self.start('prompts')
  with patch.object(self.q,'text_request',return_value=self.prompt_response()) as request:self.q.worker(self.pid,self.stored(retry))
  self.assertEqual(request.call_count,1);self.assertEqual(self.stored(retry)['status'],'completed');self.assertEqual(self.stored(retry)['storyboard_resumed_prompts'],1)
 def test_check_is_read_only_and_makes_no_model_request(self):
  p=self.prepare();p['shots']=[self.fixture_shot()];before=copy.deepcopy(p)
  with patch.object(self.q,'text_request') as request:report=b.check_existing(m.AppContext(),p)
  request.assert_not_called();self.assertEqual(p,before);self.assertTrue(report['ok']);self.assertEqual(report['missing_prompts'],1)
  p['shots'][0]['asset_ids']=['unknown'];self.assertFalse(b.check_existing(m.AppContext(),p)['ok'])
 def test_prompt_job_respects_concurrent_plan_edit(self):
  self.prepare();shot=self.fixture_shot();m.update(self.pid,lambda p:p.update(shots=[shot]));j=self.start('prompts');result={'shots':[dict(shot,video_prompt='new')]}
  m.update(self.pid,lambda p:p['shots'][0].update(description='用户修改'))
  with patch.object(m,'plan_storyboard',return_value=result):self.q.worker(self.pid,self.stored(j))
  self.assertEqual(self.stored(j)['status'],'failed');self.assertEqual(m.load(self.pid)['shots'][0]['description'],'用户修改')

 def test_prompt_stage_respects_each_shot_video_mode(self):
  self.prepare();a=self.fixture_shot();c=dict(self.fixture_shot(),id='second',video_override={'mode':'first_frame','model':'MiniMaxH3-R2V-8step-768p'});m.update(self.pid,lambda p:p.update(shots=[a,c]));j=self.start('prompts')
  def answer(body,task):
   props=body['response_format']['json_schema']['schema']['properties']['prompts']['items']['properties'];ref='summary' in props
   entry={'index':0,'events':[{'visual':'@林岚·日常 走入 @客厅。' if ref else '林岚走入客厅。','dialogue_indices':[0],'cut_at':None}],'overall_soundscape':'脚步声。','non_diegetic_music':'N/A'}
   if ref:entry['summary']='问候'
   return self.response({'prompts':[entry]})
  with patch.object(self.q,'text_request',side_effect=answer):self.q.worker(self.pid,self.stored(j))
  self.assertEqual(self.stored(j)['status'],'completed',self.stored(j).get('error'));shots=m.load(self.pid)['shots'];self.assertEqual(shots[0]['prompt_video_mode'],'reference');self.assertEqual(shots[1]['prompt_video_mode'],'first_frame');self.assertTrue(shots[1]['video_prompt'].split('\n',1)[1].strip().startswith(b.FIRST_FRAME))
