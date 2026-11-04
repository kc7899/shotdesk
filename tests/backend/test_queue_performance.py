import io,unittest,json
from pathlib import Path
from unittest.mock import patch,Mock
from tests.backend import test_queue
m=test_queue.m
class QueueIndex(unittest.TestCase):
 setUp=test_queue.QueueContracts.setUp
 tearDown=test_queue.QueueContracts.tearDown
 job=test_queue.QueueContracts.job
 def test_list_and_new_process_reuse_small_summary_without_loading_inputs(self):
  self.job(request={'image':'large-payload'*100000},status='completed');first=self.q.list();reader=Path.read_text
  def reject_full(path,*args,**kwargs):
   if path.parent.name=='jobs':raise AssertionError('Full job must not be read again')
   return reader(path,*args,**kwargs)
  with patch.object(Path,'read_text',reject_full):
   self.assertEqual(first,self.q.list());self.assertEqual(first,m.TaskQueue(m.AppContext()).list())
  self.assertNotIn('request',first[0]);self.assertLess(len(json.dumps(first)),2000)
 def test_poll_summary_excludes_large_bindings_but_preserves_full_agent_records(self):
  self.job(status='completed',original_prompt='prompt'*100000,reference_bindings=[{'data':'binding'*100000}],title='Test',error='readable error')
  full=self.q.list();compact=self.q.list(summary=True)
  self.assertIn('original_prompt',full[0]);self.assertNotIn('original_prompt',compact[0]);self.assertNotIn('reference_bindings',compact[0])
  self.assertEqual(compact[0]['id'],full[0]['id']);self.assertEqual(compact[0]['error'],'readable error')
  self.assertLess(len(json.dumps(compact)),2000)
  self.assertIn('reference_bindings',self.q.list()[0])
 def test_file_update_invalidates_summary(self):
  j=self.job(status='queued');self.assertEqual(self.q.list()[0]['status'],'queued');j['status']='cancelled';m.job_save(self.pid,j)
  self.assertEqual(self.q.list()[0]['status'],'cancelled');self.assertEqual(m.TaskQueue(m.AppContext()).list()[0]['status'],'cancelled')
class MediaRanges(unittest.TestCase):
 setUp=test_queue.QueueContracts.setUp
 tearDown=test_queue.QueueContracts.tearDown
 def serve(self,value):
  path=self.root/'media'/'test.mp4';path.write_bytes(b'0123456789');h=m.Handler.__new__(m.Handler);h.headers={'Range':value} if value else {};h.wfile=io.BytesIO();h.send_response=Mock();h.send_header=Mock();h.end_headers=Mock();h.serve_media(path)
  return h,dict(call.args for call in h.send_header.call_args_list)
 def test_json_compression_is_negotiated_and_round_trips(self):
  import gzip
  for accept in ('','gzip'):
   h=m.Handler.__new__(m.Handler);h.headers={'Accept-Encoding':accept};h.wfile=io.BytesIO();h.send_response=Mock();h.send_header=Mock();h.end_headers=Mock()
   obj={'message':'large response '*1000};h.reply(obj);headers=dict(call.args for call in h.send_header.call_args_list);body=h.wfile.getvalue()
   self.assertEqual(int(headers['Content-Length']),len(body))
   if accept:self.assertEqual(headers['Content-Encoding'],'gzip');body=gzip.decompress(body)
   else:self.assertNotIn('Content-Encoding',headers)
   self.assertEqual(json.loads(body),obj)
 def test_partial_and_suffix_reads(self):
  for value,body,content in [('bytes=2-5',b'2345','bytes 2-5/10'),('bytes=-3',b'789','bytes 7-9/10'),('bytes=7-',b'789','bytes 7-9/10')]:
   h,headers=self.serve(value);h.send_response.assert_called_once_with(206);self.assertEqual(h.wfile.getvalue(),body);self.assertEqual(headers['Content-Range'],content)
 def test_full_and_unsatisfiable_reads(self):
  h,headers=self.serve(None);h.send_response.assert_called_once_with(200);self.assertEqual(h.wfile.getvalue(),b'0123456789');self.assertEqual(headers['Accept-Ranges'],'bytes')
  h,headers=self.serve('bytes=20-');h.send_response.assert_called_once_with(416);self.assertEqual(headers['Content-Range'],'bytes */10')
