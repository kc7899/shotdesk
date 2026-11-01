import copy,json,unittest
from unittest.mock import patch
import test_queue
import storyboard as b

# Legacy scheme tests: pin the pre-h3-structured-v2 default so they keep exercising the old pipeline.
import storyboard as _legacy_scheme_storyboard
_legacy_scheme_default=_legacy_scheme_storyboard.DEFAULT_SCHEME
def setUpModule():_legacy_scheme_storyboard.DEFAULT_SCHEME='huobao-native-v1'
def tearDownModule():_legacy_scheme_storyboard.DEFAULT_SCHEME=_legacy_scheme_default

m=test_queue.m
if not (m.ROOT/'docs/skills/shotdesk-storyboard/references/h3-ref-en.txt').exists():raise unittest.SkipTest('optional unlicensed upstream reference fixtures are not distributed')
def legacy_bundle(p):
 # Frozen v8 fixtures continue testing the shipped compatibility path.
 raw=(m.ROOT/'docs/skills/shotdesk-storyboard/references/legacy-v8.md').read_text()
 with patch.object(m,'prompt_skill_bundle',return_value={'text':raw,'version':'2026-10-29.8'}):bundle=b.skill_bundle(m.AppContext(),p)
 return bundle

def legacy_setup(self):
 test_queue.QueueContracts.setUp(self)
 raw=(m.ROOT/'docs/skills/shotdesk-storyboard/references/legacy-v8.md').read_text()
 base=patch.object(m,'prompt_skill_bundle',return_value={'text':raw,'version':'2026-10-29.8'});base.start();self.addCleanup(base.stop)
 frozen=patch.object(m,'storyboard_skill_bundle',side_effect=legacy_bundle);frozen.start();self.addCleanup(frozen.stop)

