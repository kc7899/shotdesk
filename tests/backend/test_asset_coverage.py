import copy,json,unittest
from unittest.mock import patch
from tests.backend import test_queue
m=test_queue.m
class AssetCoverage(unittest.TestCase):
 setUp=test_queue.QueueContracts.setUp
 tearDown=test_queue.QueueContracts.tearDown
 def response(self,rows,reason=''):return {'choices':[{'message':{'content':json.dumps({'candidates':rows,'empty_reason':reason},ensure_ascii=False)}}]}
 def character(self):return {'type':'角色','name':'林岚','gender':'女性','age_range':'30岁','description':'30岁女性，齐肩黑发。','looks':[{'name':'日常','description':'蓝色棉质衬衫、黑色直筒西裤和黑色平底鞋。'}]}
 def scene(self):return {'type':'场景','name':'办公室','description':'白墙、木质书桌和左侧入口，布局清晰。','looks':[]}
 def prop(self):return {'type':'道具','name':'钥匙','description':'银色金属钥匙，圆形钥匙头和短齿。','looks':[]}
 def prepare(self):
  m.update(self.pid,lambda p:p.update(script='办公室内，林岚将银色钥匙交给同事。'))
  return m.load(self.pid)
 def test_character_only_output_gets_two_scoped_checks_and_keeps_project(self):
  p=self.prepare();before=copy.deepcopy(p);task={'snapshot':p,'model':'local'}
  with patch.object(self.q,'text_request',side_effect=[self.response([self.character()]),self.response([self.scene()]),self.response([self.prop()])]) as request:result=m.extract_assets(task)
  self.assertEqual(request.call_count,3);self.assertEqual(result['coverage']['counts'],{'角色':1,'场景':1,'道具':1});self.assertEqual(m.load(self.pid),before)
  self.assertEqual(json.loads(request.call_args_list[1].args[0]['messages'][1]['content'])['category'],'场景');self.assertEqual(json.loads(request.call_args_list[2].args[0]['messages'][1]['content'])['category'],'道具')
 def test_complete_result_adds_no_extra_calls(self):
  p=self.prepare()
  with patch.object(self.q,'text_request',return_value=self.response([self.character(),self.scene(),self.prop()])) as request:result=m.extract_assets({'snapshot':p,'model':'local'})
  self.assertEqual(request.call_count,1);self.assertEqual(result['coverage']['supplemented'],[])
 def test_truly_absent_prop_is_not_invented(self):
  p=self.prepare()
  with patch.object(self.q,'text_request',side_effect=[self.response([self.character(),self.scene()]),self.response([],'仅有对话，没有必要独立制作的道具。')]) as request:result=m.extract_assets({'snapshot':p,'model':'local'})
  self.assertEqual(request.call_count,2);self.assertEqual(result['coverage']['counts']['道具'],0);self.assertIn('仅有对话',result['coverage']['empty_reasons']['道具'])
 def test_wrong_category_is_not_added_or_retried_forever(self):
  p=self.prepare()
  with patch.object(self.q,'text_request',side_effect=[self.response([self.character(),self.scene()]),self.response([self.character()])]) as request:result=m.extract_assets({'snapshot':p,'model':'local'})
  self.assertEqual(request.call_count,2);self.assertEqual(result['coverage']['counts']['角色'],1);self.assertEqual(result['coverage']['counts']['道具'],0);self.assertIn('其他类型',result['coverage']['empty_reasons']['道具'])
 def test_old_frozen_tasks_keep_old_call_contract(self):
  p=self.prepare();skill=m.extraction_skill_bundle();skill.pop('coverage_check')
  with patch.object(self.q,'text_request',return_value=self.response([self.character()])) as request:result=m.extract_assets({'snapshot':p,'model':'local','extraction_skill':skill,'extraction_skill_text':skill['text']})
  self.assertEqual(request.call_count,1);self.assertNotIn('coverage',result)
 def test_supplement_length_failure_preserves_existing_assets(self):
  p=self.prepare();bad={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
  with patch.object(self.q,'text_request',side_effect=[self.response([self.character()]),bad]):
   with self.assertRaisesRegex(ValueError,'未修改'):m.extract_assets({'snapshot':p,'model':'local'})
  self.assertEqual(m.load(self.pid),p)
if __name__=='__main__':unittest.main()
