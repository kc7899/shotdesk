import io,json,unittest
from unittest.mock import patch,Mock
from tests.backend import test_queue
m=test_queue.m

class ScreenwriterSkillContracts(unittest.TestCase):
 setUp=test_queue.QueueContracts.setUp
 tearDown=test_queue.QueueContracts.tearDown
 def test_task_freezes_skill_and_exposes_only_metadata(self):
  with patch('task_queue.threading.Thread'):job=self.q.start_text(self.pid)
  saved=json.loads(m.job_path(self.pid,job['id']).read_text())
  self.assertTrue(saved['script_skill_text']);self.assertEqual(len(job['script_skill']['sha256']),64);self.assertNotIn('script_skill_text',job)
  with patch.object(m,'script_skill_bundle',side_effect=AssertionError('must use frozen skill')),patch.object(self.q,'text_request',return_value={'choices':[{'message':{'content':'{"script":"场次正文"}'}}]}) as req:
   m.plan(saved['snapshot'],saved)
  self.assertEqual(req.call_args.args[0]['messages'][0]['content'],saved['script_skill_text'])
 def test_context_uses_assets_without_history_or_media(self):
  p={'content':'保留原台词。','script':'不要当成原文','assets':[{'id':'person','type':'角色','name':'林岚','prompt':'短发，谨慎','generation_requirements':'hidden rendering','image':'/image.png','versions':[{'prompt':'history prompt'}],'looks':[{'id':'look','name':'外套','prompt':'蓝色外套','image':'/look.png','versions':[]}]},{'id':'voice','type':'音频','audio':'/voice.wav'}]}
  with patch.object(self.q,'text_request',return_value={'choices':[{'message':{'content':'{"script":"正文"}'}}]}) as req:m.plan(p,{'model':'selected-llm'})
  body=req.call_args.args[0];context=json.loads(body['messages'][1]['content'])
  self.assertEqual(context['source'],p['content']);self.assertEqual(context['reference_assets'][0]['looks'][0]['description'],'蓝色外套');self.assertEqual(len(context['reference_assets']),1)
  for excluded in ['/image.png','/look.png','/voice.wav','history prompt','hidden rendering','不要当成原文']:self.assertNotIn(excluded,body['messages'][1]['content'])
  self.assertEqual(body['model'],'selected-llm')
 def test_truncation_is_not_accepted_even_when_json_parses(self):
  with patch.object(self.q,'text_request',return_value={'choices':[{'finish_reason':'length','message':{'content':'{"script":"unfinished"}'}}]}):
   with self.assertRaisesRegex(ValueError,'正文未完成'):m.plan({'content':'story'},{'model':'local'})
 def test_stream_preserves_length_finish_reason(self):
  stream=io.BytesIO(b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\ndata: [DONE]\n')
  response=Mock(status=200);response.readline=stream.readline;conn=Mock();conn.getresponse.return_value=response
  with patch('task_queue.http.client.HTTPConnection',return_value=conn):result=self.q.text_request({'model':'local'},{'id':'stream-test'})
  self.assertEqual(result['choices'][0]['finish_reason'],'length');self.assertEqual(result['choices'][0]['message']['content'],'partial')
 def test_skill_load_failure_prevents_task_submission(self):
  with patch.object(m,'script_skill_bundle',side_effect=FileNotFoundError('missing')),patch.object(self.q,'enqueue') as enqueue:
   with self.assertRaises(FileNotFoundError):self.q.start_text(self.pid)
   enqueue.assert_not_called()

if __name__=='__main__':unittest.main()
