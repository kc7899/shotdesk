import copy,json,unittest
from unittest.mock import patch
import test_queue
m=test_queue.m

class ScriptOnlyContracts(unittest.TestCase):
 setUp=test_queue.QueueContracts.setUp
 tearDown=test_queue.QueueContracts.tearDown
 def prepare(self):
  p=m.load(self.pid);p.update(script='existing script',assets=[{'id':'asset','name':'reference','versions':[{'id':'v'}]}],shots=[{'id':'shot','video':'keep.mp4','versions':[{'id':'video'}]}]);m.save(self.root/'project.json',p);return m.load(self.pid)
 def enqueue_script(self):
  with patch('task_queue.threading.Thread'):
   return self.q.start_text(self.pid)
 def test_existing_assets_and_shots_allow_regeneration(self):
  before=self.prepare();j=self.enqueue_script();self.assertEqual(j['operation'],'generate_script')
  with patch.object(m,'plan',return_value={'script':'new script','assets':[],'shots':[]}):self.q.worker(self.pid,json.loads(m.job_path(self.pid,j['id']).read_text()))
  after=m.load(self.pid);self.assertEqual(after['script'],'new script')
  for k in ('assets','shots','content'):self.assertEqual(after[k],before[k])
  self.assertEqual(self.enqueue_script()['operation'],'generate_script')
 def test_active_duplicate_is_rejected(self):
  self.prepare();self.enqueue_script()
  with self.assertRaises(ValueError):self.enqueue_script()
 def test_manual_script_change_is_preserved_and_result_recoverable(self):
  self.prepare();j=self.enqueue_script();m.update(self.pid,lambda p:p.update(script='manual edit'))
  with patch.object(m,'plan',return_value={'script':'generated'}):self.q.worker(self.pid,json.loads(m.job_path(self.pid,j['id']).read_text()))
  self.assertEqual(m.load(self.pid)['script'],'manual edit');saved=json.loads(m.job_path(self.pid,j['id']).read_text());self.assertEqual(saved['status'],'failed');self.assertEqual(saved['result']['script'],'generated')
 def test_asset_change_during_generation_is_preserved(self):
  self.prepare();j=self.enqueue_script();m.update(self.pid,lambda p:p['assets'].append({'id':'new-asset'}))
  with patch.object(m,'plan',return_value={'script':'generated'}):self.q.worker(self.pid,json.loads(m.job_path(self.pid,j['id']).read_text()))
  self.assertEqual(len(m.load(self.pid)['assets']),2);self.assertEqual(m.load(self.pid)['script'],'generated')
 def test_llm_response_cannot_create_shots_or_assets(self):
  before=self.prepare()
  response={'choices':[{'message':{'content':json.dumps({'script':'a script','assets':[{'name':'unexpected'}],'shots':[{}]})}}]}
  with patch.object(self.q,'text_request',return_value=response) as request:
   result=m.plan(before,{'model':'local'})
  self.assertEqual(result,{'script':'a script'});self.assertEqual(request.call_args.args[0]['model'],'local')
 def test_empty_script_is_rejected(self):
  with patch.object(self.q,'text_request',return_value={'choices':[{'message':{'content':'{"script":""}'}}]}):
   with self.assertRaises(ValueError):m.plan({'content':'story'},{'model':'local'})

if __name__=='__main__':unittest.main()
