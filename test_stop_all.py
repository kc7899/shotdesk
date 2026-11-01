import unittest,tempfile,json,threading,time
from pathlib import Path
from unittest.mock import patch,Mock
import server as m
class StopAll(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);fix=patch.object(m,'DATA',Path(t.name));fix.start();self.addCleanup(fix.stop);self.q=m.TaskQueue(m.AppContext());qfix=patch.object(m,'Q',self.q);qfix.start();self.addCleanup(qfix.stop);self.pids=['a'*32,'b'*32]
  for pid in self.pids:
   root=m.project(pid).parent;(root/'jobs').mkdir(parents=True);m.save(root/'project.json',{'id':pid,'name':'Queue test','assets':[],'shots':[],'ratio':'16:9'})
 def job(self,pid,kind='video',status='queued',**kw):
  j={'id':m.uid(),'kind':kind,'status':status,'created':time.time(),'target_id':'s',**kw};m.job_save(pid,j);return j
 def read(self,pid,j):return json.loads(m.job_path(pid,j['id']).read_text())
 def test_all_projects_and_types_stop_without_removing_history(self):
  jobs=[(pid,self.job(pid,kind)) for pid in self.pids for kind in ('text','image','video','audio','compose')];history=self.job(self.pids[0],status='completed',url='/old.mp4');before=m.job_path(self.pids[0],history['id']).read_bytes();r=self.q.cancel_all();self.assertEqual(r['requested'],10);self.assertEqual(r['cancelled'],10)
  for pid,j in jobs:self.assertEqual(self.read(pid,j)['status'],'cancelled');self.assertTrue(self.q.events[j['id']].is_set())
  self.assertEqual(m.job_path(self.pids[0],history['id']).read_bytes(),before)
 def test_snapshot_marks_every_task_before_upstream_cancel(self):
  running=self.job(self.pids[0],status='running',prompt_id='only-mine');queued=self.job(self.pids[1]);
  with patch('task_queue.threading.Thread') as thread,patch.object(self.q,'stop_comfy') as stop:
   r=self.q.cancel_all();self.assertEqual(r['cancelling'],1);self.assertEqual(self.read(self.pids[1],queued)['status'],'cancelled');self.assertTrue(self.q.events[running['id']].is_set());stop.assert_not_called();thread.call_args.kwargs['target']();stop.assert_called_once_with('only-mine')
 def test_later_tasks_are_not_part_of_stop_snapshot(self):
  running=self.job(self.pids[0],status='running',prompt_id='mine')
  with patch('task_queue.threading.Thread') as thread,patch.object(self.q,'stop_comfy'):
   result=self.q.cancel_all();later=self.job(self.pids[1]);thread.call_args.kwargs['target']()
  self.assertNotIn(later['id'],[j['id'] for j in result['jobs']]);self.assertEqual(self.read(self.pids[1],later)['status'],'queued')
 def test_slow_or_failed_upstream_stays_cancelling(self):
  j=self.job(self.pids[0],status='running',prompt_id='mine')
  with patch('task_queue.threading.Thread') as thread,patch.object(self.q,'stop_comfy',side_effect=TimeoutError('upstream busy')),patch.object(self.q,'monitor_cancel'):
   self.q.cancel_all();thread.call_args.kwargs['target']()
  result=self.read(self.pids[0],j);self.assertEqual(result['status'],'cancelling');self.assertIn('upstream busy',result['cancel_error'])
 def test_duplicate_calls_do_not_spawn_parallel_cancellation_for_same_job(self):
  self.job(self.pids[0],status='running',prompt_id='mine')
  with patch('task_queue.threading.Thread') as thread:
   self.q.cancel_all();self.q.cancel_all();self.assertEqual(thread.call_count,1)
 def test_queued_with_upstream_id_is_not_prematurely_cancelled(self):
  j=self.job(self.pids[0],prompt_id='existing')
  with patch('task_queue.threading.Thread'):self.q.cancel_all()
  self.assertEqual(self.read(self.pids[0],j)['status'],'cancelling')
 def test_local_queued_media_cannot_start_after_stop(self):
  j=self.job(self.pids[0]);self.q.cancel_all()
  with patch.object(self.q,'run_media') as run:self.q.worker(self.pids[0],j);run.assert_not_called()
 def test_text_connection_is_closed_before_slow_media_stop(self):
  self.job(self.pids[0],status='running',prompt_id='mine');text=self.job(self.pids[1],kind='text',status='running');conn=Mock();self.q.connections[text['id']]=conn
  def stop(prompt):conn.close.assert_called_once();self.assertEqual(prompt,'mine')
  with patch('task_queue.threading.Thread') as thread,patch.object(self.q,'stop_comfy',side_effect=stop):self.q.cancel_all();thread.call_args.kwargs['target']()
 def test_no_active_tasks_is_successful_noop(self):
  self.assertEqual(self.q.cancel_all()['requested'],0)
if __name__=='__main__':unittest.main()
