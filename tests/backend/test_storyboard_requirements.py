import copy,json,unittest
from unittest.mock import patch
import h3_structured as H
from tests.backend.test_h3_structured import Api,FakeQ,project
from tests.backend import test_portable as fixture
import shot_preparation
class DirectorRequirements(unittest.TestCase):
 def test_requirements_reach_each_planning_chunk(self):
  p=project();p['storyboard_requirements']='适当增加紧张场景的反应镜头。';api=Api(FakeQ([]));task={'storyboard_skill':{'video_mode':p['video_mode'],'video_model':p['video_model']},'model':'fake'}
  with patch.object(H,'asset_profiles',return_value={}),patch.object(H,'ask_rows',side_effect=RuntimeError('captured')) as ask:
   with self.assertRaisesRegex(RuntimeError,'captured'):H.plan(api,p,task)
  payload=ask.call_args.args[4];self.assertEqual(payload['storyboard_requirements'],p['storyboard_requirements']);self.assertEqual(p['shots'],[])
 def test_custom_direction_does_not_replace_schema_or_dialogue_rules(self):
  q=FakeQ([{'shots':[]}]);api=Api(q)
  with patch.object(H,'validate_rows',return_value=[]),patch.object(H,'resolve_lines',return_value=[]):H.ask_rows(api,{'model':'fake'},[],H.model_rules('MiniMaxH3-R2V-8step-768p'),{'storyboard_requirements':'增加打戏时长'},[],[],False)
  instruction=q.bodies[0]['messages'][0]['content'];self.assertIn('storyboard_requirements',instruction);self.assertIn('胜负结果',instruction);self.assertIn('line_ids',instruction);self.assertIn('原台词',instruction)
 def test_prompt_fingerprint_changes_when_direction_changes(self):
  p=project();s={'description':'A person enters','duration':4,'asset_ids':[],'character_looks':{}};before=shot_preparation.fingerprint(p,s,'prompts');p['storyboard_requirements']='增加停顿';self.assertNotEqual(before,shot_preparation.fingerprint(p,s,'prompts'))
class DirectorRequirementsHTTP(unittest.TestCase):
 setUp=fixture.Portable.setUp
 req=fixture.Portable.req
 def test_save_reload_and_task_snapshot(self):
  import server
  p=self.req('/api/projects',{'name':'Additional direction'});pid=p['id'];text='增加打戏的攻防细节，保持胜负不变。'
  self.req('/api/projects/'+pid+'/save',{'storyboard_requirements':text,'script':'A character enters.'});p=self.req('/api/projects/'+pid);self.assertEqual(p['storyboard_requirements'],text)
  with patch.object(self.q,'enqueue',side_effect=lambda pid,j:j),patch.object(server,'llm_model',return_value='fake'):job=self.q.start_storyboard(pid)
  self.assertEqual(job['snapshot']['storyboard_requirements'],text)
  self.req('/api/projects/'+pid+'/save',{'storyboard_requirements':''});self.assertEqual(self.req('/api/projects/'+pid)['storyboard_requirements'],'')
 def test_invalid_requirements_rejected_without_changing_project(self):
  import urllib.error
  p=self.req('/api/projects',{'name':'Validate direction'});pid=p['id']
  for text in ([],123,'x'*6001):
   with self.assertRaises(urllib.error.HTTPError):self.req('/api/projects/'+pid+'/save',{'storyboard_requirements':text})
  self.assertFalse(self.req('/api/projects/'+pid).get('storyboard_requirements'))
