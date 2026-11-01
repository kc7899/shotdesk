import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import server as m

class LookOptimization(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);p=patch.object(m,'DATA',Path(self.tmp.name));p.start();self.addCleanup(p.stop)
  self.pid='c'*32;root=m.project(self.pid).parent;(root/'jobs').mkdir(parents=True)
  self.p={'id':self.pid,'name':'test','llm_model':'test-llm','assets':[{'id':'a','name':'人物','type':'角色','looks':[{'id':'l','name':'常服','prompt':'蓝色外套，站在床边','generation_requirements':'单人正面全身，白底','versions':[]}]}],'shots':[]}
  m.save(m.project(self.pid),self.p)
 def test_launch_snapshots_description_and_requirements_no_mutation(self):
  with patch.object(m,'llm_catalog',return_value={'models':[{'id':'test-llm'}]}),patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j):j=m.launch_look_optimization(self.pid,{'look_id':'l'})
  self.assertEqual(j['model'],'test-llm');self.assertEqual(j['kind'],'text');self.assertEqual(j['operation'],'optimize_look');self.assertEqual(j['snapshot']['description'],'蓝色外套，站在床边')
  before=m.load(self.pid)
  with patch.object(m.Q,'text_request',return_value={'choices':[{'message':{'content':'{"description":"蓝色外套"}'}}]}) as call:result=m.optimize_look(j)
  self.assertEqual(result['description'],'蓝色外套');self.assertEqual(result['original_requirements'],'单人正面全身，白底');self.assertEqual(m.load(self.pid),before)
  payload=call.call_args[0][0];self.assertEqual(payload['model'],'test-llm');self.assertIn('generation_requirements',payload['messages'][1]['content'])
 def test_bad_json_and_extra_fields_rejected(self):
  j={'id':'j','model':'m','snapshot':{'description':'coat','generation_requirements':'white'}}
  for raw in ['not JSON','{"description":"coat","generation_requirements":"changed"}','{"description":null}']:
   with patch.object(m.Q,'text_request',return_value={'choices':[{'message':{'content':raw}}]}):
    with self.assertRaises((ValueError,TypeError)):m.optimize_look(j)
 def test_missing_or_empty_look_rejected(self):
  with self.assertRaises(ValueError):m.launch_look_optimization(self.pid,{'look_id':'missing'})
  self.p['assets'][0]['looks'][0]['prompt']='';m.save(m.project(self.pid),self.p)
  with self.assertRaises(ValueError):m.launch_look_optimization(self.pid,{'look_id':'l'})
 def test_unknown_model_rejected(self):
  with patch.object(m,'llm_catalog',return_value={'models':[{'id':'other'}]}):
   with self.assertRaises(ValueError):m.llm_model(self.p)
 def test_empty_optimized_description_is_explicit_candidate(self):
  j={'id':'j','model':'m','snapshot':{'description':'站在床边','generation_requirements':'white'}}
  with patch.object(m.Q,'text_request',return_value={'choices':[{'message':{'content':'{"description":""}'}}]}):result=m.optimize_look(j)
  self.assertEqual(result['description'],'');self.assertEqual(result['original_description'],'站在床边')
 def test_worker_optimizer_does_not_plan_or_mutate_project(self):
  job={'id':'optimizer-worker','kind':'text','status':'queued','operation':'optimize_look'}
  with patch.object(m.Q,'start'),patch.object(m.Q,'done') as done,patch.object(m,'optimize_look',return_value={'description':'coat'}),patch.object(m,'plan') as plan,patch.object(m,'update') as update:
   m.Q.worker(self.pid,job)
  plan.assert_not_called();update.assert_not_called();self.assertEqual(done.call_args.kwargs['result']['description'],'coat')
 def test_prop_optimization_uses_target_name_and_own_instruction(self):
  self.p['assets'].append({'id':'prop','name':'梯子','type':'道具','prompt':'铝合金梯子，靠在橱柜和微波炉旁','generation_requirements':m.ASSET_PROMPT_PRESETS['prop'],'versions':[]});m.save(m.project(self.pid),self.p)
  with patch.object(m,'llm_catalog',return_value={'models':[{'id':'test-llm'}]}),patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j):job=m.launch_prop_optimization(self.pid,{'asset_id':'prop'})
  self.assertEqual(job['operation'],'optimize_prop');self.assertEqual(job['target'],'asset');self.assertEqual(job['snapshot']['asset_name'],'梯子')
  with patch.object(m.Q,'text_request',return_value={'choices':[{'message':{'content':'{"description":"铝合金梯子"}'}}]}) as call:result=m.optimize_look(job)
  self.assertEqual(call.call_args[0][0]['messages'][0]['content'],m.PROP_OPTIMIZATION_INSTRUCTION);self.assertEqual(result['description'],'铝合金梯子')
 def test_prop_generation_composes_visible_requirements_and_is_square(self):
  self.p['ratio']='9:16';self.p['image_model']='Flux2-Klein-4B-4step-1K';self.p['assets'].append({'id':'prop','name':'梯子','type':'道具','prompt':'铝合金梯子','generation_requirements':'灰色无缝背景','versions':[]});m.save(m.project(self.pid),self.p)
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j):job=m.launch(self.pid,'asset','prop','image')
  self.assertEqual(job['request']['aspect_ratio'],'1:1');self.assertEqual(job['request']['prompt'],'铝合金梯子\n\n灰色无缝背景')
 def test_prop_optimizer_rejects_other_asset_types(self):
  with self.assertRaises(ValueError):m.launch_prop_optimization(self.pid,{'asset_id':'a'})
 def test_llm_selection_saved(self):
  body=copy.deepcopy(self.p);body['llm_model']='other'
  with patch.object(m.Q,'list',return_value=[]):m.merge_save(self.p,body)
  self.assertEqual(self.p['llm_model'],'other')

if __name__=='__main__':unittest.main()
