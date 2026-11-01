import copy,importlib.util,json,tempfile,threading,time,unittest,subprocess,sys
from pathlib import Path
from unittest.mock import patch,Mock
spec=importlib.util.spec_from_file_location('shotdesk',Path(__file__).with_name('server.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from task_queue import Cancelled
class QueueContracts(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.patch=patch.object(m,'DATA',Path(self.temp.name));self.patch.start();self.pid='a'*32;self.root=Path(self.temp.name)/self.pid;(self.root/'jobs').mkdir(parents=True);(self.root/'media').mkdir()
  m.save(self.root/'project.json',{'id':self.pid,'name':'Queue test','content':'original story','script':'','assets':[],'shots':[],'ratio':'16:9'})
  self.q=m.TaskQueue(m.AppContext());self.qpatch=patch.object(m,'Q',self.q);self.qpatch.start()
  self.llmpatch=patch.object(m,'llm_catalog',return_value={'default':m.TEXT_MODEL,'models':[{'id':m.TEXT_MODEL,'available':True}],'available':True});self.llmpatch.start()
  self.addCleanup(self.llmpatch.stop)
  from test_support import legacy_engine
  engine_patch=patch.object(self.q,'engine',return_value=legacy_engine(m));engine_patch.start();self.addCleanup(engine_patch.stop)
 def tearDown(self):self.qpatch.stop();self.patch.stop();self.temp.cleanup()
 def job(self,kind='image',**kw):
  j={'id':m.uid(),'kind':kind,'status':'queued','created':time.time(),'target_id':'s','model':'model',**kw};m.job_save(self.pid,j);return j
 def test_queued_job_cancel_never_submits(self):
  j=self.job();self.q.media_lock.acquire()
  with patch.object(self.q,'run_media') as run:
   self.q.enqueue(self.pid,j);result=self.q.cancel(self.pid,j['id']);self.q.media_lock.release();time.sleep(.3)
   self.assertEqual(result['status'],'cancelled');run.assert_not_called()
 def test_targeted_upstream_delete_and_interrupt(self):
  calls=[]
  def request(url,body=None,**kw):
   calls.append((url,body));return {'queue_running':[[0,'mine']] if not any(x[0].endswith('/interrupt') for x in calls) else [[0,'somebody-else']],'queue_pending':[]} if url.endswith('/queue') and body is None else {}
  with patch.object(m,'request',side_effect=request):self.q.stop_comfy('mine')
  self.assertIn((self.q.comfy+'/queue',{'delete':['mine']}),calls)
  self.assertIn((self.q.comfy+'/interrupt',{'prompt_id':'mine'}),calls)
  self.assertFalse(any(body and ('clear' in body or 'prompt_id' in body and body['prompt_id']!='mine') for url,body in calls))
 def test_queued_or_absent_own_task_does_not_interrupt_another_client(self):
  calls=[]
  def request(url,body=None,**kwargs):
   calls.append((url,body));return {'queue_running':[[0,'somebody-else']],'queue_pending':[]} if body is None else {}
  with patch.object(m,'request',side_effect=request):self.q.stop_comfy('mine')
  self.assertFalse(any(url.endswith('/interrupt') for url,body in calls))
 def test_cancel_failure_is_not_falsely_completed(self):
  j=self.job(status='running',prompt_id='mine')
  with patch.object(self.q,'stop_comfy',side_effect=TimeoutError('still running')),patch.object(self.q,'monitor_cancel'):
   result=self.q.cancel(self.pid,j['id']);self.assertEqual(result['status'],'cancelling');self.assertIn('still running',result['cancel_error'])
 def test_cancellation_before_commit_keeps_project(self):
  j=self.job('text',target_id='project',snapshot=m.load(self.pid));self.q.events[j['id']]=threading.Event();self.q.events[j['id']].set()
  self.q.worker(self.pid,j);self.assertEqual(m.load(self.pid)['shots'],[]);self.assertEqual(json.loads(m.job_path(self.pid,j['id']).read_text())['status'],'cancelled')
 def test_text_worker_persists_timestamps(self):
  j=self.job('text',target_id='project',snapshot=m.load(self.pid))
  with patch.object(m,'plan',return_value={'script':'created','assets':[],'shots':[]}):self.q.worker(self.pid,j)
  value=json.loads(m.job_path(self.pid,j['id']).read_text());self.assertEqual(value['status'],'completed');self.assertGreaterEqual(value['finished_at'],value['started_at']);self.assertEqual(m.load(self.pid)['script'],'created')
 def test_text_cancel_closes_only_selected_connection(self):
  j=self.job('text',status='running');mine=Mock();other=Mock();self.q.connections={j['id']:mine,'other':other};result=self.q.cancel(self.pid,j['id'])
  self.assertEqual(result['status'],'cancelled');mine.close.assert_called_once();other.close.assert_not_called()
 def test_compose_cancel_terminates_only_own_process(self):
  j=self.job('compose',status='running');mine=Mock();mine.poll.return_value=None;other=Mock();self.q.processes={j['id']:mine,'other':other};self.q.cancel(self.pid,j['id']);mine.terminate.assert_called_once();other.terminate.assert_not_called()
 def test_public_jobs_never_leak_base64_requests(self):
  j=self.job(request={'image':['secret-base64']},snapshot={'content':'private'});value=self.q.list()[0];self.assertNotIn('request',value);self.assertNotIn('snapshot',value)
 def test_eta_requires_three_completed_matching_jobs(self):
  now=time.time()
  for i in range(3):self.job(status='completed',created=now-200-i,started_at=now-100-i,finished_at=now-80-i)
  active=self.job(status='running',started_at=now-2);rows=self.q.list();row=next(x for x in rows if x['id']==active['id']);self.assertIsNotNone(row['eta_at']);self.assertEqual(row['eta_samples'],3)
 def test_pending_cancel_survives_restart(self):
  j=self.job(status='cancelling',cancel_requested=True)
  with patch.object(self.q,'cancel') as cancel:
   self.q.resume();time.sleep(.05);cancel.assert_called_once_with(self.pid,j['id'])
class MediaCompletionContracts(unittest.TestCase):
 setUp=QueueContracts.setUp
 tearDown=QueueContracts.tearDown
 job=QueueContracts.job
 def test_media_result_completion_and_start_time(self):
  import io
  p=m.load(self.pid);p['shots']=[{'id':'s','title':'first','image_prompt':'Literal prompt','duration':4}];m.save(self.root/'project.json',p)
  j=self.job(request={'model':'model','prompt':'Literal prompt'},transport='comfy',target='shot')
  engine=Mock();engine.build_graph.return_value=({'1':{'inputs':{'text':'Literal prompt'}}},'output',[])
  def request(url,body=None,**kw):
   if url.endswith('/prompt'):return {'prompt_id':'my-upstream'}
   if '/history/' in url:return {'my-upstream':{'status':{'completed':True,'messages':[['execution_start',{'timestamp':int((time.time()-5)*1000)}]]},'outputs':{'output':{'images':[{'filename':'result.png','type':'output'}]}}}}
   return {'queue_running':[],'queue_pending':[]}
  with patch.object(self.q,'engine',return_value=engine),patch.object(m,'request',side_effect=request),patch.object(m.OP,'open',return_value=io.BytesIO(b'PNG media bytes')):
   self.q.worker(self.pid,j)
  result=json.loads(m.job_path(self.pid,j['id']).read_text());self.assertEqual(result['status'],'completed');self.assertGreaterEqual(result['finished_at']-result['started_at'],4)
  shot=m.load(self.pid)['shots'][0];self.assertEqual(shot['versions'][0]['prompt'],'Literal prompt');self.assertTrue(m.local_file(shot['image']).is_file())
if __name__=='__main__':unittest.main()
