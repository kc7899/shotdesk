import copy,io,json,unittest
from unittest.mock import patch,Mock
import storyboard as b
import source_storyboard as s
import test_queue
import test_storyboard_official as fixtures

# Legacy scheme tests: pin the pre-h3-structured-v2 default so they keep exercising the old pipeline.
import storyboard as _legacy_scheme_storyboard
_legacy_scheme_default=_legacy_scheme_storyboard.DEFAULT_SCHEME
def setUpModule():_legacy_scheme_storyboard.DEFAULT_SCHEME='huobao-native-v1'
def tearDownModule():_legacy_scheme_storyboard.DEFAULT_SCHEME=_legacy_scheme_default

m=test_queue.m

class SourceStoryboard(unittest.TestCase):
 def setUp(self):
  test_queue.QueueContracts.setUp(self)
  def frozen(p):
   raw=(m.ROOT/'docs/skills/shotdesk-storyboard/references/source-v1.md').read_text()
   with patch.object(m,'prompt_skill_bundle',return_value={'text':raw,'version':'2026-10-30.1'}):return b.skill_bundle(m.AppContext(),p)
  patcher=patch.object(m,'storyboard_skill_bundle',side_effect=frozen);patcher.start();self.addCleanup(patcher.stop)
 tearDown=test_queue.QueueContracts.tearDown
 prepare=fixtures.OfficialStoryboard.prepare
 def task(self,p,stage='all'):
  skill=m.storyboard_skill_bundle(p)
  return {'id':m.uid(),'model':'local','storyboard_stage':stage,'storyboard_skill':{k:v for k,v in skill.items() if k not in ('text','official_text')},'storyboard_skill_text':skill['text']}
 def run_plan(self,p,response=None):
  task=self.task(p)
  with patch.object(self.q,'text_request',return_value=response or {'choices':[{'message':{'content':'{"recipes":[]}'}}]}):r=m.plan_storyboard(p,task)
  return r,task
 def test_frozen_skill_selects_source_owned_path(self):
  p=self.prepare();skill=m.storyboard_skill_bundle(p)
  self.assertTrue(skill['source_owned_events']);self.assertEqual(skill['version'],'2026-10-30.1')
 def test_source_actions_are_not_rewritten_by_free_model_prose(self):
  p=self.prepare();p['script']='林岚把主机搬向旅行袋。袋口太小，放不进去。\n她换个方向。\n还是不行。\n林岚：先放椅子上。\n林岚把主机放到椅子上。\n【声音】一声电脑错误提示音。\n'
  before=copy.deepcopy(p)
  response={'choices':[{'message':{'content':json.dumps({'recipes':[{'unit_id':'U1','title':'放不进去','framing':'中景','movement':'固定机位','focus_id':'person','looks':{'person':'look'},'visual':'已经塞进袋子，只是拉链关不上。'}]},ensure_ascii=False)}}]}
  r,t=self.run_plan(p,response);self.assertEqual(p,before)
  text='\n'.join(x['video_prompt'] for x in r['shots']);self.assertIn('袋口太小，放不进去',text);self.assertIn('还是不行',text);self.assertNotIn('拉链关不上',text);self.assertIn('一声电脑错误提示音',text)
  self.assertEqual([beat['text'] for shot in r['shots'] for beat in shot['source_contract']['beats']], [beat['text'] for beat in s.ledger(m.AppContext(),p)['events']])
 def test_caption_and_stage_direction_are_not_spoken(self):
  p=self.prepare();p['script']='胸牌：\n风险处置专员：林岚\n林岚轻轻按住文件夹：先听。\n林岚：（点头）\n林岚：您好。\n'
  book=s.ledger(m.AppContext(),p);self.assertEqual([e['text'] for e in book['events'] if e['kind']=='dialogue'],['您好。'])
  self.assertIn('林岚轻轻按住文件夹：先听。',[e['text'] for e in book['events']])
 def test_scene_boundaries_and_local_freeze_do_not_leak(self):
  p=self.prepare();p['script']='场景 1\n客厅\n林岚戴着面罩。\n林岚：您好。\n场景 2\n客厅\n【次日】\n林岚摘下面罩。\n林岚：再见。\n【全景定格。】\n【声音】错误提示音。\n'
  r,t=self.run_plan(p);self.assertEqual(len(r['shots']),2)
  self.assertNotIn('摘下',r['shots'][0]['video_prompt']);self.assertIn('摘下',r['shots'][1]['video_prompt'])
  for shot in r['shots']:self.assertEqual(len({e['scene_id'] for e in shot['source_contract']['beats']}),1);self.assertIn('room',shot['asset_ids'])
  self.assertEqual([e['kind'] for e in r['shots'][-1]['source_contract']['beats']][-2:],['transition','sound'])
  self.assertNotIn('定格',[e['text'] for e in r['shots'][0]['source_contract']['beats']])
 def test_duration_is_budgeted_before_compiling_and_idempotent(self):
  p=self.prepare();p['script']='林岚：'+('您好'*30)+'。\n【停顿2秒】\n林岚：再见。\n'
  r,t=self.run_plan(p)
  for shot in r['shots']:
   first=copy.deepcopy(shot);s.compile_shot(m.AppContext(),p,shot);self.assertEqual(shot,first)
   for event in shot['source_timeline']:
    beat=next(e for e in shot['source_contract']['beats'] if e['id']==event['beat_id'])
    if beat['kind']=='dialogue':self.assertGreaterEqual(event['end']-event['start']+.001,s.speech_seconds(beat['text']))
   self.assertGreater(shot['duration'],shot['source_timeline'][-1]['end'])
  self.assertGreater(r['shots'][0]['duration'],10)
 def test_reference_labels_compile_actual_picture_order(self):
  p=self.prepare();r,t=self.run_plan(p);shot=r['shots'][0]
  text,bindings=m.compile_shot_prompt(p,shot,'video',[{'asset_id':'room','url':'/room.png'},{'asset_id':'person','look_id':'look','url':'/look.png'}])
  self.assertIn('<Subject 2>',text);self.assertIn('Source: <Picture 2>',text);self.assertNotIn('@',text)
  self.assertEqual(shot['character_looks'],{'person':'look'});self.assertTrue(b.check_existing(m.AppContext(),dict(p,shots=r['shots']))['ok'])
 def test_bad_recipes_fall_back_without_retry_or_story_loss(self):
  p=self.prepare();task=self.task(p)
  with patch.object(self.q,'text_request',return_value={'choices':[{'finish_reason':'length','message':{'content':'{"recipes":['}}]}) as call:r=m.plan_storyboard(p,task)
  self.assertEqual(call.call_count,1);self.assertEqual(r['shots'][0]['dialogue'],[{'speaker':'林岚','text':'您好。'}]);self.assertTrue(task['storyboard_quality_notes'])
 def test_wrong_look_focus_and_future_continuity_are_ignored(self):
  p=self.prepare();p['assets'].append({'id':'other','name':'别人','type':'角色','looks':[{'id':'other-look'}]})
  response={'choices':[{'message':{'content':json.dumps({'recipes':[{'unit_id':'U1','framing':'中景','movement':'固定机位','focus_id':'other','looks':{'person':'other-look','other':'other-look'},'continuity_ids':['B999','B2']}]})}}]}
  r,t=self.run_plan(p,response);shot=r['shots'][0];self.assertEqual(shot['character_looks'],{'person':'look'});self.assertNotIn('other',shot['asset_ids']);self.assertEqual(shot['source_contract']['prior_facts'],[])
 def test_prompt_only_uses_same_contract_without_model_or_media_change(self):
  p=self.prepare();r,t=self.run_plan(p);p['shots']=r['shots'];p['shots'][0].update(versions=[{'id':'old','kind':'video','url':'/old.mp4'}],video='/old.mp4');before=copy.deepcopy(p);task=self.task(p,'prompts');task['storyboard_shot_ids']=[p['shots'][0]['id']]
  with patch.object(self.q,'text_request',side_effect=AssertionError('no model needed')):r=b.write_existing(m.AppContext(),p,task)
  self.assertEqual(p,before);self.assertEqual(r['shots'],p['shots'])
 def test_edited_source_plan_is_not_silently_replaced_by_contract(self):
  p=self.prepare();r,t=self.run_plan(p);p['shots']=r['shots'];p['shots'][0]['description']='人工修改动作';task=self.task(p,'prompts');task['storyboard_shot_ids']=[p['shots'][0]['id']]
  with patch.object(b,'write_existing',return_value={'shots':p['shots']}) as legacy:r=s.write_existing(m.AppContext(),p,task)
  self.assertFalse(legacy.call_args.args[2]['storyboard_skill'].get('source_owned_events'));self.assertEqual(r['shots'][0]['description'],'人工修改动作')
 def test_text_and_first_frame_modes_have_no_fake_asset_tags(self):
  for mode in ('text','first_frame'):
   p=self.prepare('first_frame');p['video_mode']=mode;r,t=self.run_plan(p)
   shot=r['shots'][0];self.assertNotIn('@',shot['video_prompt']);b.validate(m.AppContext(),p,shot,shot['video_prompt'],mode)
 def test_english_source_keeps_english_wrappers(self):
  p=self.prepare();p['script']='林岚: Hello.\nThe door opens.\n';r,t=self.run_plan(p)
  shot=r['shots'][0];self.assertEqual(shot['prompt_language'],'en');self.assertIn('The door opens.',shot['video_prompt']);b.validate(m.AppContext(),p,shot,shot['video_prompt'],'reference')
 def test_missing_asset_catalog_still_preserves_named_speech(self):
  p=self.prepare();p['assets']=[];p['script']='甲：你好。\n乙：再见。\n';r,t=self.run_plan(p)
  self.assertEqual([(d['speaker'],d['text']) for shot in r['shots'] for d in shot['dialogue']],[('甲','你好。'),('乙','再见。')])
 def test_transport_failure_and_cancel_do_not_masquerade_as_completed(self):
  from task_queue import Cancelled
  p=self.prepare()
  for error in (ValueError('503'),Cancelled('stop')):
   with patch.object(self.q,'text_request',side_effect=error),self.assertRaises(type(error)):m.plan_storyboard(p,self.task(p))
 def test_short_handles_decode_looks_and_lock_the_scene_selection(self):
  p=self.prepare();p['assets'][0]['looks'].append({'id':'second','name':'另一造型'})
  p['script']='林岚：'+('你好'*25)+'。\n林岚：再见。\n'
  response={'choices':[{'message':{'content':json.dumps({'recipes':[{'unit_id':'U1','title':'第一镜','framing':'中景','movement':'固定机位','focus_id':'R1','looks':{'R1':'L2'}},{'unit_id':'U2','title':'第二镜','framing':'中景','movement':'固定机位','focus_id':'R1','looks':{'R1':'L1'}}]})}}]}
  r,t=self.run_plan(p,response);self.assertGreater(len(r['shots']),1)
  for shot in r['shots']:self.assertEqual(shot['character_looks']['person'],'second')
 def test_action_duration_note_is_not_a_silent_pause(self):
  p=self.prepare();p['script']='林岚把主机放向袋口。\n她换个方向。\n还是不行。\n【保留完整动作，约4秒。】\n林岚：放椅子上。\n'
  book=s.ledger(m.AppContext(),p);note=next(e for e in book['events'] if e['kind']=='timing');self.assertEqual(note['seconds'],0);self.assertGreaterEqual(sum(e['seconds'] for e in book['events'] if e['kind']=='action'),3.99)
  r,t=self.run_plan(p);text='\n'.join(x['video_prompt'] for x in r['shots']);self.assertIn('保留完整动作，约4秒',text);self.assertNotIn('原文动作时长说明',text);self.assertNotIn('按原文保留停顿',text)
 def test_prop_aliases_do_not_replace_characters_inside_unrelated_words(self):
  assets=[{'id':'notice','name':'招聘启事','type':'道具'},{'id':'forms','name':'文件夹与表格','type':'道具'},{'id':'gun','name':'道具枪','type':'道具'}]
  aliases=s.prop_aliases(assets);self.assertNotIn('事',aliases);self.assertNotIn('格',aliases);self.assertEqual(aliases['枪'],'gun')
 def test_unhashable_camera_choices_do_not_break_completion(self):
  p=self.prepare();response={'choices':[{'message':{'content':json.dumps({'recipes':[{'unit_id':[]},{'unit_id':'U1','focus_id':[],'looks':[]}]})}}]}
  r,t=self.run_plan(p,response);self.assertTrue(r['shots'][0]['video_prompt'])
 def test_explicit_complete_action_group_is_not_split_by_target_duration(self):
  p=self.prepare();p['script']='林岚抱主机走向袋口，放不进去。\n她换个方向。\n还是不行。\n【保留完整动作，约4秒。】\n'
  book=s.ledger(m.AppContext(),p);groups=s.units(book,target=1);self.assertEqual(len(groups),1);self.assertGreaterEqual(groups[0]['duration'],4)
 def test_contextual_prop_reference_follows_the_source_object(self):
  p=self.prepare();p['assets'].append({'id':'bag','name':'旅行袋','type':'道具'})
  ids=s.resource_ids(p,{'beats':[{'text':'还是不行。','role_ids':['person']}]},{'location_id':'room'},[{'text':'林岚抱主机走向旅行袋。','role_ids':['person']}])
  self.assertIn('bag',ids);self.assertIn('room',ids)
 def test_one_click_worker_commits_source_contract_and_coverage_to_temporary_project(self):
  p=self.prepare()
  with patch('task_queue.threading.Thread'):job=self.q.start_storyboard(self.pid)
  stored=json.loads(m.job_path(self.pid,job['id']).read_text())
  with patch.object(self.q,'text_request',return_value={'choices':[{'message':{'content':'{"recipes":[]}'}}]}):self.q.worker(self.pid,stored)
  after=m.load(self.pid);done=json.loads(m.job_path(self.pid,job['id']).read_text())
  self.assertEqual(done['status'],'completed');self.assertEqual(after['script'],p['script']);self.assertEqual(after['assets'],p['assets']);self.assertIn('source_contract',after['shots'][0]);self.assertEqual(done['storyboard_source_coverage']['dialogue'],1)
 def test_video_prompt_contains_content_without_internal_instructions(self):
  p=self.prepare();r,t=self.run_plan(p);text=r['shots'][0]['video_prompt']
  for phrase in ('原文动作','前情已发生','原文事件','当前事件优先','本场原文设定','只执行以下','固定机位下保留','Source event:'):
   self.assertNotIn(phrase,text)
  self.assertIn('<d>[Chinese] 您好。</d>',text);self.assertIn('走进',text)
 def test_old_checkpoint_not_reused_for_new_source_protocol(self):
  p=self.prepare();skill=m.storyboard_skill_bundle(p);old=dict(skill);old.pop('source_owned_events');job={'id':m.uid(),'created':1,'kind':'text','operation':'generate_storyboard','status':'failed','snapshot':p,'storyboard_skill':old,'storyboard_planning_parts':[{'start':0,'end':len(p['script']),'shots':[]}]};m.job_save(self.pid,job)
  self.assertFalse(self.q.storyboard_checkpoint(self.pid,p,skill))

class TextStreamErrors(unittest.TestCase):
 def test_http_200_stream_error_is_not_an_empty_success(self):
  q=m.TaskQueue(m.AppContext());response=io.BytesIO(b'data: {"error":{"message":"invalid schema"}}\n\ndata: [DONE]\n');response.status=200;connection=Mock();connection.getresponse.return_value=response
  with patch('task_queue.http.client.HTTPConnection',return_value=connection),self.assertRaisesRegex(ValueError,'invalid schema'):q.text_request({}, {'id':'test'})
  connection.close.assert_called_once()
 def test_connection_with_no_content_or_finish_marker_is_not_success(self):
  q=m.TaskQueue(m.AppContext());response=io.BytesIO(b'data: [DONE]\n');response.status=200;connection=Mock();connection.getresponse.return_value=response
  with patch('task_queue.http.client.HTTPConnection',return_value=connection),self.assertRaisesRegex(ValueError,'未返回'):q.text_request({}, {'id':'test'})
