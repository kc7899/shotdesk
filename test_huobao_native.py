import copy,hashlib,json,re,unittest
from unittest.mock import patch
import test_queue
try:import huobao_native as h
except ImportError:raise unittest.SkipTest('optional Huobao package not distributed')
import storyboard as b

# Legacy scheme tests: pin the pre-h3-structured-v2 default so they keep exercising the old pipeline.
import storyboard as _legacy_scheme_storyboard
_legacy_scheme_default=_legacy_scheme_storyboard.DEFAULT_SCHEME
def setUpModule():_legacy_scheme_storyboard.DEFAULT_SCHEME='huobao-native-v1'
def tearDownModule():_legacy_scheme_storyboard.DEFAULT_SCHEME=_legacy_scheme_default

m=test_queue.m
if not (m.ROOT/'docs/huobao-native').exists():raise unittest.SkipTest('optional Huobao package not distributed')
class Native(unittest.TestCase):
 setUp=test_queue.QueueContracts.setUp
 tearDown=test_queue.QueueContracts.tearDown
 def project(self):
  p=m.load(self.pid);p['script']='银行营业大厅。小刘站在柜台左侧。小刘：您好。';p['video_mode']='reference';p['video_model']='MiniMaxH3-R2V-8step-768p'
  p['assets']=[{'id':'role','name':'小刘','type':'角色','prompt':'成年女性','image':'/identity.png','default_look_id':'uniform','looks':[{'id':'uniform','name':'制服','image':'/uniform.png','prompt':'银行制服'}]},{'id':'scene','name':'银行营业大厅','type':'场景','prompt':'柜台','image':'/bank.png'}];return p
 def task(self,p):
  x=m.storyboard_skill_bundle(p)
  return {'id':m.uid(),'model':'local','storyboard_stage':'all','storyboard_skill':{k:v for k,v in x.items() if k not in ('text','prompt_generator_text')},'storyboard_skill_text':x['text'],'huobao_prompt_generator_text':x['prompt_generator_text']}
 def call(self,name,args):return {'choices':[{'message':{'content':'','tool_calls':[{'id':m.uid(),'type':'function','function':{'name':name,'arguments':json.dumps(args,ensure_ascii=False)}}]},'finish_reason':'tool_calls'}]}
 def row(self):return {'shot_number':1,'scene_id':2,'character_ids':[1],'prop_ids':[],'duration':9,'description':'【镜头1】小刘站在左侧说：“您好。”','video_prompt':'人物：@小刘；场景：@银行营业大厅\n0-3秒：@小刘说：“您好。”'}
 def test_all_vendored_files_identical_and_no_own_rules(self):
  root=m.ROOT/'docs/huobao-native';manifest=json.loads((root/'manifest.json').read_text())
  for path,digest in manifest['files'].items():self.assertEqual(hashlib.sha256((root/path).read_bytes()).hexdigest(),digest,path)
  skill=m.storyboard_skill_bundle(self.project());self.assertEqual(skill['format'],h.FORMAT);self.assertNotIn('official_text',skill);self.assertNotIn('director_format',skill)
  self.assertTrue(skill['text'].startswith(h.body((root/'workspace/prompts/storyboard_breaker.md').read_text())))
  for name in ('character-prompt','scene-prompt','prop-prompt','video-prompt'):self.assertIn('## Skill: prompt-generator/'+name,skill['prompt_generator_text'])
 def test_native_tool_loop_and_raw_save_load_compile(self):
  p=self.project();before=copy.deepcopy(p);t=self.task(p);row=self.row()
  replies=iter([self.call('readStoryboardContext',{}),self.call('saveStoryboards',{'replace_existing':True,'storyboards':[row]}),{'choices':[{'message':{'content':'完成'},'finish_reason':'stop'}]}])
  bodies=[]
  def request(body,task):bodies.append(copy.deepcopy(body));return next(replies)
  with patch.object(self.q,'text_request',side_effect=request):out=b.plan(m.AppContext(),p,t)
  self.assertEqual(p,before);shot=out['shots'][0];self.assertEqual(shot['video_prompt'],row['video_prompt']);self.assertEqual(shot['asset_ids'],['scene','role']);self.assertEqual(shot['character_looks'],{'role':'uniform'})
  self.assertEqual(bodies[0]['max_tokens'],16384);self.assertEqual((bodies[0]['temperature'],bodies[0]['top_p'],bodies[0]['presence_penalty']),(0.3,0.8,1.0));self.assertNotIn('response_format',bodies[0]);self.assertIn('当前集已有角色：小刘(ID:1)',bodies[0]['messages'][1]['content'])
  p['shots']=[shot];m.save(self.root/'project.json',p);fresh=m.load(self.pid);self.assertEqual(fresh['shots'][0]['video_prompt'],row['video_prompt'])
  compiled,bindings=m.compile_shot_prompt(fresh,fresh['shots'][0],'video',m.image_resources(fresh,fresh['shots'][0]));self.assertIn('@图片1银行营业大厅',compiled);self.assertIn('@图片2小刘',compiled);self.assertNotIn('Duration:',compiled)
 def test_native_upsert_invalid_id_feedback_and_no_auto_binding(self):
  p=self.project();session=h.Session(m.AppContext(),p,self.task(p));row=self.row()
  session.execute('saveStoryboards',{'replace_existing':True,'storyboards':[row,row]});self.assertEqual(len(session.rows),1)
  with self.assertRaises(ValueError):session.execute('saveStoryboards',{'storyboards':[dict(row,character_ids=[99])]})
  session.execute('updateStoryboard',{'storyboard_id':1,'description':'null','video_prompt':'new'});self.assertEqual(session.rows[0]['description'],row['description'])
  shot=session.shots()[0];shot['asset_ids']=[];m.sync_shot_mentions(p,shot);self.assertEqual(shot['asset_ids'],[])
 def test_tool_error_is_returned_to_model_for_self_repair(self):
  p=self.project();task=self.task(p);calls=[]
  responses=iter([self.call('saveStoryboards',{'storyboards':[dict(self.row(),character_ids=[999])]}),self.call('saveStoryboards',{'replace_existing':True,'storyboards':[self.row()]}),{'choices':[{'message':{'content':'完成'},'finish_reason':'stop'}]}])
  def request(body,t):calls.append(copy.deepcopy(body));return next(responses)
  with patch.object(self.q,'text_request',side_effect=request):result=h.plan(m.AppContext(),p,task)
  self.assertEqual(len(result['shots']),1);self.assertIn('error',json.loads(calls[1]['messages'][-1]['content']))
 def test_missing_prompt_uses_native_generator_all_skills(self):
  p=self.project();task=self.task(p);row=self.row();row.pop('video_prompt');session=h.Session(m.AppContext(),p,task);session.execute('saveStoryboards',{'replace_existing':True,'storyboards':[row]});calls=[]
  replies=iter([self.call('updateStoryboard',{'storyboard_id':1,'video_prompt':'@小刘说：“您好。”'}),{'choices':[{'message':{'content':'完成'},'finish_reason':'stop'}]}])
  def request(body,t):calls.append(copy.deepcopy(body));return next(replies)
  with patch.object(self.q,'text_request',side_effect=request):session.fill_prompts()
  self.assertEqual(session.rows[0]['video_prompt'],'@小刘说：“您好。”');self.assertIn('第一行是信息头',calls[0]['messages'][1]['content']);self.assertEqual(len(calls[0]['tools']),8)
 def test_queue_freezes_native_prompts_and_protects_assets(self):
  p=self.project();m.save(self.root/'project.json',p);before=m.load(self.pid)
  with patch.object(self.q,'enqueue',side_effect=lambda pid,j:j):task=self.q.start_storyboard(self.pid)
  self.assertTrue(task['huobao_prompt_generator_text']);self.assertNotIn('prompt_generator_text',task['storyboard_skill']);self.assertNotIn('huobao_prompt_generator_text',self.q.public(self.pid,task))
  replies=iter([self.call('saveStoryboards',{'replace_existing':True,'storyboards':[self.row()]}),{'choices':[{'message':{'content':'完成'},'finish_reason':'stop'}]}])
  with patch.object(self.q,'text_request',side_effect=lambda body,t:next(replies)):self.q.worker(self.pid,task)
  self.assertEqual(task['status'],'completed');after=m.load(self.pid);self.assertEqual(after['assets'],before['assets']);self.assertEqual(after['script'],before['script']);self.assertEqual(after['shots'][0]['video_prompt'],self.row()['video_prompt'])
 def test_english_exact_directive_and_original_prompts(self):
  en=h.instructions(m.ROOT,'storyboard_breaker','en');self.assertIn('MUST be written in English.',en);self.assertIn('## Output Language (HIGHEST PRIORITY)',en)
 def test_streaming_tool_call_fragments_are_assembled(self):
  import io
  from unittest.mock import Mock
  chunks=[{'choices':[{'delta':{'tool_calls':[{'index':0,'id':'call1','type':'function','function':{'name':'saveStoryboards','arguments':'{"story'}}]}}]}, {'choices':[{'delta':{'tool_calls':[{'index':0,'function':{'arguments':'boards":[]}'}}]}}]}, {'choices':[{'delta':{},'finish_reason':'tool_calls'}]}]
  raw=b''.join(('data: '+json.dumps(c)+'\n\n').encode() for c in chunks)+b'data: [DONE]\n\n'
  response=io.BytesIO(raw);response.status=200;conn=Mock();conn.getresponse.return_value=response
  with patch('task_queue.http.client.HTTPConnection',return_value=conn):out=self.q.text_request({'messages':[]},{'id':m.uid()})
  call=out['choices'][0]['message']['tool_calls'][0];self.assertEqual(call['id'],'call1');self.assertEqual(call['function']['name'],'saveStoryboards');self.assertEqual(json.loads(call['function']['arguments']),{'storyboards':[]});conn.close.assert_called_once()
 def test_native_check_does_not_apply_old_h3_or_source_rules(self):
  p=self.project();session=h.Session(m.AppContext(),p,self.task(p));session.execute('saveStoryboards',{'storyboards':[self.row()]});p['shots']=session.shots();report=b.check_existing(m.AppContext(),p)
  self.assertTrue(report['ok'],report)
if __name__=='__main__':unittest.main()
