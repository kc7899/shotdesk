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
class DialogueSlots(unittest.TestCase):
 setUp=fixtures.legacy_setup
 tearDown=test_queue.QueueContracts.tearDown
 prepare=fixtures.OfficialStoryboard.prepare
 row=fixtures.OfficialStoryboard.row
 response=fixtures.OfficialStoryboard.response
 def test_slot_keys_compile_in_source_order_not_object_insertion_order(self):
  event=lambda text:{'visual':text,'cut_at':None}
  obj={'prompts':[{'events':{'opening':None,'dialogue':{'line_1':event('Second.'),'line_0':event('First.')},'closing':event('Ends.')}}]}
  result=b.compile_dialogue_slots(obj,2);self.assertEqual([e['dialogue_indices'] for e in result['prompts'][0]['events']],[[0],[1],[]])
  text=b.compile_dialogue_events(result,'h3-base',2,8)['prompts'][0]['integrated_multimodal_description'];self.assertLess(text.index('{{dialogue:0}}'),text.index('{{dialogue:1}}'))
 def test_missing_unknown_and_empty_action_slots_are_not_fabricated(self):
  for lines in ({},{'line_1':{'visual':'Still.','cut_at':None}}):
   with self.assertRaises(ValueError):b.compile_dialogue_slots({'prompts':[{'events':{'opening':None,'dialogue':lines,'closing':None}}]},1)
  with self.assertRaises(ValueError):b.compile_dialogue_slots({'prompts':[{'events':{'opening':None,'dialogue':{},'closing':None}}]},0)
  result=b.compile_dialogue_slots({'prompts':[{'events':{'opening':{'visual':'Empty room.','cut_at':None},'dialogue':{},'closing':None}}]},0)
  self.assertEqual(result['prompts'][0]['events'][0]['dialogue_indices'],[])
 def test_fixed_slot_pipeline_assembles_exact_speech_and_schema_requires_slots(self):
  p=self.prepare();skill=m.storyboard_skill_bundle(p);task={'model':'local','storyboard_skill':{k:v for k,v in skill.items() if k not in ('text','official_text')},'storyboard_skill_text':skill['text'],'storyboard_official_text':skill['official_text']}
  entry={'index':0,'summary':'问候','events':{'opening':None,'dialogue':{'line_0':{'visual':'@林岚·日常 走入 @客厅。','cut_at':None}},'closing':None},'overall_soundscape':'环境声。','non_diegetic_music':'N/A'}
  with patch.object(b,'plan_in_parts',return_value={'shots':[self.row()]}),patch.object(self.q,'text_request',return_value=self.response({'prompts':[entry]})) as request:result=m.plan_storyboard(p,task)
  self.assertIn('<d>[Chinese] 您好。</d>',result['shots'][0]['video_prompt']);schema=request.call_args.args[0]['response_format']['json_schema']['schema']['properties']['prompts']['items']['properties']['events'];self.assertEqual(schema['type'],'object');self.assertEqual(schema['properties']['dialogue']['required'],['line_0'])
 def test_failed_local_prompt_diagnostics_are_saved_on_parent_task(self):
  self.prepare();shot=dict(self.row(),id='one',duration=6,video_prompt='',versions=[],video_override=None);m.update(self.pid,lambda p:p.update(shots=[shot]))
  with patch('task_queue.threading.Thread'):j=self.q.start_storyboard(self.pid,stage='prompts')
  stored=json.loads(m.job_path(self.pid,j['id']).read_text());stored['storyboard_skill']['resilient_storyboard']=False;entry={'index':0,'summary':'问候','events':{'opening':None,'dialogue':{},'closing':None},'overall_soundscape':'环境声。','non_diegetic_music':'N/A'}
  with patch.object(self.q,'text_request',return_value=self.response({'prompts':[entry]})):self.q.worker(self.pid,stored)
  failed=json.loads(m.job_path(self.pid,j['id']).read_text());self.assertEqual(failed['status'],'failed');self.assertEqual(len(failed['storyboard_json_diagnostics']),2);self.assertEqual(failed['storyboard_json_diagnostics'][0]['shot_id'],'one')
 def test_checkpoint_survives_internal_protocol_upgrade_after_final_prompt_validation(self):
  self.prepare();shot=dict(self.row(),id='one',duration=6,video_prompt='',versions=[],video_override=None);m.update(self.pid,lambda p:p.update(shots=[shot]));p=m.load(self.pid);skill=m.storyboard_skill_bundle(p)
  old={k:v for k,v in skill.items() if k not in ('text','official_text')};old.pop('h3_dialogue_slots',None);old['version']='2026-10-29.6'
  job={'id':m.uid(),'created':1,'kind':'text','operation':'generate_video_prompts','status':'failed','snapshot':copy.deepcopy(p),'storyboard_skill':old,'storyboard_shot_ids':['one'],'storyboard_prompt_parts':[{'shot_id':'one','index':0,'video_prompt':'saved'}]};m.job_save(self.pid,job)
  with patch('task_queue.threading.Thread'):j=self.q.start_storyboard(self.pid,stage='prompts')
  stored=json.loads(m.job_path(self.pid,j['id']).read_text());self.assertEqual(len(stored['storyboard_seed_prompts']),1)
