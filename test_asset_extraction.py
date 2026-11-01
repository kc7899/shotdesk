import copy,json,unittest
from unittest.mock import patch
import test_queue
m=test_queue.m

class AssetExtractionContracts(unittest.TestCase):
 setUp=test_queue.QueueContracts.setUp
 tearDown=test_queue.QueueContracts.tearDown
 def prepare(self):
  m.update(self.pid,lambda p:p.update(script='林岚穿睡衣在客厅拿起钥匙。',assets=[{'id':'person','type':'角色','name':'林岚','prompt':'原人物描述','image':'keep.png','generation_requirements':'用户要求','looks':[{'id':'default','name':'默认造型','prompt':'原造型','image':'look.png','versions':[]}],'default_look_id':'default','voices':[{'id':'voice','name':'原声线','asset_id':None}],'default_voice_id':'voice','versions':[]}],shots=[{'id':'shot','title':'旧镜头','versions':[]}]))
  return m.load(self.pid)
 def rows(self):return [{'type':'角色','name':'林岚','description':'不能覆盖原文','asset_id':'person','looks':[{'name':'睡衣','description':'蓝色睡衣'}]},{'type':'场景','name':'客厅','description':'明亮客厅'},{'type':'道具','name':'钥匙','description':'银色钥匙'}]
 def extract(self,rows=None):
  rows=copy.deepcopy(self.rows() if rows is None else rows)
  for row in rows:
   if row.get('type')=='角色':
    row.setdefault('gender','女性');row.setdefault('age_range','约30至35岁');row.setdefault('looks',[{'name':'日常造型','description':'米色棉质衬衫搭配深蓝直筒长裤、黑色平底鞋，头发整理成低马尾，自然淡妆。'}])
  response={'choices':[{'message':{'content':json.dumps({'candidates':rows},ensure_ascii=False)}}]}
  with patch.object(self.q,'text_request',return_value=response):return m.extract_assets({'snapshot':m.load(self.pid),'model':'local'})
 def completed(self,result=None):
  j={'id':m.uid(),'kind':'text','target':'project','target_id':'project','operation':'extract_assets','status':'completed','snapshot':m.load(self.pid),'result':result or self.extract()};m.job_save(self.pid,j);return j
 def body(self,j):return {'job_id':j['id'],'selections':[{'candidate_id':c['id'],'asset_id':c['asset_id'],'look_ids':[l['id'] for l in c['looks']]} for c in j['result']['candidates']]}
 def test_extraction_does_not_mutate_project(self):
  before=self.prepare();result=self.extract();self.assertEqual(m.load(self.pid),before);self.assertEqual(result['candidates'][0]['asset_id'],'person')
 def test_confirm_only_appends_missing_resources(self):
  before=self.prepare();j=self.completed();result=m.apply_asset_extraction(self.pid,self.body(j));after=result['project'];self.assertEqual(result['added'],2);self.assertEqual(result['reused'],1);self.assertEqual(result['looks_added'],1)
  old=before['assets'][0];current=after['assets'][0]
  for key in ('prompt','image','generation_requirements','default_look_id','voices','default_voice_id'):self.assertEqual(current[key],old[key])
  self.assertEqual(current['looks'][0],old['looks'][0]);self.assertEqual(after['script'],before['script']);self.assertEqual(after['shots'],before['shots'])
 def test_confirmation_is_idempotent(self):
  self.prepare();j=self.completed();body=self.body(j);first=m.apply_asset_extraction(self.pid,body);again=m.apply_asset_extraction(self.pid,body)
  self.assertEqual(again['project']['assets'],first['project']['assets']);self.assertEqual(again['already_applied'],3);self.assertEqual(again['added'],0)
 def test_new_extraction_reuses_previously_added_names_and_looks(self):
  self.prepare();j=self.completed();m.apply_asset_extraction(self.pid,self.body(j));new=self.completed();result=m.apply_asset_extraction(self.pid,self.body(new));self.assertEqual(result['added'],0);self.assertEqual(result['looks_added'],0)
 def test_new_character_outfits_share_one_character_and_default_voice(self):
  self.prepare();rows=[{'type':'角色','name':'陈明','description':'短发','looks':[{'name':'常服','description':'衬衫'},{'name':'雨衣','description':'黄色雨衣'}]}];j=self.completed(self.extract(rows));result=m.apply_asset_extraction(self.pid,self.body(j));a=result['project']['assets'][-1]
  self.assertEqual(a['type'],'角色');self.assertEqual(len(a['looks']),2);self.assertEqual(a['default_look_id'],a['looks'][0]['id']);self.assertEqual(len(a['voices']),1);self.assertNotIn('image',a)
 def test_new_character_without_outfits_is_rejected(self):
  self.prepare()
  with self.assertRaisesRegex(ValueError,'角色缺少'):self.extract([{'type':'角色','name':'陈明','description':'成年男性，短发','looks':[]}])
 def test_declining_generated_outfits_does_not_restore_placeholder(self):
  self.prepare();j=self.completed(self.extract([{'type':'角色','name':'陈明','description':'成年男性，短发'}]));body=self.body(j);body['selections'][0]['look_ids']=[]
  a=m.apply_asset_extraction(self.pid,body)['project']['assets'][-1];self.assertEqual(a['looks'][0]['prompt'],'');self.assertEqual(len(a['voices']),1)
 def test_select_only_scene(self):
  self.prepare();j=self.completed();body=self.body(j);body['selections']=body['selections'][1:2];result=m.apply_asset_extraction(self.pid,body);self.assertEqual(result['added'],1);self.assertEqual(result['looks_added'],0);self.assertEqual(len(result['project']['assets']),2)
 def test_can_skip_outfit(self):
  self.prepare();j=self.completed();body=self.body(j);body['selections']=body['selections'][:1];body['selections'][0]['look_ids']=[];result=m.apply_asset_extraction(self.pid,body);self.assertEqual(len(result['project']['assets'][0]['looks']),1)
 def test_stale_script_rejected_without_any_write(self):
  self.prepare();j=self.completed();m.update(self.pid,lambda p:p.update(script='改写后的剧本'));before=m.load(self.pid)
  with self.assertRaisesRegex(ValueError,'剧本已修改'):m.apply_asset_extraction(self.pid,self.body(j))
  self.assertEqual(m.load(self.pid),before)
 def test_invalid_candidate_or_duplicate_selection_rejected(self):
  self.prepare();j=self.completed();body=self.body(j);body['selections']*=2
  with self.assertRaises(ValueError):m.apply_asset_extraction(self.pid,body)
 def test_invalid_late_selection_rolls_back_earlier_additions(self):
  self.prepare();j=self.completed();body=self.body(j);body['selections'][2]['asset_id']='missing';before=m.load(self.pid)
  with self.assertRaises(ValueError):m.apply_asset_extraction(self.pid,body)
  self.assertEqual(m.load(self.pid),before)
 def test_invalid_look_selection_rejected(self):
  self.prepare();j=self.completed();body=self.body(j);body['selections'][0]['look_ids']=['fake']
  with self.assertRaises(ValueError):m.apply_asset_extraction(self.pid,body)
 def test_explicit_reuse_another_same_type_asset(self):
  self.prepare();j=self.completed(self.extract([{'type':'角色','name':'林女士','description':'别名'}]));body=self.body(j);body['selections'][0]['asset_id']='person';result=m.apply_asset_extraction(self.pid,body);self.assertEqual(result['added'],0);self.assertEqual(result['project']['assets'][0]['name'],'林岚')
 def test_existing_same_name_added_after_extraction_is_reused(self):
  self.prepare();j=self.completed();m.update(self.pid,lambda p:p['assets'].append({'id':'new-room','name':'客厅','type':'场景','prompt':'人工描述','versions':[]}));result=m.apply_asset_extraction(self.pid,self.body(j));self.assertEqual(result['added'],1);self.assertEqual(next(a for a in result['project']['assets'] if a['id']=='new-room')['prompt'],'人工描述')
 def test_duplicate_model_candidates_coalesce_with_outfits(self):
  self.prepare();rows=self.rows()[:1];rows+=copy.deepcopy(rows);rows[1]['looks']=[{'name':'外套','description':'蓝外套'}];result=self.extract(rows);self.assertEqual(len(result['candidates']),1);self.assertEqual(len(result['candidates'][0]['looks']),2)
 def test_unknown_model_asset_or_cross_character_look_rejected(self):
  self.prepare();rows=self.rows();rows[0]['asset_id']='fake'
  with self.assertRaises(ValueError):self.extract(rows)
  rows=self.rows();rows[0]['looks'][0]['look_id']='fake'
  with self.assertRaises(ValueError):self.extract(rows)
 def test_worker_returns_candidates_without_applying(self):
  before=self.prepare()
  with patch('task_queue.threading.Thread'):job=m.launch_asset_extraction(self.pid)
  saved=json.loads(m.job_path(self.pid,job['id']).read_text());result=self.extract()
  with patch.object(m,'extract_assets',return_value=result):self.q.worker(self.pid,saved)
  self.assertEqual(m.load(self.pid),before);stored=json.loads(m.job_path(self.pid,job['id']).read_text());self.assertEqual(stored['result'],result);self.assertEqual(stored['status'],'completed')
 def test_empty_script_and_active_duplicate_are_blocked(self):
  with self.assertRaises(ValueError):m.launch_asset_extraction(self.pid)
  self.prepare()
  with patch('task_queue.threading.Thread'):m.launch_asset_extraction(self.pid)
  with self.assertRaises(ValueError):m.launch_asset_extraction(self.pid)
 def test_empty_candidates_are_valid(self):
  self.prepare();self.assertEqual(self.extract([])['candidates'],[])

 def test_gender_and_age_are_explicit_in_output_prompt(self):
  self.prepare();result=self.extract();role=result['candidates'][0];self.assertIn('女性',role['description']);self.assertIn('30至35岁',role['description'])
 def test_missing_gender_from_model_is_rejected(self):
  self.prepare();response={'choices':[{'message':{'content':json.dumps({'candidates':self.rows()})}}]}
  with patch.object(self.q,'text_request',return_value=response):
   with self.assertRaisesRegex(ValueError,'性别'):m.extract_assets({'snapshot':m.load(self.pid),'model':'local'})
 def test_placeholder_costume_is_rejected(self):
  self.prepare();rows=self.rows();rows[0]['looks'][0]['description']='沿用身份参考图中可见的服装，补全为完整造型。'
  with self.assertRaisesRegex(ValueError,'提示词'):self.extract(rows)
 def test_extraction_skill_is_frozen_for_queued_tasks(self):
  self.prepare()
  with patch('task_queue.threading.Thread'):job=m.launch_asset_extraction(self.pid)
  self.assertNotIn('extraction_skill_text',job);self.assertEqual(len(job['extraction_skill']['sha256']),64)
  stored=json.loads(m.job_path(self.pid,job['id']).read_text())
  with patch.object(m,'extraction_skill_bundle',side_effect=AssertionError('must use snapshot')),patch.object(self.q,'text_request',return_value={'choices':[{'message':{'content':'{"candidates":[]}'}}]}) as request:m.extract_assets(stored)
  self.assertEqual(request.call_args_list[0].args[0]['messages'][0]['content'],stored['extraction_skill_text'])
 def test_inference_notes_stay_outside_image_prompt(self):
  self.prepare();rows=self.rows();rows[0]['inferred_details']=['年龄为美术推演，不是原文事实'];result=self.extract(rows)
  self.assertEqual(result['candidates'][0]['inferred_details'],rows[0]['inferred_details']);self.assertNotIn('美术推演',result['candidates'][0]['description'])
 def test_opt_in_updates_only_existing_prompt(self):
  before=self.prepare();j=self.completed();body=self.body(j);body['selections']=body['selections'][:1];body['selections'][0]['update_description']=True
  result=m.apply_asset_extraction(self.pid,body);after=result['project']['assets'][0];self.assertEqual(after['prompt'],j['result']['candidates'][0]['description']);self.assertEqual(result['descriptions_updated'],1)
  for key in ('image','generation_requirements','default_look_id','voices','default_voice_id'):self.assertEqual(after[key],before['assets'][0][key])
 def test_opt_in_updates_matching_look_without_losing_image(self):
  before=self.prepare();rows=self.rows()[:1];rows[0]['looks']=[{'name':'默认造型','look_id':'default','description':'米色棉质长袖衬衫，深蓝直筒长裤，黑色平底鞋，整洁低马尾与自然淡妆。'}];j=self.completed(self.extract(rows));body=self.body(j);cid=j['result']['candidates'][0]['looks'][0]['id'];body['selections'][0]['update_look_descriptions']=[cid]
  result=m.apply_asset_extraction(self.pid,body);look=result['project']['assets'][0]['looks'][0];self.assertEqual(look['prompt'],rows[0]['looks'][0]['description']);self.assertEqual(look['image'],before['assets'][0]['looks'][0]['image']);self.assertEqual(result['look_descriptions_updated'],1);self.assertEqual(len(result['project']['assets'][0]['looks']),1)
 def test_opt_in_cannot_overwrite_concurrent_manual_description(self):
  self.prepare();j=self.completed();body=self.body(j);body['selections'][0]['update_description']=True;m.update(self.pid,lambda p:p['assets'][0].update(prompt='用户后来修改'))
  with self.assertRaisesRegex(ValueError,'描述已修改'):m.apply_asset_extraction(self.pid,body)
  self.assertEqual(m.load(self.pid)['assets'][0]['prompt'],'用户后来修改')
 def test_opt_in_cannot_overwrite_concurrent_look_edit(self):
  self.prepare();rows=self.rows()[:1];rows[0]['looks']=[{'name':'默认造型','look_id':'default','description':'完整的新造型提示词'}];j=self.completed(self.extract(rows));body=self.body(j);body['selections'][0]['update_look_descriptions']=[j['result']['candidates'][0]['looks'][0]['id']];m.update(self.pid,lambda p:p['assets'][0]['looks'][0].update(prompt='手动改过的造型'))
  with self.assertRaisesRegex(ValueError,'提示词已修改'):m.apply_asset_extraction(self.pid,body)
  self.assertEqual(m.load(self.pid)['assets'][0]['looks'][0]['prompt'],'手动改过的造型')

 def test_targeted_finalization_changes_only_flagged_prompt(self):
  rows=[{'name':'林岚','type':'角色','description':'女性，约30岁，齐肩黑发。','looks':[{'name':'睡衣','look_id':'keep-id','description':'赤脚或穿棉袜，灰色棉质睡衣。'}]},{'type':'道具','name':'钥匙','description':'银色金属钥匙。','looks':[]}]
  before=copy.deepcopy(rows);task={'model':'local','snapshot':{'script':'夜晚居家，穿睡衣。'}}
  with patch.object(self.q,'text_request',return_value={'choices':[{'message':{'content':'{"prompts":[{"key":"0","description":"灰色纯棉圆领长袖睡衣搭配同色宽松长裤、白色棉袜，头发束成低马尾，素颜。"}]}'}}]}) as request:m.finalize_asset_prompts(rows,task)
  self.assertEqual(rows[0]['description'],before[0]['description']);self.assertEqual(rows[1],before[1]);self.assertEqual(rows[0]['looks'][0]['look_id'],'keep-id');self.assertNotIn('或',rows[0]['looks'][0]['description']);self.assertEqual(request.call_count,1);self.assertEqual(task['prompt_finalization']['attempts'],1)
 def test_finalization_has_no_infinite_retry(self):
  rows=[{'type':'角色','description':'男性，约30岁，寸头或短发。','looks':[]}]
  with patch.object(self.q,'text_request',return_value={'choices':[{'message':{'content':'{"prompts":[{"key":"0","description":"男性，寸头或短发。"}]}'}}]}) as request:
   m.finalize_asset_prompts(rows,{'model':'local'})
  self.assertTrue(rows[0]['review_warnings'])
  self.assertEqual(request.call_count,1)
 def test_costume_repair_receives_explicit_owner(self):
  rows=[{'type':'角色','name':'小刘','description':'女性，黑发。','looks':[{'name':'次日入职','description':'胸牌写着老黑，蓝色马甲。'}]},{'type':'角色','name':'老黑','description':'男性，短发。','looks':[]}]
  response={'choices':[{'message':{'content':'{"prompts":[{"key":"0","description":"蓝色衬衫、深蓝长裤，黑色平底鞋。"}]}'}}]}
  with patch.object(self.q,'text_request',return_value=response) as request:m.finalize_asset_prompts(rows,{'model':'local'})
  sent=json.loads(request.call_args.args[0]['messages'][1]['content'])['prompts'][0]
  self.assertEqual(sent['owner_name'],'小刘');self.assertEqual(sent['character_context']['identity'],'女性，黑发。');self.assertNotIn('老黑',rows[0]['looks'][0]['description'])
  self.assertIsNone(m.look_owner_problem('蓝色衬衫。','小刘',rows))
  self.assertIsNotNone(m.look_owner_problem('胸牌写着老黑。','小刘',rows))

 def test_harmless_expression_does_not_block_complete_costume(self):
  text='浅蓝色长袖衬衫，面料挺括，领口扣好，袖口收紧；深灰色修身西裤，裤长及踝；黑色低跟皮鞋，搭配深灰色短袜；深蓝色银行工作马甲，马甲左胸佩戴工牌。头发整齐梳理，神态轻松。'
  self.assertIsNone(m.asset_prompt_problem(text,'角色',True))
  self.assertIsNone(m.asset_prompt_problem('灰色西装，自然表情。','角色',True))
  self.assertIn('剧情动作',m.asset_prompt_problem('灰色西装，坐在床上。','角色',True))
  self.assertIn('手持道具',m.asset_prompt_problem('灰色西装，手持扫码枪。','角色',True))

 def test_negative_exclusions_are_not_alternative_designs(self):
  self.assertIsNone(m.asset_prompt_problem('银色金属钥匙，不含人物或其他家具。','道具'))
  self.assertIsNone(m.asset_prompt_problem('女性，短黑发，职业气质不可或缺。','角色'))
  self.assertIn('备选',m.asset_prompt_problem('黄色或橙色马甲。','角色',True))

 def test_identity_clothing_detected_without_rejecting_stable_traits(self):
  for text in ('女性，身穿白色T恤。','男性，蓝色衬衫。','女性，佩戴银色耳钉。','man wearing a jacket'):
   self.assertIn('身份描述混入',m.asset_prompt_problem(text,'角色'))
  self.assertIsNone(m.asset_prompt_problem('男性，35岁，白领职员，白皙肤色，黑色短发，宽肩。','角色'))
  self.assertIsNone(m.asset_prompt_problem('蓝色衬衫配黑色长裤。','角色',True))
 def test_identity_repair_includes_looks_and_preserves_bindings(self):
  rows=[{'type':'角色','name':'林岚','asset_id':'person','description':'女性，30岁，黑发，身穿白色T恤。','looks':[{'name':'日常','look_id':'day','description':'白色T恤、蓝色牛仔裤。'},{'name':'睡衣','look_id':'night','description':'灰色棉质睡衣、白色棉袜。'}]}]
  repaired=['女性，30岁，黑色齐肩发，椭圆脸。','白色棉质T恤、蓝色直筒牛仔裤、白色运动鞋。','灰色棉质睡衣、白色棉袜。']
  response={'choices':[{'message':{'content':json.dumps({'prompts':[{'key':str(i),'description':v} for i,v in enumerate(repaired)]})}}]}
  with patch.object(self.q,'text_request',return_value=response) as request:m.finalize_asset_prompts(rows,{'model':'local'})
  self.assertEqual(request.call_count,1);self.assertNotIn('T恤',rows[0]['description']);self.assertEqual(rows[0]['asset_id'],'person');self.assertEqual(rows[0]['looks'][1]['look_id'],'night');self.assertNotIn('T恤',rows[0]['looks'][1]['description'])
  sent=json.loads(request.call_args.args[0]['messages'][1]['content']);self.assertEqual(len(sent['prompts']),3);self.assertIn('白色T恤',sent['prompts'][0]['character_context']['identity'])
 def test_repair_that_keeps_identity_clothing_is_rejected_atomically(self):
  rows=[{'type':'角色','description':'男性，白色T恤。','looks':[]}];before=copy.deepcopy(rows)
  response={'choices':[{'message':{'content':'{"prompts":[{"key":"0","description":"男性，白色T恤。"}]}'}}]}
  with patch.object(self.q,'text_request',return_value=response) as request:
   with self.assertRaisesRegex(ValueError,'身份描述混入'):m.finalize_asset_prompts(rows,{'model':'local'})
  self.assertEqual(rows,before);self.assertEqual(request.call_count,1)

 def test_legacy_candidate_requires_reextraction(self):
  self.prepare();j=self.completed();j['result'].pop('prompt_skill');m.job_save(self.pid,j)
  with self.assertRaisesRegex(ValueError,'旧版提取结果'):m.apply_asset_extraction(self.pid,self.body(j))

 def test_alternatives_return_all_candidates_and_can_be_confirmed(self):
  before=self.prepare();rows=self.rows()
  rows[1]['name']='银行营业大厅';rows[1]['description']='现代银行营业大厅，墙面为白色或浅灰色。'
  rows[2]['name']='取号纸';rows[2]['description']='白色热敏纸，上面印有黑色数字或条形码。'
  initial={'choices':[{'message':{'content':json.dumps({'candidates':rows},ensure_ascii=False)}}]}
  rows[0].update(gender='女性',age_range='30岁')
  initial['choices'][0]['message']['content']=json.dumps({'candidates':rows},ensure_ascii=False)
  repair={'choices':[{'message':{'content':json.dumps({'prompts':[{'key':'0','description':rows[1]['description']},{'key':'1','description':rows[2]['description']}]},ensure_ascii=False)}}]}
  with patch.object(self.q,'text_request',side_effect=[initial,repair]) as req:
   result=m.extract_assets({'snapshot':before,'model':'local'})
  self.assertEqual(req.call_count,2);self.assertEqual(len(result['candidates']),3)
  self.assertTrue(all(c['review_warnings'] for c in result['candidates'][1:]))
  self.assertEqual(m.load(self.pid),before)
  j=self.completed(result);applied=m.apply_asset_extraction(self.pid,self.body(j))
  self.assertEqual(applied['added'],2)
 def test_ambiguity_does_not_hide_identity_clothing_or_wrong_owner(self):
  self.assertIn('身份描述混入',m.asset_prompt_problem('男性，白色或蓝色T恤。','角色'))
  rows=[{'type':'角色','name':'小刘','description':'女性，黑发。','looks':[{'name':'日常','description':'胸牌写着老黑，蓝或灰马甲。'}]},{'type':'角色','name':'老黑','description':'男性，短发。','looks':[]}]
  response={'choices':[{'message':{'content':json.dumps({'prompts':[{'key':'0','description':'胸牌写着老黑，蓝或灰马甲。'}]},ensure_ascii=False)}}]}
  with patch.object(self.q,'text_request',return_value=response):
   with self.assertRaisesRegex(ValueError,'其他角色'):m.finalize_asset_prompts(rows,{'model':'local'})

if __name__=='__main__':unittest.main()
