import copy,json,unittest
from unittest.mock import patch
import test_queue
m=test_queue.m

class StoryboardContracts(unittest.TestCase):
 setUp=test_queue.QueueContracts.setUp
 tearDown=test_queue.QueueContracts.tearDown
 def prepare(self,shots=None):
  m.update(self.pid,lambda p:p.update(script='主角进入客厅。',assets=[{'id':'person','name':'主角','type':'角色','prompt':'短发','looks':[{'id':'look','name':'日常','prompt':'日常服装','versions':[]}]},{'id':'room','name':'客厅','type':'场景','prompt':'客厅'}],shots=shots or [],video_mode='reference'))
  return m.load(self.pid)
 def enqueue(self,replace=False):
  with patch('task_queue.threading.Thread'):return self.q.start_storyboard(self.pid,replace)
 def stored(self,j):return json.loads(m.job_path(self.pid,j['id']).read_text())
 def row(self):return {'title':'进入','description':'主角进入客厅。','duration':6,'image_prompt':'@主角·日常 站在 @客厅','video_prompt':'@主角·日常 走进 @客厅','asset_ids':['person','room'],'character_looks':{'person':'look'}}
 def generate(self,p,rows):
  with patch.object(self.q,'text_request',return_value={'choices':[{'message':{'content':json.dumps({'shots':rows},ensure_ascii=False)}}]}):return m.plan_storyboard(p,{'model':'local'})
 def test_requires_reviewable_script(self):
  with self.assertRaises(ValueError):self.enqueue()
 def test_existing_shots_require_explicit_replace(self):
  self.prepare([{'id':'old'}])
  with self.assertRaises(ValueError):self.enqueue()
  self.assertEqual(self.enqueue(True)['operation'],'generate_storyboard')
 def test_active_media_blocks_replacement(self):
  self.prepare();test_queue.QueueContracts.job(self,kind='video',target_id='old')
  with self.assertRaises(ValueError):self.enqueue(True)
 def test_duplicate_project_text_rejected(self):
  self.prepare();self.enqueue()
  with self.assertRaises(ValueError):self.enqueue()
 def test_creates_bound_shots_and_strips_untrusted_media(self):
  p=self.prepare();row=self.row();row.update(id='untrusted',image='/bad.png',video='/bad.mp4',versions=[{'id':'bad'}])
  shot=self.generate(p,[row])['shots'][0]
  self.assertEqual(shot['character_looks'],{'person':'look'});self.assertEqual(shot['asset_ids'],['person','room']);self.assertEqual(shot['versions'],[])
  self.assertNotIn('image',shot);self.assertNotIn('video',shot);self.assertNotEqual(shot['id'],'untrusted');self.assertEqual(shot['prompt_mentions']['主角·日常']['look_id'],'look');self.assertTrue(shot['video_prompt'].startswith('Duration: 6s'));self.assertIsNone(shot['video_override'])
 def test_invalid_asset_rejected(self):
  p=self.prepare();row=self.row();row['asset_ids']=['fake']
  with self.assertRaises(ValueError):self.generate(p,[row])
 def test_invalid_look_rejected(self):
  p=self.prepare();row=self.row();row['character_looks']={'person':'fake'}
  with self.assertRaises(ValueError):self.generate(p,[row])
 def test_unknown_mention_rejected(self):
  p=self.prepare();row=self.row();row['video_prompt']='@不存在 走进房间'
  with self.assertRaises(ValueError):self.generate(p,[row])
 def test_empty_response_rejected(self):
  with self.assertRaises(ValueError):self.generate(self.prepare(),[])
 def test_worker_only_updates_shots(self):
  before=self.prepare();j=self.enqueue();result=self.generate(before,[self.row()])
  with patch.object(m,'plan_storyboard',return_value={**result,'script':'bad','assets':[]}):self.q.worker(self.pid,self.stored(j))
  after=m.load(self.pid);self.assertEqual(after['script'],before['script']);self.assertEqual(after['assets'],before['assets']);self.assertEqual(len(after['shots']),1);self.assertEqual(self.stored(j)['status'],'completed')
 def test_concurrent_edit_preserved_with_recoverable_result(self):
  p=self.prepare();j=self.enqueue();result=self.generate(p,[self.row()]);m.update(self.pid,lambda p:p.update(script='用户改写'))
  with patch.object(m,'plan_storyboard',return_value=result):self.q.worker(self.pid,self.stored(j))
  self.assertEqual(m.load(self.pid)['script'],'用户改写');self.assertEqual(m.load(self.pid)['shots'],[]);self.assertEqual(self.stored(j)['status'],'failed');self.assertEqual(self.stored(j)['result'],result)
 def test_confirmed_replacement_keeps_assets(self):
  before=self.prepare([{'id':'old','video':'old.mp4','versions':[]}]);j=self.enqueue(True);result=self.generate(before,[self.row()])
  with patch.object(m,'plan_storyboard',return_value=result):self.q.worker(self.pid,self.stored(j))
  after=m.load(self.pid);self.assertEqual(after['assets'],before['assets']);self.assertNotEqual(after['shots'][0]['id'],'old');self.assertEqual(self.stored(j)['snapshot']['shots'],before['shots'])

if __name__=='__main__':unittest.main()
