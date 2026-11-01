import copy,json,unittest
from unittest.mock import patch
import test_queue
import test_storyboard_official as fixtures
import storyboard as b
import source_storyboard as source
import coverage_director as d

# Legacy scheme tests: pin the pre-h3-structured-v2 default so they keep exercising the old pipeline.
import storyboard as _legacy_scheme_storyboard
_legacy_scheme_default=_legacy_scheme_storyboard.DEFAULT_SCHEME
def setUpModule():_legacy_scheme_storyboard.DEFAULT_SCHEME='huobao-native-v1'
def tearDownModule():_legacy_scheme_storyboard.DEFAULT_SCHEME=_legacy_scheme_default

m=test_queue.m

class CoverageDirector(unittest.TestCase):
 def setUp(self):
  test_queue.QueueContracts.setUp(self)
  original=m.storyboard_skill_bundle
  def frozen(p):
   raw=(m.ROOT/'docs/skills/shotdesk-storyboard/references/coverage-2026-10-30.4.md').read_text()
   with patch.object(m,'prompt_skill_bundle',return_value={'text':raw,'version':'2026-10-30.4'}):skill=b.skill_bundle(m.AppContext(),p)
   skill.pop('segment_director',None);skill['version']='2026-10-30.4';skill['text']=(m.ROOT/'docs/skills/shotdesk-storyboard/references/coverage-2026-10-30.4.md').read_text();return skill
  guard=patch.object(m,'storyboard_skill_bundle',side_effect=frozen);guard.start();self.addCleanup(guard.stop)
 tearDown=test_queue.QueueContracts.tearDown
 prepare=fixtures.OfficialStoryboard.prepare
 def project(self):
  p=self.prepare();p['assets'].append({'id':'man','name':'周明','type':'角色','prompt':'成年男子，短发，黑色外套。','image':'/man.png','looks':[{'id':'coat','name':'外套','prompt':'黑色外套','image':'/coat.png'}],'default_look_id':'coat'})
  p['script']='场景 1\n客厅\n林岚坐在房间左侧。\n周明站在右侧，面对林岚。\n林岚：您好。\n周明：你好。\n林岚：请坐。\n周明坐下。\n';p['prompt_language']='zh';return p
 def task(self):return {'id':m.uid(),'model':'local','storyboard_stage':'all','storyboard_skill':{'director_format':'coverage-v1'},'storyboard_skill_text':'摄影：明确站位与说话者。'}
 def response(self,body,job):
  payload=json.loads(body['messages'][1]['content'])
  if payload.get('phase')=='scene_blocking':
   chars=payload['characters'];cast={c['key']:{'appearance':c['identity'],'placement':'画面左侧，坐在椅子上。' if i==0 else '画面右侧，站立面对左侧。','side':'left' if i==0 else 'right','voice':'清亮女声' if i==0 else '低沉男声','present':True,'look':'L1','changes':[]} for i,c in enumerate(chars)}
   value={'space':'明亮客厅。','axis':'相机始终在交谈轴线同一侧。','cast':cast,'actors':{},'clips':[{'through':payload['events'][-1]['id'],'props':[]}]}
  elif 'actions' in payload:
   value={'actions':{e['id']:e.get('text',e.get('fact','动作。')) for e in payload['actions']}}
  elif payload.get('phase')=='film_coverage':
   value={'clips':{c['id']:{'title':'对话','shots':{cut['id']:{'view':'平视双人中景，'+('；'.join(k+' 位于左侧或右侧，彼此面对。' for k in cut['visible']))} for cut in c['cuts']}} for c in payload['clips']}}
  else:value={'issues':[]}
  return {'choices':[{'message':{'content':json.dumps(value,ensure_ascii=False)}}]}
 def run_plan(self,p):
  task=self.task()
  with patch.object(self.q,'text_request',side_effect=self.response):result=d.plan(m.AppContext(),p,task)
  return result,task
 def test_public_one_click_queue_worker_uses_director_and_commits_without_touching_assets(self):
  p=self.project();m.save(self.root/'project.json',p);p=m.load(self.pid);skill=m.storyboard_skill_bundle(p);self.assertEqual(skill['director_format'],'coverage-v1');self.assertEqual(skill['version'],'2026-10-30.4');self.assertNotIn('source_owned_events',skill)
  with patch.object(self.q,'enqueue',side_effect=lambda pid,j:j):job=self.q.start_storyboard(self.pid)
  with patch.object(self.q,'text_request',side_effect=self.response):self.q.worker(self.pid,job)
  self.assertEqual(json.loads(m.job_path(self.pid,job['id']).read_text())['status'],'completed');saved=m.load(self.pid);self.assertEqual(saved['assets'],p['assets']);self.assertEqual(saved['script'],p['script']);self.assertTrue(saved['shots']);self.assertTrue(all(s['director_plan']['version']=='coverage-v1' and s['video_prompt'] for s in saved['shots']))
 def test_user_edits_are_never_overwritten_by_stale_director_state(self):
  p=self.project();r,t=self.run_plan(p);shot=next(s for s in r['shots'] if s['dialogue']);shot['description']='人工修改的调度';shot['dialogue'][0]['text']='人工修改的台词';p['shots']=[shot];t['storyboard_shot_ids']=[shot['id']]
  with patch.object(b,'write_existing',side_effect=lambda api,p,t:{'shots':p['shots']}) as compatibility:out=d.write_existing(m.AppContext(),p,t)
  compatibility.assert_called_once();self.assertEqual(out['shots'][0]['description'],'人工修改的调度');self.assertEqual(out['shots'][0]['dialogue'][0]['text'],'人工修改的台词')
 def test_entrance_change_is_sorted_and_cannot_make_actor_enter_at_previous_sound(self):
  p=self.project();p['script']='场景 1\n客厅\n【声音】门被推开。\n周明冲进客厅。\n周明：你好。';book=source.ledger(m.AppContext(),p);events=book['events'];entry=next(e for e in events if '冲进' in e['text']);sound=next(e for e in events if e['kind']=='sound');key=next(k for k,a in d.catalog(p).items() if a['id']=='man')
  def wrong(body,job):
   result=self.response(body,job);obj=json.loads(result['choices'][0]['message']['content']);obj['cast'][key]['changes']=[{'at':sound['id'],'placement':'从门外冲入','present':True,'look':'L1'}];result['choices'][0]['message']['content']=json.dumps(obj);return result
  with patch.object(self.q,'text_request',side_effect=wrong):scene=d.direct_scene(m.AppContext(),p,self.task(),book,'scene-1',events)
  self.assertFalse(d.state_at(scene,events,events.index(entry))[key]['present']);self.assertTrue(d.state_at(scene,events,events.index(entry)+1)[key]['present'])
 def test_reference_outfit_is_not_repeated_in_any_generated_section(self):
  p=self.project();r,t=self.run_plan(p)
  for shot in r['shots']:
   self.assertNotIn('黑色外套',shot['video_prompt']);self.assertNotIn('成年男子',shot['video_prompt']);self.assertNotIn('黑色外套',shot['image_prompt'])
 def test_explicit_actor_beats_wrong_model_assignment_and_joint_action_keeps_both(self):
  p=self.project();cat=d.catalog(p);key=next(k for k,a in cat.items() if a['id']=='man');event={'id':'B1','kind':'action','text':'周明顺手指向姓名栏。','role_ids':[]};scene={'actors':{'B1':['A1']}}
  self.assertEqual(d.actor_keys(cat,event,scene),[key]);event['text']='林岚和周明各拍两下手。';self.assertEqual(set(d.actor_keys(cat,event,scene)),{'A1',key})
 def test_physical_contact_keeps_partner_but_glance_can_be_offscreen(self):
  p=self.project();cat=d.catalog(p);key=next(k for k,a in cat.items() if a['id']=='man');scene={'actors':{}};e={'id':'B1','kind':'action','text':'林岚轻轻拍周明肩膀。','role_ids':[]};self.assertEqual(set(d.screen_participants(cat,e,scene)),{'A1',key});e['text']='林岚看向周明。';self.assertEqual(d.screen_participants(cat,e,scene),['A1'])
 def test_camera_cannot_introduce_unbound_shoulders(self):
  p=self.project();cat=d.catalog(p);state={'A1':{'placement':'柜台后','side':'left','camera':'前景为周明的背影，看向林岚。'}};view=d.fallback_view(cat,{'visible':['A1'],'before':[]},state,'zh','axis');self.assertNotIn('周明',view);self.assertIn('柜台后',view)
 def test_time_jump_does_not_reuse_yesterday_actor_snapshots(self):
  p=self.project();cat=d.catalog(p);task={'director_location_context':{'room':{'space':'客厅','axis':'同侧','cast':{'A1':{'placement':'躺着','present':True,'look':'L1','camera':'wrong'}}}}};ctx=d.blocking_context(task,{'location_id':'room'},[{'text':'次日。'}],cat);self.assertNotIn('positions',ctx)
 def test_mask_only_change_keeps_current_outfit_and_dynamic_detail(self):
  p=self.project();cat=d.catalog(p);key=next(k for k,a in cat.items() if a['id']=='man');events=[{'id':'B1','kind':'action','text':'周明戴上面罩。'}];scene={'cast':{key:{'look':'L2','placement':'柜台前','changes':[{'at':'B1','look':'L1','present':True,'placement':'柜台前','detail':'戴着面罩'}]}},'actors':{}}
  d.normalize_cast_changes(cat,scene,events);self.assertEqual(scene['cast'][key]['changes'][0]['look'],'L2')
 def test_restage_preserves_stable_ids_dialogue_and_history(self):
  p=self.project();r,t=self.run_plan(p);p['shots']=r['shots'];p['shots'][0]['versions']=[{'id':'old','kind':'video','url':'/old.mp4'}];before=copy.deepcopy(p['shots']);after=d.restage_draft(m.AppContext(),p,t['director_scenes']);self.assertEqual([s['id'] for s in after],[s['id'] for s in before]);self.assertEqual([s['dialogue'] for s in after],[s['dialogue'] for s in before]);self.assertEqual(after[0]['versions'],before[0]['versions'])
 def test_checkpoint_from_appearance_duplicating_revision_is_not_reused(self):
  self.prepare();p=m.load(self.pid);skill=m.storyboard_skill_bundle(p);old=copy.deepcopy(skill);old['version']='2026-10-30.2';job={'id':m.uid(),'created':1,'kind':'text','operation':'generate_storyboard','status':'failed','snapshot':copy.deepcopy(p),'storyboard_skill':old,'storyboard_planning_parts':[{'start':0,'end':len(p['script']),'shots':[]}]};m.job_save(self.pid,job);self.assertFalse(self.q.storyboard_checkpoint(self.pid,p,skill))
 def test_explicit_standing_transition_overrides_stale_seated_snapshot(self):
  scene={'cast':{'A1':{'appearance':'unused','placement':'柜台旁，坐','side':'left','voice':'v','present':True,'look':'L1','changes':[]}},'event_actors':{'B1':['A1']}};events=[{'id':'B1','kind':'action','text':'猛地站起。'},{'id':'B2','kind':'dialogue','text':'你好'}];state=d.state_at(scene,events,1);self.assertEqual(state['A1']['posture'],'站立');p=self.project();view=d.fallback_view(d.catalog(p),{'visible':['A1'],'before':[]},state,'zh','axis');self.assertIn('站立',view);self.assertNotIn('，坐',view)
 def test_source_wide_shot_beats_default_closeup(self):
  p=self.project();view=d.fallback_view(d.catalog(p),{'visible':['A1'],'before':[{'kind':'camera','text':'【固定全景】'}]},{'A1':{'placement':'柜台后','side':'left'}},'zh','axis');self.assertTrue(view.startswith('固定全景'));self.assertNotIn('中近景',view)
 def test_sound_guess_cannot_spawn_bystander_reference_or_change_door_owner(self):
  p=self.project();p['script']='场景 1\n客厅\n林岚站在门旁。\n【声音】大门被猛地推开。\n周明冲进客厅。\n周明：别动。';book=source.ledger(m.AppContext(),p);sound=next(e for e in book['events'] if e['kind']=='sound')
  def wrong(body,job):
   r=self.response(body,job);obj=json.loads(r['choices'][0]['message']['content']);obj['actors'][sound['id']]=['A1'];r['choices'][0]['message']['content']=json.dumps(obj,ensure_ascii=False);return r
  task=self.task()
  with patch.object(self.q,'text_request',side_effect=wrong):out=d.plan(m.AppContext(),p,task)
  shot=next(s for s in out['shots'] if any('冲进' in e['text'] for e in s['source_contract']['beats']));self.assertNotIn('person',shot['asset_ids']);self.assertNotIn('@林岚',shot['video_prompt']);self.assertNotIn('林岚推开',shot['video_prompt']);self.assertIn('大门被猛地推开',shot['video_prompt'])
  scene=task['director_scenes']['scene-1'];scene['action_prose'][sound['id']]='@A1猛地推开大门。';p['shots']=out['shots'];fixed=d.restage_draft(m.AppContext(),p,{'scene-1':scene});entry=next(s for s in fixed if s['id']==shot['id']);self.assertNotIn('@林岚',entry['video_prompt'])
 def test_sound_schema_does_not_ask_model_to_assign_an_unknown_owner(self):
  p=self.project();book=source.ledger(m.AppContext(),p);e={'id':'B_sound','kind':'sound','text':'门响了。'};schema=d.scene_schema(d.scene_roles(d.catalog(p),book['events']),[e],{});self.assertNotIn('B_sound',schema['properties']['actors']['properties'])
 def test_explicit_sound_actor_remains_an_explicit_source_fact(self):
  p=self.project();cat=d.catalog(p);e={'id':'B1','kind':'sound','text':'林岚敲响桌面。'};self.assertEqual(d.actor_keys(cat,e,{'actors':{'B1':['wrong']}}),['A1']);self.assertEqual(d.source_visual(cat,e,{}),'@A1敲响桌面。')
 def test_unassigned_passive_action_cannot_inherit_previous_actor(self):
  p=self.project();cat=d.catalog(p);event={'id':'B1','kind':'action','text':'大门被推开。'};self.assertEqual(d.actor_keys(cat,event,{'actors':{'B1':['A1']}}),[]);event['text']='大门被林岚推开。';self.assertEqual(d.actor_keys(cat,event,{}),['A1'])
 def test_single_entrant_frame_declares_its_cast_extent(self):
  p=self.project();view=d.fallback_view(d.catalog(p),{'visible':['A1'],'before':[{'kind':'action','text':'林岚走进客厅。'}]},{'A1':{'placement':'门外','side':'left'}},'zh','axis');self.assertIn('取景只有他一人',view)
 def test_entry_choreography_uses_unique_named_entrant_not_sound_guess(self):
  p=self.project();cat=d.catalog(p);key=next(k for k,a in cat.items() if a['id']=='man');sound={'id':'B1','kind':'sound','text':'大门被猛地推开。'};entry={'id':'B2','kind':'action','text':'周明冲进客厅。'};state={key:{'placement':'门外','side':'left','voice':'男声'}};cut={'id':'K1','before':[sound,entry],'after':[],'line':None,'visible':[key],'speaker_keys':[],'states':state};clip={'cuts':[cut],'beats':[sound,entry],'states':state};scene={'language':'zh','axis':'same','space':'客厅','actors':{'B1':['A1']},'asset_guided':True};d.stage_clips(scene,[clip],cat);self.assertIn('@'+key+'伸手推开大门',cut['before_text']);self.assertNotIn('@A1',cut['before_text']);self.assertEqual(d.actor_keys(cat,sound,scene),[]);self.assertEqual(cut['director_decisions'][0]['supported_by'],['B1','B2'])
 def test_rewriting_old_generated_plan_rebuilds_instead_of_recycling_false_cache(self):
  p=self.project();r,t=self.run_plan(p);shot=r['shots'][0];shot['director_plan'].pop('pipeline_revision',None);p['shots']=[shot];t['storyboard_shot_ids']=[shot['id']]
  with patch.object(self.q,'text_request',side_effect=self.response) as request:out=d.write_existing(m.AppContext(),p,t)
  self.assertTrue(request.called);self.assertEqual(out['shots'][0]['id'],shot['id']);self.assertEqual(out['shots'][0]['director_plan']['pipeline_revision'],d.PIPELINE_REVISION)
 def test_native_clips_preserve_source_and_only_one_speaking_source(self):
  p=self.project();before=copy.deepcopy(p);r,t=self.run_plan(p);self.assertEqual(p,before)
  source_lines=[(e['speaker'],e['text']) for e in b.script_dialogue_lines(p['script'],p['assets'],True)]
  self.assertEqual(source_lines,[(line['speaker'],line['text']) for shot in r['shots'] for line in shot['dialogue']])
  for shot in r['shots']:
   self.assertLessEqual(len({line['speaker'] for line in shot['dialogue']}),1);self.assertGreaterEqual(shot['duration'],4);b.validate(m.AppContext(),p,shot,shot['video_prompt'],'reference')
  events=[e for shot in r['shots'] for e in shot['source_contract']['beats']];self.assertEqual(events,source.ledger(m.AppContext(),p)['events'])
 def test_native_reverse_shot_has_only_current_visible_speaker(self):
  p=self.project();r,t=self.run_plan(p);shot=next(s for s in r['shots'] if s['dialogue'] and s['dialogue'][0]['text']=='你好。')
  self.assertIn('man',shot['asset_ids']);self.assertNotIn('person',shot['asset_ids']);self.assertIn('@周明',shot['video_prompt'])
  self.assertEqual(shot['director_plan']['cuts'][0]['visible'],[next(k for k,a in d.catalog(p).items() if a['id']=='man')])
 def test_sound_and_visible_cause_stay_in_same_clip(self):
  p=self.project();p['script']='场景 1\n客厅\n林岚坐在左侧。\n【声音】门被推开。\n周明冲进客厅。\n周明：你好。\n';book=source.ledger(m.AppContext(),p);groups=d.event_groups(book['events']);sound=next(e for e in book['events'] if e['kind']=='sound');group=next(g for g in groups if sound in g)
  self.assertTrue(any('冲进' in e['text'] for e in group))
  r,t=self.run_plan(p);clip=next(s for s in r['shots'] if any(e['id']==sound['id'] for e in s['source_contract']['beats']));self.assertTrue(any('冲进' in e['text'] for e in clip['source_contract']['beats']))
 def test_true_entrance_has_outside_precondition(self):
  p=self.project();p['script']='场景 1\n客厅\n【声音】门被推开。\n周明冲进客厅。\n周明：你好。\n';book=source.ledger(m.AppContext(),p)
  with patch.object(self.q,'text_request',side_effect=self.response):scene=d.direct_scene(m.AppContext(),p,self.task(),book,'scene-1',book['events'])
  key=next(k for k,a in d.catalog(p).items() if a['id']=='man');self.assertFalse(scene['cast'][key]['present']);self.assertIn('入口外侧',scene['cast'][key]['placement'])
  event=next(e for e in book['events'] if '冲进' in e['text']);after=d.state_at(scene,book['events'],book['events'].index(event)+1);self.assertTrue(after[key]['present'])
 def test_typed_location_change_replaces_old_location_without_keyword_guessing(self):
  scene={'cast':{'A1':{'appearance':'a','placement':'门外','side':'left','voice':'v','present':False,'look':None,'changes':[{'at':'B1','placement':'场内，面向柜台','present':True,'look':None}]}}}
  state=d.state_at(scene,[{'id':'B1'},{'id':'B2'}],1)['A1'];self.assertEqual(state['placement'],'场内，面向柜台');self.assertTrue(state['present'])
 def test_two_visible_people_are_not_automatically_made_to_face_each_other(self):
  p=self.project();cat=d.catalog(p);keys=list(d.scene_roles(cat,source.ledger(m.AppContext(),p)['events']));state={k:{'appearance':'人物','placement':'面向入口','side':'center','present':True} for k in keys};view=d.fallback_view(cat,{'visible':keys,'before':[]},state,'zh','axis');self.assertNotIn('面向@',view)
 def test_unknown_or_missing_view_cannot_hide_the_speaker(self):
  p=self.project();r,t=self.run_plan(p);shot=r['shots'][0];cut=shot['director_plan']['cuts'][0];self.assertIn('A1',cut['visible']);self.assertIn('@A1',cut['view'])
 def test_model_cannot_put_quoted_dialogue_in_delivery(self):
  p=self.project();r,t=self.run_plan(p)
  for shot in r['shots']:
   for cut in shot['director_plan']['cuts']:self.assertIn(cut['delivery'],('清亮女声','低沉男声',''))
 def test_alias_adjacent_to_chinese_is_compiled_and_actual_order_is_used(self):
  p=self.project();r,t=self.run_plan(p);shot=r['shots'][0];apply,_=d.labels(m.AppContext(),p,shot,d.catalog(p),'reference');self.assertNotIn('@A',apply('@A1抬头。'))
  inputs=[{'asset_id':aid,'url':'/asset.png','look_id':shot['character_looks'].get(aid)} for aid in reversed(shot['asset_ids'])]
  compiled,bindings=m.compile_shot_prompt(p,shot,'video',inputs);self.assertNotIn('@A',compiled);self.assertIn('Source: <Picture',compiled)
 def test_guessed_performer_cannot_rewrite_unassigned_passive_sound(self):
  p=self.project();cat=d.catalog(p);key=next(k for k,a in cat.items() if a['id']=='man');event={'id':'B1','kind':'sound','text':'门被猛地推开。','role_ids':[]};scene={'actors':{'B1':[key]}}
  self.assertEqual(d.source_visual(cat,event,scene),'门被猛地推开。')
 def test_large_planning_boundaries_cannot_duplicate_or_drop_events(self):
  p=self.project();book=source.ledger(m.AppContext(),p);events=book['events'];scene={'clips':[{'through':events[-1]['id'],'props':[]},{'through':events[0]['id'],'props':[]},{'through':events[-1]['id'],'props':[]}]};clips=d.split_clips(events,scene)
  self.assertEqual([e for c in clips for e in c['beats']],events)
 def test_reference_props_are_not_copied_from_the_global_catalogue(self):
  p=self.project();cat=d.catalog(p);cat['A99']={'id':'never','name':'未出场的道具','type':'道具'};keys=d.resources(cat,{'beats':[{'text':'两人说话。'}],'props':['A99']},{'location_id':'room'},[{'visible':['A1'],'speaker_keys':['A1']}],{})
  self.assertNotIn('A99',keys)
 def test_recompile_is_idempotent_and_does_not_touch_media(self):
  p=self.project();r,t=self.run_plan(p);shot=r['shots'][0];shot.update(video='/old.mp4',versions=[{'id':'v','kind':'video','url':'/old.mp4'}]);before=copy.deepcopy(shot);d.compile_shot(m.AppContext(),p,shot);self.assertEqual(before,shot)
 def test_source_fields_and_debug_notes_do_not_enter_video_prompt(self):
  p=self.project();r,t=self.run_plan(p)
  for shot in r['shots']:
   for phrase in ('原文动作','原文事件','前情已发生','@A1','B1','before_text'):self.assertNotIn(phrase,shot['video_prompt'])
 def test_final_check_accepts_compound_group_speakers(self):
  p=self.project();p['script']='场景 1\n客厅\n林岚、周明同时抬头。\n两人：好！\n';r,t=self.run_plan(p);shot=r['shots'][0];self.assertIn('(S1,S2)',shot['video_prompt']);b.validate(m.AppContext(),p,shot,shot['video_prompt'],'reference')
 def test_first_frame_is_a_spatial_snapshot_not_a_future_action_summary(self):
  p=self.project();r,t=self.run_plan(p)
  for shot in r['shots']:
   view=shot['director_plan']['cuts'][0]['view'];self.assertTrue('画面' in view);self.assertNotIn('原文',view)
 def test_reverse_turns_keep_the_same_screen_sides(self):
  p=self.project();r,t=self.run_plan(p);views=[s['director_plan']['cuts'][0]['view'] for s in r['shots'] if s['dialogue']]
  for shot,view in zip([s for s in r['shots'] if s['dialogue']],views):
   self.assertIn('左侧' if shot['dialogue'][0]['speaker']=='林岚' else '右侧',view)
 def test_timestamps_never_emit_four_digit_milliseconds(self):
  p=self.project();p['script']='场景 1\n客厅\n林岚：你好。\n林岚：再见。\n';r,t=self.run_plan(p);shot=r['shots'][0];cut=copy.deepcopy(shot['director_plan']['cuts'][0]);shot['director_plan']['cuts']=[copy.deepcopy(cut) for _ in range(3)]
  for c,seconds in zip(shot['director_plan']['cuts'],[3.2,5.8,2.1]):c['seconds']=seconds
  shot['dialogue']=[copy.deepcopy(shot['dialogue'][0]) for _ in range(3)];d.compile_shot(m.AppContext(),p,shot);self.assertIn('At 00:09.000,',shot['video_prompt'])
 def test_backend_failure_and_cancellation_are_not_hidden(self):
  from task_queue import Cancelled
  p=self.project()
  for error in (ValueError('503'),Cancelled('stop')):
   with patch.object(self.q,'text_request',side_effect=error),self.assertRaises(type(error)):d.plan(m.AppContext(),p,self.task())
