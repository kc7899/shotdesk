import copy,json,unittest
from unittest.mock import patch
import storyboard as b
from tests.backend import test_queue
from tests.legacy import test_storyboard_official as fixtures

# Legacy scheme tests: pin the pre-h3-structured-v2 default so they keep exercising the old pipeline.
import storyboard as _legacy_scheme_storyboard
_legacy_scheme_default=_legacy_scheme_storyboard.DEFAULT_SCHEME
def setUpModule():_legacy_scheme_storyboard.DEFAULT_SCHEME='huobao-native-v1'
def tearDownModule():_legacy_scheme_storyboard.DEFAULT_SCHEME=_legacy_scheme_default

m=test_queue.m
class CompletionFirst(unittest.TestCase):
 setUp=fixtures.legacy_setup
 tearDown=test_queue.QueueContracts.tearDown
 prepare=fixtures.OfficialStoryboard.prepare
 row=fixtures.OfficialStoryboard.row
 def task(self,p):
  skill=m.storyboard_skill_bundle(p);return {'id':m.uid(),'model':'local','storyboard_stage':'all','storyboard_skill':{k:v for k,v in skill.items() if k not in ('text','official_text')},'storyboard_skill_text':skill['text'],'storyboard_official_text':skill['official_text']}
 def invalid(self,*args):return {'choices':[{'message':{'content':'{"broken":true}'}}]}
 def test_one_click_completes_even_when_all_model_outputs_are_malformed(self):
  p=self.prepare();before=copy.deepcopy(p);task=self.task(p)
  with patch.object(self.q,'text_request',side_effect=self.invalid):result=m.plan_storyboard(p,task)
  self.assertEqual(p,before);self.assertEqual(len(result['shots']),1);shot=result['shots'][0];self.assertEqual(shot['dialogue'][0]['text'],'您好。');self.assertIn('<d>[Chinese] 您好。</d>',shot['video_prompt']);self.assertEqual(shot['generation_quality'],'basic');self.assertTrue(task['storyboard_quality_notes'])
  self.assertTrue(b.check_existing(m.AppContext(),dict(p,shots=result['shots']))['ok'])
 def test_all_existing_shots_finish_without_losing_source_or_media(self):
  p=self.prepare();a=dict(self.row(),id='one',duration=6,video_prompt='',versions=[{'id':'old','kind':'video','url':'/old.mp4'}],video='/old.mp4',video_override=None);p['shots']=[a,dict(a,id='two')];task=self.task(p);task.update(storyboard_stage='prompts',storyboard_shot_ids=['one','two']);before=copy.deepcopy(p)
  with patch.object(self.q,'text_request',side_effect=self.invalid):result=m.plan_storyboard(p,task)
  self.assertEqual(p,before)
  for old,new in zip(p['shots'],result['shots']):
   for key in ('id','description','dialogue','asset_ids','character_looks','versions','video'):self.assertEqual(old[key],new[key])
   self.assertFalse(b.prompt_is_missing(m.AppContext(),new));b.validate(m.AppContext(),p,new,new['video_prompt'],'reference')
 def test_external_service_failure_is_not_disguised_as_success(self):
  p=self.prepare();task=self.task(p)
  with patch.object(self.q,'text_request',side_effect=ValueError('HTTP 503 model unavailable')):
   with self.assertRaisesRegex(ValueError,'503'):m.plan_storyboard(p,task)
 def test_cancellation_does_not_generate_fallback(self):
  import task_queue
  p=self.prepare();task=self.task(p)
  with patch.object(self.q,'text_request',side_effect=task_queue.Cancelled('stop')):
   with self.assertRaises(task_queue.Cancelled):m.plan_storyboard(p,task)
 def test_soft_language_polish_does_not_block_exact_source_dialogue(self):
  p=self.prepare();p['prompt_language']='en';shot=dict(self.row(),id='one',duration=6,video_prompt='',versions=[],video_override=None);task=self.task(p);b.basic_prompt(m.AppContext(),p,shot,task,'format failed')
  self.assertIn('您好。',shot['video_prompt']);self.assertEqual(shot['prompt_language'],'zh');self.assertEqual(shot['generation_quality'],'basic')

 def test_basic_plan_without_asset_catalog_preserves_named_source_speech(self):
  script='甲：你好。\n乙：再见。\n'
  result=b.basic_plan({'script':script,'assets':[]},0,len(script),None,'bad model')
  self.assertEqual([(line['speaker'],line['text']) for shot in result['shots'] for line in shot['dialogue']],[('甲','你好。'),('乙','再见。')])
