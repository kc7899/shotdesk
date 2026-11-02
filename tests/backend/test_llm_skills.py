import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import llm_skills as skills
from runtime_config import RuntimeConfig
class LLMSkills(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.settings=RuntimeConfig(Path(self.tmp.name))
  self.api=SimpleNamespace(SETTINGS=self.settings,Q=SimpleNamespace(persist=Mock()),load=lambda pid:{'llm_skill_mode':'auto'})
  self.custom={'id':'continuity','name':'Continuity','content':'Preserve screen direction.','stages':['prompts'],'enabled':True}
  self.body={'messages':[{'role':'system','content':'Current task JSON schema wins'},{'role':'user','content':'A person enters'}]}
 def test_default_builtin_guidance_is_task_scoped(self):
  j={'operation':'prepare_shots','preparation_progress':{'stage':'assets'}}
  result=skills.apply(self.api,self.body,j)
  self.assertIn('造型必须属于该角色',result['messages'][0]['content']);self.assertNotIn('明确景别',result['messages'][0]['content'])
  self.assertEqual(j['llm_skill_trace'][0]['stage'],'matching');self.assertNotIn('_llm_skill_config',self.body)
 def test_custom_only_applies_to_selected_stage_and_does_not_mutate_request(self):
  self.settings.update({'llm_skills':[self.custom]});old=copy.deepcopy(self.body)
  j={'operation':'prepare_shots','preparation_progress':{'stage':'prompts'}};result=skills.apply(self.api,self.body,j)
  self.assertIn(self.custom['content'],result['messages'][0]['content']);self.assertEqual(result['messages'][1]['content'],old['messages'][0]['content']);self.assertEqual(self.body,old)
  j2={'operation':'prepare_shots','preparation_progress':{'stage':'assets'}};result=skills.apply(self.api,self.body,j2);self.assertNotIn(self.custom['content'],result['messages'][0]['content'])
 def test_project_builtin_only_and_disabled_skill(self):
  self.settings.update({'llm_skills':[self.custom]})
  j={'operation':'generate_script','snapshot':{'llm_skill_mode':'builtin'}}
  result=skills.apply(self.api,self.body,j);self.assertNotIn(self.custom['content'],str(result));self.assertEqual(len(j['llm_skill_trace']),1)
  self.custom['enabled']=False;self.settings.update({'llm_skills':[self.custom]});j={'operation':'generate_video_prompts'};self.assertEqual(len(skills.apply(self.api,self.body,j)['messages']),3);self.assertEqual(len(j['llm_skill_trace']),1)
 def test_native_skill_not_injected_twice_and_trace_uses_actual_hash(self):
  native='Native screenwriter instruction';j={'operation':'generate_script','script_skill_text':native}
  body={'messages':[{'role':'system','content':native}]};result=skills.apply(self.api,body,j);self.assertEqual(result,body)
  import hashlib
  self.assertEqual(j['llm_skill_trace'][0]['sha256'],hashlib.sha256(native.encode()).hexdigest())
 def test_job_freezes_custom_config_and_trace_has_no_content(self):
  self.settings.update({'llm_skills':[self.custom]});j={'operation':'prepare_shots','preparation_progress':{'stage':'prompts'}}
  skills.apply(self.api,self.body,j);self.settings.update({'llm_skills':[]});result=skills.apply(self.api,self.body,j)
  self.assertIn(self.custom['content'],str(result));self.assertEqual(len(j['llm_skill_trace']),2);self.assertNotIn('content',json.dumps(j['llm_skill_trace']))
 def test_rejects_empty_stages_bad_values_and_size(self):
  for key,value in [('stages',[]),('stages',['unknown']),('content','a'*12001),('enabled','true'),('id','../../secret')]:
   with self.subTest(key=key),self.assertRaises(ValueError):skills.validate([{**self.custom,key:value}])
  with self.assertRaises(ValueError):skills.validate([self.custom,self.custom])
 def test_settings_persist_privately(self):
  self.settings.update({'llm_skills':[self.custom]});self.assertEqual(self.settings.read()['llm_skills'][0],self.custom);self.assertEqual(self.settings.path.stat().st_mode&0o777,0o600)
 def test_unknown_operations_unchanged(self):
  j={'operation':'unknown'};self.assertIs(skills.apply(self.api,self.body,j),self.body);self.assertNotIn('llm_skill_trace',j)