class OfficialStoryboard(unittest.TestCase):
 setUp=legacy_setup
 tearDown=test_queue.QueueContracts.tearDown
 def prepare(self,mode='reference'):
  m.update(self.pid,lambda p:p.update(script='林岚：您好。\n林岚走进客厅。',video_mode=mode,video_model='MiniMaxH3-R2V-8step-768p',assets=[{'id':'person','name':'林岚','type':'角色','prompt':'成年女性','looks':[{'id':'look','name':'日常','prompt':'蓝色衬衫','versions':[]}],'image':'/portrait.png','default_look_id':'look'},{'id':'room','name':'客厅','type':'场景','prompt':'客厅','image':'/room.png'}]))
  return m.load(self.pid)
 def row(self):return {'title':'进入','description':'林岚走进客厅并打招呼。','duration':1,'dialogue':[{'speaker':'林岚','text':'您好。'}],'action_seconds':1,'pause_seconds':.5,'duration_basis':'问候和走入','image_prompt':'@林岚·日常 在 @客厅','asset_ids':['person','room'],'character_looks':{'person':'look'}}
 def prompt(self):return 'subject_definitions:\n@林岚·日常 is the woman in a blue shirt.\n@客厅 is the living room.\nsummary:\n[reference generation] A woman greets someone.\nretention_analysis:\n@林岚·日常: fully_preserved - Keep her identity and outfit.\n@客厅: fully_preserved - Keep the room layout.\ndetailed_description:\n[Shot 1] A static medium shot frames @林岚·日常 walking into @客厅. @林岚·日常 (S1) smiles and says <d>[Chinese] 您好。</d>\noverall_soundscape:\nQuiet indoor room tone and footsteps.\nnon_diegetic_music:\nN/A'
 def response(self,obj):return {'choices':[{'message':{'content':json.dumps(obj,ensure_ascii=False)}}]}
 def task(self,p):
  skill=m.storyboard_skill_bundle(p);skill.pop('planning_format',None);skill.pop('dialogue_format',None);skill.pop('h3_batch_size',None);skill.pop('performance_format',None);skill.pop('prompt_language',None);skill.pop('dialogue_planning',None);skill.pop('h3_dialogue_slots',None);skill.pop('resilient_storyboard',None);return {'model':'local','storyboard_skill':{k:v for k,v in skill.items() if k not in ('text','official_text')},'storyboard_skill_text':'冻结旧版规划：asset_ids与character_looks；保持台词与真实引用。','storyboard_official_text':skill.get('official_text','')}
 def planned(self,p):
  task=self.task(p)
  with patch.object(self.q,'text_request',side_effect=[self.response({'analysis':'问候并进入。','shots':[self.row()]}),self.response({'prompts':[{'index':0,'video_prompt':self.prompt()}]})]) as request:result=m.plan_storyboard(p,task)
  return result,task,request
 def test_pipeline_uses_analysis_then_frozen_official_guide(self):
  p=self.prepare();before=copy.deepcopy(p);result,task,request=self.planned(p);shot=result['shots'][0]
  self.assertEqual(request.call_count,2);self.assertEqual(p,before);self.assertEqual(shot['prompt_format'],'h3-official-v1');self.assertEqual(shot['duration'],2)
  self.assertFalse(shot['timing']['verified_by_audio']);self.assertTrue(shot['timing']['adjusted']);self.assertEqual(task['storyboard_prompt_checks'][0]['attempts'],1)
  body=request.call_args_list[1].args[0];self.assertIn('Full-Reference Mode',body['messages'][0]['content']);self.assertIn('video_model',json.loads(body['messages'][1]['content']))
 def test_compile_uses_actual_picture_order_and_removes_duration_header(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0]
  inputs=[{'asset_id':'room','url':'/room.png'},{'asset_id':'person','look_id':'look','url':'/look.png'}]
  text,bindings=m.compile_shot_prompt(p,shot,'video',inputs)
  self.assertTrue(text.startswith('subject_definitions:'));self.assertNotIn('Duration:',text);self.assertIn('<Subject 2> is the woman',text);self.assertIn('Source: <Picture 2>',text);self.assertIn('<Subject 1> is the living room',text);self.assertNotIn('@',text)
  self.assertEqual(bindings[0]['reference_index'],2)
 def test_legacy_at_compiler_is_unchanged(self):
  p=self.prepare();shot={'video_prompt':'@林岚·日常 waves.','asset_ids':['person'],'character_looks':{'person':'look'}}
  text,_=m.compile_shot_prompt(p,shot,'video',[{'asset_id':'person','look_id':'look','url':'/look.png'}]);self.assertIn('参考图1',text);self.assertNotIn('<Subject',text)
 def test_wrong_format_dialogue_speaker_and_picture_indices_are_rejected(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0]
  bad=[self.prompt().replace('overall_soundscape:','wrong_field:'),self.prompt().replace('您好。','再见。'),self.prompt().replace('(S1)','(S2)'),self.prompt().replace('is the woman','is the woman in <Picture 1>')]
  for text in bad:
   with self.subTest(text=text[-90:]):
    with self.assertRaises(ValueError):b.validate(m.AppContext(),p,shot,text,'reference')
 def test_cut_outside_clip_rejected(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0];text=self.prompt().replace('overall_soundscape:','[Shot 2] At 00:20.000, the camera cuts to a door.\noverall_soundscape:')
  with self.assertRaisesRegex(ValueError,'切点'):b.validate(m.AppContext(),p,shot,text,'reference')
 def test_bounded_prompt_retry_does_not_mutate_project(self):
  p=self.prepare();task=self.task(p)
  responses=[self.response({'shots':[self.row()]}),self.response({'prompts':[{'index':0,'video_prompt':'bad'}]}),self.response({'prompts':[{'index':0,'video_prompt':'still bad'}]})]
  with patch.object(self.q,'text_request',side_effect=responses) as request:
   with self.assertRaisesRegex(ValueError,'未覆盖'):m.plan_storyboard(p,task)
  self.assertEqual(request.call_count,3);self.assertEqual(m.load(self.pid)['shots'],[])
 def test_length_truncation_does_not_use_partial_json(self):
  p=self.prepare();task=self.task(p)
  with patch.object(self.q,'text_request',return_value={'choices':[{'finish_reason':'length','message':{'content':'{"shots":[]}'}}]}):
   with self.assertRaisesRegex(ValueError,'长度限制'):m.plan_storyboard(p,task)
 def test_queue_freezes_version_and_hides_large_bodies(self):
  self.prepare()
  with patch('task_queue.threading.Thread'):j=self.q.start_storyboard(self.pid)
  self.assertEqual(len(j['storyboard_skill']['official_commit']),40);self.assertNotIn('storyboard_skill_text',j);self.assertNotIn('storyboard_official_text',j)
  stored=json.loads(m.job_path(self.pid,j['id']).read_text());self.assertIn('Full-Reference Mode',stored['storyboard_official_text'])
 def test_first_frame_alignment_and_three_fields(self):
  p=self.prepare('first_frame');shot={'duration':5,'asset_ids':[],'dialogue':[]}
  text=b.FIRST_FRAME+'\n\nintegrated_multimodal_description: [Shot 1] A static shot frames a woman entering the room.\noverall_soundscape: Quiet room tone.\nnon_diegetic_music: N/A'
  self.assertEqual(b.validate(m.AppContext(),p,shot,text,'first_frame'),text)
  with self.assertRaisesRegex(ValueError,'0秒'):b.validate(m.AppContext(),p,shot,text.replace(b.FIRST_FRAME+'\n\n',''),'first_frame')
 def test_official_numeric_output_normalizes_to_stable_mentions(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0];slots=b.reference_slots(m.AppContext(),p,shot)
  text=self.prompt().replace('@林岚·日常','<Subject 1>').replace('@客厅','<Subject 2>').replace('is the woman in a blue shirt.','is the woman in a blue shirt from <Picture 1>.').replace('is the living room.','is the living room from <Picture 2>.')
  normalized=b.normalize_references(text,slots)
  self.assertIn('@林岚·日常 (S1)',normalized);self.assertNotIn('<Subject',normalized);self.assertNotIn('<Picture',normalized)
  b.validate(m.AppContext(),p,shot,normalized,'reference')
  with self.assertRaisesRegex(ValueError,'来源'):b.normalize_references(text.replace('from <Picture 1>','from <Picture 2>'),slots)
  with self.assertRaisesRegex(ValueError,'reference_slots'):b.normalize_references(text.replace('<Subject 2>','<Subject 9>'),slots)
 def test_generated_speaker_table_is_per_clip(self):
  p=self.prepare();_,_,request=self.planned(p);payload=json.loads(request.call_args_list[1].args[0]['messages'][1]['content'])
  self.assertEqual(payload['shots'][0]['speaker_ids'],{'林岚':'S1'});self.assertEqual(payload['shots'][0]['reference_slots'][0]['label'],'@林岚·日常')
 def test_english_body_and_no_invented_audio_reference(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0]
  text=self.prompt().replace('A static medium shot frames @林岚·日常 walking into @客厅.','固定镜头表现人物走进客厅以后缓缓停下。')
  with self.assertRaisesRegex(ValueError,'英文'):b.validate(m.AppContext(),p,shot,text,'reference')
  with self.assertRaisesRegex(ValueError,'虚构'):b.validate(m.AppContext(),p,shot,self.prompt().replace('Quiet indoor room tone','Use <Audio 1>'),'reference')

 def test_dialogue_placeholders_render_exact_text_and_source(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0]
  text=self.prompt().replace('@林岚·日常 (S1) smiles and says <d>[Chinese] 您好。</d>','{{dialogue:0}}')
  out=b.render_dialogue(m.AppContext(),p,shot,text,'reference');self.assertIn('@林岚·日常 (S1) says: <d>[Chinese] 您好。</d>',out);b.validate(m.AppContext(),p,shot,out,'reference')
  with self.assertRaisesRegex(ValueError,'占位'):b.render_dialogue(m.AppContext(),p,shot,text.replace('{{dialogue:0}}','{{dialogue:1}}'),'reference')
 def test_missing_speaker_cues_are_added_without_changing_spoken_text(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0];text=self.prompt().replace('@林岚·日常 (S1) smiles and says','The woman smiles and says')
  out=b.render_dialogue(m.AppContext(),p,shot,text,'reference');self.assertIn('您好。',out);self.assertIn('@林岚·日常 (S1) says:',out);b.validate(m.AppContext(),p,shot,out,'reference')
  with self.assertRaises(ValueError):b.render_dialogue(m.AppContext(),p,shot,text.replace('您好。','再见。'),'reference')
 def test_speaker_fix_preserves_delivery_without_duplicate_says(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0];text=self.prompt().replace('@林岚·日常 (S1) smiles and says','@林岚·日常 says in a calm tone,')
  out=b.render_dialogue(m.AppContext(),p,shot,text,'reference');self.assertIn('@林岚·日常 (S1) says in a calm tone,',out);self.assertEqual(out.count('says'),1);b.validate(m.AppContext(),p,shot,out,'reference')

 def test_silent_clip_does_not_keep_speaker_ids(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0];shot['dialogue']=[];text=self.prompt().replace('<d>[Chinese] 您好。</d>','')
  out=b.render_dialogue(m.AppContext(),p,shot,text,'reference');self.assertNotIn('(S1)',out)

 def test_mode_switch_requires_new_prompt(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0];shot['video_override']={'mode':'first_frame','model':'MiniMaxH3-8step-I2V'}
  with self.assertRaisesRegex(ValueError,'方案已改变'):b.compile_prompt(m.AppContext(),p,shot,shot['video_prompt'],[])
 def test_timing_includes_turns_and_extra_actions_without_ten_second_cap(self):
  p=self.prepare();row=self.row();row['dialogue']=[{'speaker':'林岚','text':'你'*89}];p['script']='你'*89;row['action_seconds']=2
  duration,budget=b.timing(m.AppContext(),row,p['script']);self.assertGreater(duration,24);self.assertEqual(budget['speech_seconds'],22.25)
 def test_invented_dialogue_and_invalid_timing_are_rejected(self):
  p=self.prepare();row=self.row();row['dialogue'][0]['text']='不在剧本中'
  with self.assertRaisesRegex(ValueError,'原文'):b.timing(m.AppContext(),row,p['script'])
  row=self.row();row['action_seconds']=float('inf')
  with self.assertRaises(ValueError):b.timing(m.AppContext(),row,p['script'])
 def test_batches_receive_director_analysis_and_correct_neighbors(self):
  p=self.prepare();before=copy.deepcopy(p);task=self.task(p)
  rows=[dict(self.row(),title='镜头'+str(i),description='状态'+str(i)) for i in range(4)]
  responses=[self.response({'analysis':'请求后等待回应；保持画面左右与情绪。','shots':rows}),self.response({'prompts':[{'index':i,'video_prompt':self.prompt()} for i in range(3)]}),self.response({'prompts':[{'index':3,'video_prompt':self.prompt()}]})]
  with patch.object(self.q,'text_request',side_effect=responses) as request:result=m.plan_storyboard(p,task)
  self.assertEqual(request.call_count,3);self.assertEqual(len(result['shots']),4);self.assertEqual(p,before)
  first=json.loads(request.call_args_list[1].args[0]['messages'][1]['content']);last=json.loads(request.call_args_list[2].args[0]['messages'][1]['content'])
  self.assertIsNone(first['continuity_context']['previous']);self.assertEqual(first['continuity_context']['next']['index'],3)
  self.assertEqual(last['continuity_context']['previous']['index'],2);self.assertIsNone(last['continuity_context']['next'])
  self.assertEqual(last['continuity_context']['planning_analysis'],task['storyboard_analysis'])
  self.assertNotIn('video_prompt',last['continuity_context']['previous'])
  self.assertEqual([x['index'] for x in last['shots']],[3])
  for call in request.call_args_list:self.assertIn(task['storyboard_skill_text'],call.args[0]['messages'][0]['content'])
 def test_long_source_segments_cover_exact_source_in_order(self):
  script=('【办公室】\n林岚：报告已经发给你了。\n周明抬头，林岚等候。\n'*100)
  spans=b.planning_segments(script)
  self.assertGreater(len(spans),1);self.assertEqual(''.join(script[a:z] for a,z in spans),script)
  self.assertEqual(spans[0][0],0);self.assertEqual(spans[-1][1],len(script))
  self.assertTrue(all(a[1]==z[0] for a,z in zip(spans,spans[1:])))
 def test_only_truncated_planning_segment_is_split_and_retried(self):
  script=('林岚：您好。\n'*60);task={'model':'local'}
  truncated={'choices':[{'finish_reason':'length','message':{'content':'{"shots":[{"title":"discard"}]}'}}]}
  response=lambda title:self.response({'analysis':title,'shots':[dict(self.row(),title=title)]})
  with patch.object(self.q,'text_request',side_effect=[truncated,response('前半'),response('后半')]) as request:
   result=b.plan_in_parts(m.AppContext(),task,{'script':script},'frozen instructions')
  self.assertEqual([r['title'] for r in result['shots']],['前半','后半']);self.assertEqual(request.call_count,3)
  payloads=[json.loads(c.args[0]['messages'][1]['content']) for c in request.call_args_list[1:]]
  self.assertEqual(''.join(p['planning_scope']['source_segment'] for p in payloads),script)
  self.assertEqual(payloads[1]['continuity_context']['previous_shots'][0]['title'],'前半')
  self.assertEqual(len(task['storyboard_planning_checks']),3)
 def test_long_plan_does_not_write_partial_results_if_later_request_fails(self):
  p=self.prepare();p['script']='林岚：您好。\n' * 300;before=copy.deepcopy(p);task=self.task(p)
  with patch.object(self.q,'text_request',side_effect=[self.response({'analysis':'首段','shots':[self.row()]}),RuntimeError('停止或连接失败')]) as request:
   with self.assertRaisesRegex(RuntimeError,'停止或连接失败'):m.plan_storyboard(p,task)
  self.assertEqual(p,before);self.assertNotIn('storyboard_draft',task);self.assertEqual(request.call_count,2)
 def test_completed_plan_segments_are_not_regenerated_on_later_truncation(self):
  script='林岚：您好。\n' * 300;task={'model':'local'};spans=b.planning_segments(script)
  calls=[]
  def reply(body,_):
   scope=json.loads(body['messages'][1]['content'])['planning_scope'];calls.append((scope['start'],scope['end']))
   if len(calls)==2:return {'choices':[{'finish_reason':'length','message':{'content':'broken'}}]}
   return self.response({'analysis':'规划','shots':[self.row()]})
  with patch.object(self.q,'text_request',side_effect=reply):result=b.plan_in_parts(m.AppContext(),task,{'script':script},'instructions')
  self.assertEqual(calls.count(spans[0]),1);self.assertEqual(len(result['shots']),len(spans)+1)
 def test_invalid_json_is_repaired_once_with_json_mode(self):
  task={'model':'local'};messages=[{'role':'user','content':'JSON object'}];original=copy.deepcopy(messages)
  bad={'choices':[{'message':{'content':'{"shots":[{"title":"标题" "description":"原文"}]}'}}]}
  with patch.object(self.q,'text_request',side_effect=[bad,self.response({'shots':[self.row()]})]) as request:
   result=b.ask(m.AppContext(),task,messages)
  self.assertEqual(result['shots'][0]['dialogue'],self.row()['dialogue']);self.assertEqual(messages,original)
  self.assertEqual(request.call_count,2);self.assertEqual(task['storyboard_json_repairs'],1)
  for call in request.call_args_list:self.assertEqual(call.args[0]['response_format'],{'type':'json_object'})
  self.assertEqual(request.call_args_list[1].args[0]['messages'][-2]['role'],'assistant')
 def test_bad_json_twice_reports_readable_error_and_preserves_project(self):
  p=self.prepare();before=copy.deepcopy(p);task=self.task(p)
  with patch.object(self.q,'text_request',return_value={'choices':[{'message':{'content':'not JSON'}}]}) as request:
   with self.assertRaisesRegex(ValueError,'自动修正一次'):m.plan_storyboard(p,task)
  self.assertEqual(request.call_count,2);self.assertEqual(m.load(self.pid),before);self.assertEqual(len(task['storyboard_json_diagnostics']),2)
 def test_format_repair_does_not_repeat_successful_planning_segment(self):
  script='林岚：您好。\n'*300;task={'model':'local'};spans=b.planning_segments(script);responses=[]
  for i,_ in enumerate(spans):
   if i==1:responses.append({'choices':[{'message':{'content':'{"shots": invalid}'}}]})
   responses.append(self.response({'analysis':str(i),'shots':[dict(self.row(),title=str(i))]}))
  with patch.object(self.q,'text_request',side_effect=responses) as request:result=b.plan_in_parts(m.AppContext(),task,{'script':script},'instructions')
  self.assertEqual(len(result['shots']),len(spans));self.assertEqual(request.call_count,len(spans)+1)
  self.assertEqual([r['title'] for r in result['shots']],[str(i) for i in range(len(spans))])
 def test_json_diagnostics_are_not_exposed_by_public_jobs(self):
  public=self.q.public(self.pid,{'id':'test','storyboard_json_diagnostics':[{'response':'private raw output'}],'storyboard_json_repairs':1})
  self.assertNotIn('storyboard_json_diagnostics',public);self.assertEqual(public['storyboard_json_repairs'],1)
 def test_string_shots_are_repaired_before_becoming_continuity_context(self):
  script='林岚：您好。\n'*300;task={'model':'local'};spans=b.planning_segments(script)
  bad=self.response({'analysis':'文字错误','shots':['不是镜头对象']*112})
  responses=[bad]+[self.response({'analysis':str(i),'shots':[self.row()]}) for i in range(len(spans))]
  with patch.object(self.q,'text_request',side_effect=responses) as request:result=b.plan_in_parts(m.AppContext(),task,{'script':script},'instructions')
  self.assertEqual(len(result['shots']),len(spans));self.assertEqual(request.call_count,len(spans)+1)
  self.assertEqual(task['storyboard_planning_checks'][0]['shots'],1)
  self.assertTrue(all(c.args[0]['response_format']['type']=='json_schema' for c in request.call_args_list))
 def test_nested_type_errors_are_rejected_before_downstream_reads(self):
  changes=[('dialogue',['您好']),('character_looks','look'),('asset_ids',['person',{}]),('duration','6'),('image_prompt',{}),('dialogue',[{'speaker':'林岚','text':{}}])]
  for key,value in changes:
   with self.subTest(key=key):
    row=self.row();row[key]=value
    with self.assertRaises(ValueError):b.check_output_types({'shots':[row]},'planning')
  with self.assertRaisesRegex(ValueError,'对象'):b.check_output_types({'prompts':['bad']},'prompts')
 def test_persistently_wrong_shot_types_fail_without_counting_success(self):
  p=self.prepare();before=copy.deepcopy(p);task=self.task(p)
  with patch.object(self.q,'text_request',return_value=self.response({'shots':['bad']})) as request:
   with self.assertRaisesRegex(ValueError,'字段结构'):m.plan_storyboard(p,task)
  self.assertEqual(request.call_count,2);self.assertEqual(p,before)
  self.assertNotIn('storyboard_planning_checks',task);self.assertNotIn('storyboard_draft',task)
 def test_look_schema_restricts_each_role_to_its_own_ids(self):
  p=self.prepare();assets=m.script_reference_context(p);schema=b.output_schema('planning',assets)
  looks=schema['properties']['shots']['items']['properties']['character_looks']
  self.assertFalse(looks['additionalProperties']);self.assertEqual(looks['properties']['person']['enum'],['look']);self.assertNotIn('room',looks['properties'])
 def test_wrong_look_binding_repaired_within_segment(self):
  p=self.prepare();assets=m.script_reference_context(p);bad=self.row();bad['character_looks']={'person':'someone-elses-look'};task={'model':'local'}
  with patch.object(self.q,'text_request',side_effect=[self.response({'shots':[bad]}),self.response({'shots':[self.row()]})]) as request:
   obj=b.ask(m.AppContext(),task,[{'role':'user','content':'plan'}],output_kind='planning',planning_assets=assets)
  self.assertEqual(obj['shots'][0]['character_looks'],{'person':'look'});self.assertEqual(request.call_count,2)
  feedback=request.call_args_list[1].args[0]['messages'][-1]['content'];self.assertIn('林岚',feedback);self.assertIn('someone-elses-look',feedback)
 def test_invalid_selected_role_or_cross_person_look_fails_before_success(self):
  p=self.prepare();assets=m.script_reference_context(p);bad=self.row();bad['character_looks']={'person':'foreign-look'};task={'model':'local'}
  with patch.object(self.q,'text_request',return_value=self.response({'shots':[bad]})) as request:
   with self.assertRaisesRegex(ValueError,'林岚'):b.plan_in_parts(m.AppContext(),task,{'script':p['script'],'assets':assets},'instructions')
  self.assertEqual(request.call_count,2);self.assertNotIn('storyboard_planning_parts',task)
  row=self.row();row['asset_ids']=['room']
  with self.assertRaisesRegex(ValueError,'未关联角色'):b.check_planning_bindings({'shots':[row]},assets)
 def test_accepted_plans_remain_internal_on_later_failure(self):
  p=self.prepare();context={'script':'林岚：您好。\n'*300,'assets':m.script_reference_context(p)};task={'model':'local'}
  with patch.object(self.q,'text_request',side_effect=[self.response({'analysis':'first','shots':[self.row()]}),RuntimeError('stop')]):
   with self.assertRaisesRegex(RuntimeError,'stop'):b.plan_in_parts(m.AppContext(),task,context,'instructions')
  self.assertEqual(len(task['storyboard_planning_parts']),1);self.assertEqual(task['storyboard_planning_parts'][0]['shots'][0]['character_looks'],{'person':'look'})
  self.assertNotIn('storyboard_planning_parts',self.q.public(self.pid,task))
 def fresh_task(self,p):
  skill=m.storyboard_skill_bundle(p);skill.pop('h3_dialogue_events',None);skill.pop('h3_event_timing',None);skill.pop('h3_stable_refs',None);skill.pop('performance_format',None);skill.pop('prompt_language',None);skill.pop('dialogue_planning',None);skill.pop('h3_dialogue_slots',None);skill.pop('resilient_storyboard',None)
  return {'model':'local','storyboard_skill':{k:v for k,v in skill.items() if k not in ('text','official_text')},'storyboard_skill_text':skill['text'],'storyboard_official_text':skill.get('official_text','')}
 def unified_row(self):
  row=self.row();ids=row.pop('asset_ids');looks=row.pop('character_looks');row['references']=[{'asset_id':aid,'look_id':looks.get(aid)} for aid in ids];return row
 def test_unified_reference_plan_compiles_through_official_h3(self):
  p=self.prepare();before=copy.deepcopy(p);task=self.fresh_task(p)
  with patch.object(self.q,'text_request',side_effect=[self.response({'analysis':'空间连续','shots':[self.unified_row()]}),self.response({'prompts':[dict(index=0,**{k:v for k,v in b.sections(self.prompt(),True).items() if k in ('summary','detailed_description','overall_soundscape','non_diegetic_music')})]})]) as request:result=m.plan_storyboard(p,task)
  shot=result['shots'][0];self.assertEqual(shot['asset_ids'],['person','room']);self.assertEqual(shot['character_looks'],{'person':'look'});self.assertNotIn('references',shot);self.assertEqual(p,before)
  first=request.call_args_list[0].args[0];second=request.call_args_list[1].args[0]
  self.assertNotIn('## 第二阶段',first['messages'][0]['content']);self.assertNotIn('## 第一阶段',second['messages'][0]['content'])
  schema=first['response_format']['json_schema']['schema']['properties']['shots']['items'];self.assertNotIn('asset_ids',schema['properties']);self.assertNotIn('character_looks',schema['properties']);self.assertIn('references',schema['required'])
  text,_=m.compile_shot_prompt(p,shot,'video',[{'asset_id':'room','url':'/room.png'},{'asset_id':'person','url':'/look.png','look_id':'look'}]);self.assertIn('<Subject 2>',text)
 def test_redundant_inactive_look_is_repaired_without_adding_character(self):
  assets=[{'id':'a','name':'甲','type':'角色','looks':[{'id':'la'}]},{'id':'b','name':'乙','type':'角色','looks':[{'id':'lb'}]}];row=self.row();row.update(asset_ids=['a'],character_looks={'a':'la','b':'lb'});task={}
  obj=b.normalize_references_plan({'shots':[row]},assets,task)
  b.check_planning_bindings(obj,assets);self.assertEqual(obj['shots'][0]['asset_ids'],['a']);self.assertEqual(obj['shots'][0]['character_looks'],{'a':'la'});self.assertEqual(task['storyboard_repairs'][0]['asset_id'],'b');self.assertEqual(row['character_looks'],{'a':'la','b':'lb'})
 def test_selected_foreign_look_is_never_silently_changed_to_default(self):
  p=self.prepare();row=self.row();row['character_looks']['person']='foreign';task={};obj=b.normalize_references_plan({'shots':[row]},m.script_reference_context(p),task)
  with self.assertRaises(ValueError):b.check_planning_bindings(obj,m.script_reference_context(p))
  self.assertEqual(obj['shots'][0]['character_looks']['person'],'foreign');self.assertNotIn('storyboard_repairs',task)
 def test_unified_refs_reject_conflicting_duplicates_and_cross_role_look(self):
  p=self.prepare();assets=m.script_reference_context(p);row=self.unified_row();row['references'].append({'asset_id':'person','look_id':None})
  with self.assertRaisesRegex(ValueError,'重复'):b.normalize_references_plan({'shots':[row]},assets,{},True)
  row=self.unified_row();row['references'][0]['look_id']='foreign'
  with self.assertRaisesRegex(ValueError,'不属于'):b.normalize_references_plan({'shots':[row]},assets,{},True)
 def test_same_reference_duplicates_are_collapsed_in_stable_order(self):
  p=self.prepare();row=self.unified_row();row['references'].append(copy.deepcopy(row['references'][0]));obj=b.normalize_references_plan({'shots':[row]},m.script_reference_context(p),{},True)
  self.assertEqual(obj['shots'][0]['asset_ids'],['person','room'])
 def test_structured_h3_assembly_keeps_dialogue_and_real_picture_order(self):
  p=self.prepare();shot=self.row();shot['duration']=4
  entry={'summary':'Greeting','detailed_description':'[Shot 1] A fixed medium shot. {{dialogue:0}}','overall_soundscape':'Quiet room tone.','non_diegetic_music':'N/A'}
  text=b.assemble_h3(m.AppContext(),p,shot,entry,'reference');text=b.render_dialogue(m.AppContext(),p,shot,text,'reference');b.validate(m.AppContext(),p,shot,text,'reference')
  shot.update(video_prompt=text,prompt_format='h3-official-v1',prompt_video_mode='reference')
  compiled,_=m.compile_shot_prompt(p,shot,'video',[{'asset_id':'room','url':'/room.png'},{'asset_id':'person','look_id':'look','url':'/look.png'}])
  self.assertIn('Source: <Picture 2>',compiled);self.assertIn('<Subject 2> (S1)',compiled);self.assertEqual(compiled.count('您好。'),1)
 def test_structured_first_frame_prefix_is_program_owned(self):
  p=self.prepare('first_frame');shot=self.row();entry={'integrated_multimodal_description':'[Shot 1] A fixed shot. {{dialogue:0}}','overall_soundscape':'Room tone.','non_diegetic_music':'N/A'}
  text=b.assemble_h3(m.AppContext(),p,shot,entry,'first_frame');text=b.render_dialogue(m.AppContext(),p,shot,text,'first_frame')
  self.assertTrue(text.startswith(b.FIRST_FRAME+'\n\n'));b.validate(m.AppContext(),p,shot,text,'first_frame')
 def test_null_look_follows_default_without_fabricating_selection(self):
  p=self.prepare();row=self.unified_row();row['references'][0]['look_id']=None
  obj=b.normalize_references_plan({'shots':[row]},m.script_reference_context(p),{},True)
  self.assertEqual(obj['shots'][0]['character_looks'],{});self.assertEqual(obj['shots'][0]['asset_ids'],['person','room'])
 def test_stage_direction_reclassified_only_with_source_evidence(self):
  row=self.row();row['dialogue']=[{'speaker':'林岚','text':'（点头）'}];task={}
  result=b.repair_dialogue({'shots':[row]},'林岚认真点头。',task)
  self.assertEqual(result['shots'][0]['dialogue'],[]);self.assertIn('点头',result['shots'][0]['description']);self.assertEqual(len(task['storyboard_repairs']),1)
  self.assertEqual(row['dialogue'][0]['text'],'（点头）')
  with self.assertRaisesRegex(ValueError,'原文不符'):b.repair_dialogue({'shots':[row]},'林岚走进客厅。',{})
 def test_explicitly_spoken_parenthesised_words_are_preserved(self):
  row=self.row();row['dialogue']=[{'speaker':'林岚','text':'（点头）'}]
  obj=b.repair_dialogue({'shots':[row]},'林岚：“（点头）”\n林岚认真点头。',{})
  self.assertEqual(obj['shots'][0]['dialogue'][0]['text'],'（点头）')
 def test_source_ledger_materializes_exact_text_and_speaker(self):
  script='林岚点头。\n林岚：您好。\n周明：请进。';assets=[{'type':'角色','name':'林岚'},{'type':'角色','name':'周明'}];lines=b.script_dialogue_lines(script,assets)
  row=self.row();row['dialogue']=[{'line_id':'D1','delivery':'礼貌'},{'line_id':'D2'}]
  result=b.repair_dialogue({'shots':[row]},script,{},lines)
  self.assertEqual([(d['speaker'],d['text']) for d in result['shots'][0]['dialogue']],[('林岚','您好。'),('周明','请进。')])
  self.assertEqual(len(lines),2);self.assertEqual(script[lines[0]['start']:].splitlines()[0],'林岚：您好。')
 def test_ledger_detects_missing_duplicate_reordered_or_unknown_lines(self):
  script='林岚：您好。\n林岚：再见。';lines=b.script_dialogue_lines(script,[{'type':'角色','name':'林岚'}])
  for ids in (['D1'],['D2','D1'],['D1','D1'],['D9']):
   with self.subTest(ids=ids):
    row=self.row();row['dialogue']=[{'line_id':i} for i in ids]
    with self.assertRaises(ValueError):b.repair_dialogue({'shots':[row]},script,{},lines)
 def test_dialogue_schema_selects_source_ids_instead_of_retyping(self):
  schema=b.output_schema('planning',[],True,[{'id':'D1'}]);fields=schema['properties']['shots']['items']['properties']['dialogue']['items']['properties']
  self.assertEqual(fields['line_id']['enum'],['D1']);self.assertNotIn('text',fields);self.assertNotIn('speaker',fields)
 def test_narration_on_next_line_can_support_silent_action(self):
  row=self.row();row['dialogue']=[{'speaker':'林岚','text':'（不说话）'}]
  result=b.repair_dialogue({'shots':[row]},'林岚看一眼空袋。\n\n不说话。',{})
  self.assertEqual(result['shots'][0]['dialogue'],[])
 def test_duplicate_dialogue_keeps_unique_verbatim_owner(self):
  script='林岚：您好。';lines=b.script_dialogue_lines(script,[{'type':'角色','name':'林岚'}]);task={}
  first=dict(self.row(),title='反应',description='对方安静等候。',dialogue=[{'line_id':'D1'}]);last=dict(self.row(),title='问候',description='林岚说“您好。”',dialogue=[{'line_id':'D1'}])
  obj=b.repair_dialogue({'shots':[first,last]},script,task,lines)
  self.assertEqual(obj['shots'][0]['dialogue'],[]);self.assertEqual(obj['shots'][1]['dialogue'][0]['text'],'您好。');self.assertEqual(task['storyboard_repairs'][0]['kept_title'],'问候')
 def test_ambiguous_duplicate_is_not_guessed_and_error_names_only_problem(self):
  script='林岚：您好。';lines=b.script_dialogue_lines(script,[{'type':'角色','name':'林岚'}]);row=dict(self.row(),description='站立',dialogue=[{'line_id':'D1'}])
  with self.assertRaisesRegex(ValueError,'重复 D1'):b.repair_dialogue({'shots':[row,copy.deepcopy(row)]},script,{},lines)
 def test_collective_speaker_uses_explicit_members_and_preserves_old_ids(self):
  script='林岚、周明同时抬头。\n\n两人：又来啦？！\n林岚：再见。';assets=[{'type':'角色','name':'林岚'},{'type':'角色','name':'周明'}]
  old=b.script_dialogue_lines(script,assets);new=b.script_dialogue_lines(script,assets,True)
  self.assertEqual(old[0]['text'],'再见。');self.assertEqual(new[0]['members'],['林岚','周明']);self.assertEqual(new[0]['text'],'又来啦？！')
  obj=b.repair_dialogue({'shots':[dict(self.row(),dialogue=[{'line_id':'D1'},{'line_id':'D2'}])]},script,{},new)
  self.assertEqual(obj['shots'][0]['dialogue'][0]['members'],['林岚','周明'])
 def test_resume_prefix_is_revalidated_and_skips_model_for_completed_range(self):
  p=self.prepare();script='林岚：您好。\n'*300;spans=b.planning_segments(script);first={'start':0,'end':spans[0][1],'analysis':'saved','shots':[self.row()]};task={'model':'local','storyboard_seed_parts':[first]}
  context={'script':script,'assets':m.script_reference_context(p)}
  with patch.object(self.q,'text_request',return_value=self.response({'shots':[self.row()]})) as request:result=b.plan_in_parts(m.AppContext(),task,context,'instructions')
  self.assertEqual(task['storyboard_resumed_segments'],1);self.assertEqual(request.call_count,len(spans)-1);self.assertEqual(len(result['shots']),len(spans))
  payload=json.loads(request.call_args_list[0].args[0]['messages'][1]['content']);self.assertEqual(payload['planning_scope']['start'],first['end'])
 def test_checkpoint_requires_identical_source_assets_and_settings(self):
  p=self.prepare();skill=m.storyboard_skill_bundle(p);job={'id':m.uid(),'created':1,'kind':'text','operation':'generate_storyboard','status':'failed','snapshot':copy.deepcopy(p),'storyboard_skill':{k:skill[k] for k in ('planning_format','performance_format','prompt_language')},'storyboard_planning_parts':[{'start':0,'end':len(p['script']),'analysis':'saved','shots':[self.row()]}]};m.job_save(self.pid,job)
  self.assertEqual(self.q.storyboard_checkpoint(self.pid,p,skill)['storyboard_resume_from'],job['id'])
  changed=copy.deepcopy(p);changed['script']+='改动';self.assertEqual(self.q.storyboard_checkpoint(self.pid,changed,skill),{})
  changed=copy.deepcopy(p);changed['assets'][0]['prompt']='改动';self.assertEqual(self.q.storyboard_checkpoint(self.pid,changed,skill),{})
  self.assertNotIn('storyboard_seed_parts',self.q.public(self.pid,{'storyboard_seed_parts':[{}]}))
 def test_natural_performance_repairs_directions_without_touching_dialogue(self):
  task={};text='The three people remain still. He says <d>[English] Do not move or react.</d> Then they do not move or react.'
  fixed=b.normalize_performance(text,task)
  self.assertIn('subtle breathing',fixed);self.assertIn('<d>[English] Do not move or react.</d>',fixed);self.assertNotIn('people remain still',fixed)
  self.assertEqual(b.normalize_performance(text,{},allow_freeze=True),text)
  self.assertIn('自然呼吸',b.normalize_performance('三人保持不动。',{}))
 def test_chinese_and_english_prompt_preferences_leave_source_dialogue_unchanged(self):
  p=self.prepare();p['prompt_language']='zh';skill=m.storyboard_skill_bundle(p)
  self.assertEqual(skill['prompt_language'],'zh');p['prompt_language']='en';self.assertEqual(m.storyboard_skill_bundle(p)['prompt_language'],'en')
  shot=self.planned(p)[0]['shots'][0];shot['prompt_language']='zh'
  entry={'summary':'柜员问候','detailed_description':'[Shot 1] @林岚·日常 在 @客厅 走入画面，抬眼看向门口，手自然放下。 {{dialogue:0}}','overall_soundscape':'室内脚步声。','non_diegetic_music':'N/A'}
  text=b.assemble_h3(m.AppContext(),p,shot,entry,'reference');text=b.render_dialogue(m.AppContext(),p,shot,text,'reference')
  b.validate(m.AppContext(),p,shot,text,'reference');self.assertIn('<d>[Chinese] 您好。</d>',text);self.assertIn('为参考角色',text)
  shot['prompt_language']='en'
  with self.assertRaisesRegex(ValueError,'英文'):b.validate(m.AppContext(),p,shot,text,'reference')
 def test_language_setting_is_saved_validated_and_invalidates_checkpoint(self):
  p=self.prepare();m.merge_save(p,{'prompt_language':'en'});self.assertEqual(p['prompt_language'],'en')
  with self.assertRaisesRegex(ValueError,'语言'):m.merge_save(p,{'prompt_language':'other'})
  skill=m.storyboard_skill_bundle(p);job={'id':m.uid(),'created':1,'kind':'text','operation':'generate_storyboard','status':'failed','snapshot':copy.deepcopy(p),'storyboard_skill':{k:skill[k] for k in ('planning_format','performance_format','prompt_language')},'storyboard_planning_parts':[{'start':0,'end':len(p['script']),'shots':[self.row()]}]};m.job_save(self.pid,job)
  self.assertTrue(self.q.storyboard_checkpoint(self.pid,p,skill));p['prompt_language']='zh'
  self.assertFalse(self.q.storyboard_checkpoint(self.pid,p,m.storyboard_skill_bundle(p)))
 def test_source_speaker_binding_preserves_selected_looks_and_only_adds_exact_roles(self):
  p=self.prepare();p['assets'].append({'id':'other','name':'周明','type':'角色','default_look_id':'suit','looks':[{'id':'suit'}]})
  row=self.row();row['dialogue']+=[{'speaker':'周明','text':'您好。'}];task={}
  bound=b.bind_dialogue_roles(p,row,task)
  self.assertEqual(row['asset_ids'],['person','room']);self.assertEqual(bound['asset_ids'],['person','room','other']);self.assertEqual(bound['character_looks'],{'person':'look','other':'suit'})
  self.assertEqual(task['storyboard_repairs'][0]['action'],'bind_source_speaker')
  self.assertEqual(b.bind_dialogue_roles(p,bound,{})['asset_ids'],bound['asset_ids'])
  p['assets'].append(dict(p['assets'][-1],id='duplicate'))
  with self.assertRaisesRegex(ValueError,'不唯一'):b.bind_dialogue_roles(p,row,{})
 def test_stable_reference_protocol_keeps_numbered_official_examples_out_of_model_request(self):
  p=self.prepare();task=self.fresh_task(p);task['storyboard_skill'].update(h3_dialogue_events=True,h3_event_timing=True,h3_stable_refs=True)
  entry={'index':0,'summary':'Greeting','events':[{'visual':'@林岚·日常 enters @客厅.','dialogue_indices':[0],'cut_at':None}],'overall_soundscape':'Room tone.','non_diegetic_music':'N/A'}
  wrong=copy.deepcopy(entry);wrong['events'][0]['visual']='<Subject 6> enters the room.'
  with patch.object(b,'plan_in_parts',return_value={'shots':[self.row()]}),patch.object(self.q,'text_request',side_effect=[self.response({'prompts':[wrong]}),self.response({'prompts':[entry]})]) as request:result=m.plan_storyboard(p,task)
  self.assertEqual(request.call_count,2);self.assertIn('@林岚·日常',result['shots'][0]['video_prompt'])
  first=request.call_args_list[0].args[0];self.assertNotIn('Full-Reference Mode',first['messages'][0]['content']);payload=json.loads(first['messages'][1]['content'])
  self.assertNotIn('subject',payload['shots'][0]['reference_slots'][0]);self.assertNotIn('picture',payload['shots'][0]['reference_slots'][0])
  self.assertNotIn('previous_prompts',json.loads(request.call_args_list[1].args[0]['messages'][1]['content']))
 def test_event_continuation_does_not_create_fake_cut(self):
  obj={'prompts':[{'events':[{'visual':'[Shot 1] A man lowers his hand.','dialogue_indices':[0],'cut_at':None},{'visual':'[Shot 1] The scene gradually fades to black.','dialogue_indices':[],'cut_at':None}]}]}
  main=b.compile_dialogue_events(obj,'h3-reference',1,6)['prompts'][0]['detailed_description']
  self.assertEqual(len(b.cut_markers(main)),1);self.assertIn('fades to black',main);self.assertNotIn('At ',main)
 def test_event_cut_time_is_formatted_and_invalid_times_are_not_guessed(self):
  def obj(t):return {'prompts':[{'events':[{'visual':'A static wide shot.','dialogue_indices':[],'cut_at':None},{'visual':'Close-up of her reaction.','dialogue_indices':[],'cut_at':t}]}]}
  main=b.compile_dialogue_events(obj(2.125),'h3-base',0,6)['prompts'][0]['integrated_multimodal_description'];self.assertIn('[Shot 2] At 00:02.125, Close-up',main)
  for t in (True,-1,0,6,7,float('nan'),.0001):
   with self.subTest(t=t),self.assertRaises(ValueError):b.compile_dialogue_events(obj(t),'h3-base',0,6)
  bad=obj(2);bad['prompts'][0]['events'][0]['cut_at']=1
  with self.assertRaises(ValueError):b.compile_dialogue_events(bad,'h3-base',0,6)
 def test_structured_cut_pipeline_preserves_dialogue_and_validates_real_cut(self):
  p=self.prepare();task=self.fresh_task(p);task['storyboard_skill'].update(h3_dialogue_events=True,h3_event_timing=True)
  row=self.row();row['duration']=6
  entry={'index':0,'summary':'Greeting','events':[{'visual':'@林岚·日常 enters @客厅.','dialogue_indices':[0],'cut_at':None},{'visual':'Close-up of her smiling face.','dialogue_indices':[],'cut_at':3.25}],'overall_soundscape':'Room tone.','non_diegetic_music':'N/A'}
  with patch.object(b,'plan_in_parts',return_value={'shots':[row]}),patch.object(self.q,'text_request',return_value=self.response({'prompts':[entry]})) as request:result=m.plan_storyboard(p,task)
  self.assertIn('[Shot 2] At 00:03.250,',result['shots'][0]['video_prompt']);self.assertIn('<d>[Chinese] 您好。</d>',result['shots'][0]['video_prompt'])
  event=request.call_args.args[0]['response_format']['json_schema']['schema']['properties']['prompts']['items']['properties']['events']['items'];self.assertIn('cut_at',event['required'])
 def test_event_pipeline_inserts_exact_dialogue_without_model_copying_it(self):
  p=self.prepare();task=self.fresh_task(p);task['storyboard_skill']['h3_dialogue_events']=True
  entry={'index':0,'summary':'Greeting','events':[{'visual':'[Shot 1] @林岚·日常 enters @客厅.','dialogue_indices':[0]}],'overall_soundscape':'Room tone.','non_diegetic_music':'N/A'}
  with patch.object(b,'plan_in_parts',return_value={'shots':[self.row()]}),patch.object(self.q,'text_request',return_value=self.response({'prompts':[entry]})) as request:result=m.plan_storyboard(p,task)
  prompt=result['shots'][0]['video_prompt'];self.assertIn('@林岚·日常 (S1) says: <d>[Chinese] 您好。</d>',prompt)
  schema=request.call_args.args[0]['response_format']['json_schema']['schema']['properties']['prompts']['items'];self.assertIn('events',schema['required']);self.assertNotIn('detailed_description',schema['properties'])
  self.assertEqual(len(task['storyboard_prompt_parts']),1)
 def test_event_missing_line_repairs_only_current_fragment(self):
  task={'model':'local'};base={'index':3,'summary':'Greeting','overall_soundscape':'Room tone.','non_diegetic_music':'N/A'}
  bad={**base,'events':[{'visual':'[Shot 1] A static close-up.','dialogue_indices':[]}]};good={**base,'events':[{'visual':'[Shot 1] A static close-up.','dialogue_indices':[0]}]}
  with patch.object(self.q,'text_request',side_effect=[self.response({'prompts':[bad]}),self.response({'prompts':[good]})]) as request:
   result=b.ask(m.AppContext(),task,[],output_kind='h3-reference',expected_indices=[3],dialogue_count=1)
  self.assertEqual(request.call_count,2);self.assertIn('{{dialogue:0}}',result['prompts'][0]['detailed_description'])
 def test_events_reject_duplicate_unknown_reordered_and_model_speech_syntax(self):
  for indices in ([0,0],[1,0],[True],[2]):
   with self.subTest(indices=indices),self.assertRaises(ValueError):b.compile_dialogue_events({'prompts':[{'events':[{'visual':'Still.','dialogue_indices':indices}]}]},'h3-base',2)
  with self.assertRaises(ValueError):b.compile_dialogue_events({'prompts':[{'events':[{'visual':'<d>[Chinese] 改写</d>','dialogue_indices':[0]}]}]},'h3-base',1)
  result=b.compile_dialogue_events({'prompts':[{'events':[{'visual':'[Shot 1] Empty room.','dialogue_indices':[]}]}]},'h3-base',0)
  self.assertIn('Empty room.',result['prompts'][0]['integrated_multimodal_description'])
 def test_length_retry_is_bounded_and_schema_closed(self):
  task={'model':'local'};bad={'choices':[{'finish_reason':'length','message':{'content':'{"prompts":['}}]}
  good=self.response({'prompts':[{'index':2,'summary':'OK','detailed_description':'[Shot 1] Still.','overall_soundscape':'Quiet','non_diegetic_music':'N/A'}]})
  with patch.object(self.q,'text_request',side_effect=[bad,good]) as request:
   result=b.ask(m.AppContext(),task,[],output_kind='h3-reference',expected_indices=[2],field_limits={'summary':900})
  self.assertEqual(result['prompts'][0]['index'],2);self.assertEqual(request.call_count,2);self.assertEqual(task['storyboard_length_retries'],1)
  schema=request.call_args.args[0]['response_format']['json_schema']['schema'];self.assertFalse(schema['additionalProperties']);self.assertEqual(schema['properties']['prompts']['items']['properties']['summary']['maxLength'],900)
  with patch.object(self.q,'text_request',return_value=bad) as request:
   with self.assertRaisesRegex(b.OutputLengthError,'第3镜'):b.ask(m.AppContext(),{'model':'local'},[],output_kind='h3-reference',expected_indices=[2])
  self.assertEqual(request.call_count,2)
 def test_complete_json_at_provider_length_limit_is_preserved(self):
  response=self.response({'prompts':[{'index':0,'video_prompt':self.prompt()}]});response['choices'][0]['finish_reason']='length'
  with patch.object(self.q,'text_request',return_value=response) as request:result=b.ask(m.AppContext(),{'model':'local'},[],output_kind='prompts')
  self.assertEqual(request.call_count,1);self.assertEqual(result['prompts'][0]['video_prompt'],self.prompt())
 def test_validated_h3_checkpoint_skips_generation_and_rejects_changed_plan(self):
  p=self.prepare();task=self.fresh_task(p);row=self.row()
  with patch.object(b,'plan_in_parts',return_value={'shots':[row]}),patch.object(self.q,'text_request',return_value=self.response({'prompts':[dict(index=0,**{k:v for k,v in b.sections(self.prompt(),True).items() if k in ('summary','detailed_description','overall_soundscape','non_diegetic_music')})]})):
   m.plan_storyboard(p,task)
  saved=task['storyboard_prompt_parts'];self.assertEqual(len(saved),1)
  resumed=self.fresh_task(p);resumed['storyboard_seed_prompts']=saved
  with patch.object(b,'plan_in_parts',return_value={'shots':[row]}),patch.object(self.q,'text_request') as request:result=m.plan_storyboard(p,resumed)
  request.assert_not_called();self.assertEqual(resumed['storyboard_resumed_prompts'],1);self.assertIn('您好。',result['shots'][0]['video_prompt'])
  changed=copy.deepcopy(result['shots']);changed[0]['description']='改变动作'
  self.assertEqual(b.resume_h3_prompts(m.AppContext(),p,{'storyboard_seed_prompts':saved},changed,'reference'),0)
  public=self.q.public(self.pid,{'storyboard_seed_prompts':saved,'storyboard_prompt_parts':saved})
  self.assertNotIn('storyboard_prompt_parts',public);self.assertNotIn('storyboard_seed_prompts',public)
 def test_collective_render_is_one_utterance_with_explicit_participants(self):
  p=self.prepare();shot=self.row();shot['dialogue']=[{'speaker':'林岚、周明','members':['林岚','周明'],'text':'您好。'}];entry={'summary':'Greeting','detailed_description':'[Shot 1] {{dialogue:0}}','overall_soundscape':'Room tone.','non_diegetic_music':'N/A'}
  text=b.assemble_h3(m.AppContext(),p,shot,entry,'reference');text=b.render_dialogue(m.AppContext(),p,shot,text,'reference');b.validate(m.AppContext(),p,shot,text,'reference')
  self.assertIn('speak together in unison',text);self.assertEqual(text.count('<d>'),1);self.assertIn('周明',text)
 def test_batch_global_labels_are_local_per_fragment(self):
  task={};text=self.prompt().replace('[Shot 1]','[Shot 9]');fixed=b.normalize_cut_labels(text,True,task,'标题')
  self.assertIn('[Shot 1]',fixed);self.assertNotIn('[Shot 9]',fixed);self.assertEqual(task['storyboard_repairs'][0]['cuts'],1)
 def test_internal_renumbering_preserves_cut_times_and_spoken_text(self):
  text=self.prompt().replace('[Shot 1]','[Shot 7]').replace('overall_soundscape:','[Shot 12] At 00:02.500, The camera shows a reaction.\noverall_soundscape:')
  fixed=b.normalize_cut_labels(text,True);self.assertIn('[Shot 2] At 00:02.500,',fixed);self.assertIn('<d>[Chinese] 您好。</d>',fixed)
  self.assertEqual(b.normalize_cut_labels(fixed,True),fixed)
 def test_quoted_or_spoken_shot_labels_are_content(self):
  text=self.prompt().replace('[Chinese] 您好。','[Chinese] 请读[Shot 77]。').replace('A static medium shot','A sign reads "[Shot 88]". A static medium shot').replace('[Shot 1]','[Shot 5]')
  fixed=b.normalize_cut_labels(text,True);self.assertIn('<d>[Chinese] 请读[Shot 77]。</d>',fixed);self.assertIn('"[Shot 88]"',fixed)
  main=b.sections(fixed,True)['detailed_description'];self.assertEqual(len(b.cut_markers(main)),1)
 def test_number_normalization_does_not_hide_invalid_cut_timing(self):
  p=self.prepare();shot=self.planned(p)[0]['shots'][0];text=self.prompt().replace('[Shot 1]','[Shot 8]').replace('overall_soundscape:','[Shot 9] At 00:20.000, Cut.\noverall_soundscape:')
  fixed=b.normalize_cut_labels(text,True)
  with self.assertRaisesRegex(ValueError,'切点'):b.validate(m.AppContext(),p,shot,fixed,'reference')
 def test_missing_initial_cut_marker_is_added_without_changing_body(self):
  original=self.prompt().replace('[Shot 1] ','');task={};fixed=b.normalize_cut_labels(original,True,task,'开场')
  self.assertIn('detailed_description:\n[Shot 1] A static',fixed);self.assertEqual(fixed.replace('[Shot 1] ',''),original)
  self.assertEqual(task['storyboard_repairs'][0]['action'],'add_initial_cut_label');self.assertEqual(b.normalize_cut_labels(fixed,True),fixed)
 def test_missing_markers_with_explicit_cut_time_are_not_guessed(self):
  text=self.prompt().replace('[Shot 1] ','At 00:02.500, ')
  with self.assertRaisesRegex(ValueError,'不能自动推断'):b.normalize_cut_labels(text,True)
 def test_one_fragment_requests_cannot_share_numeric_reference_tables(self):
  p=self.prepare();p['script']='林岚：您好。\n林岚：您好。';task=self.fresh_task(p)
  rows=[self.unified_row(),self.unified_row()];rows[0]['dialogue']=[{'line_id':'D1'}];rows[1]['dialogue']=[{'line_id':'D2'}]
  entry={k:v for k,v in b.sections(self.prompt(),True).items() if k in ('summary','detailed_description','overall_soundscape','non_diegetic_music')}
  responses=[self.response({'shots':rows}),self.response({'prompts':[dict(index=0,**entry)]}),self.response({'prompts':[dict(index=1,**entry)]})]
  with patch.object(self.q,'text_request',side_effect=responses) as request:result=m.plan_storyboard(p,task)
  self.assertEqual(len(result['shots']),2);self.assertEqual(request.call_count,3)
  for call in request.call_args_list[1:]:
   payload=json.loads(call.args[0]['messages'][1]['content']);self.assertEqual(len(payload['shots']),1);self.assertNotIn('script',payload)
   self.assertEqual({a['id'] for a in payload['assets']},set(payload['shots'][0]['asset_ids']))
   shape=call.args[0]['response_format']['json_schema']['schema']['properties']['prompts'];self.assertEqual(shape['minItems'],1);self.assertEqual(shape['maxItems'],1);self.assertEqual(shape['items']['properties']['index']['enum'],[payload['shots'][0]['index']])
if __name__=='__main__':unittest.main()
