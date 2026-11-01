import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from tests.backend import test_queue
m=test_queue.m
class LocalModels(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'providers.json';self.path.write_text(json.dumps({'models':[{'id':'Qwen3.8-27B','models_url':'http://a/v1/models'},{'id':'Qwen3.6-35B-A3B-Uncensored','models_url':'http://b/v1/models'}]}))
  for name,value in [('SETTINGS',m.RuntimeConfig(Path(self.temp.name)/'data')),('LLM_PROVIDERS_FILE',str(self.path)),('_llm_catalog_cache',None),('TEXT','http://gateway/v1/chat/completions'),('TEXT_MODEL','Qwen3.8-27B'),('TEXT_KEY_FILE','')]:
   guard=patch.object(m,name,value);guard.start();self.addCleanup(guard.stop)
 def request(self,url,*args,**kw):
  if url=='http://gateway/v1/models':return {'data':[{'id':'Qwen3.8-27B'},{'id':'Qwen3.6-35B-A3B-Uncensored'},{'id':'extra-model'}]}
  if url=='http://a/v1/models':return {'data':[{'id':'Qwen3.8-27B'}]}
  raise ConnectionRefusedError('offline')
 def test_online_offline_and_additional_gateway_models_remain_visible(self):
  with patch.object(m,'request',side_effect=self.request):catalog=m.llm_catalog()
  self.assertEqual(catalog['default'],'Qwen3.8-27B');models={x['id']:x for x in catalog['models']};self.assertTrue(models['Qwen3.8-27B']['available']);self.assertFalse(models['Qwen3.6-35B-A3B-Uncensored']['available']);self.assertIn('extra-model',models)
 def test_gateway_failure_retains_all_configured_models(self):
  with patch.object(m,'request',side_effect=ConnectionError('offline')):catalog=m.llm_catalog()
  self.assertFalse(catalog['available']);self.assertEqual(len(catalog['models']),2)
 def test_default_and_explicit_selection(self):
  with patch.object(m,'request',side_effect=self.request):self.assertEqual(m.llm_model({}),'Qwen3.8-27B');self.assertEqual(m.llm_model({'llm_model':'extra-model'}),'extra-model')
 def test_offline_has_clear_message(self):
  with patch.object(m,'request',side_effect=self.request),self.assertRaisesRegex(ValueError,'未启动或仍在加载'):m.llm_model({'llm_model':'Qwen3.6-35B-A3B-Uncensored'})
 def test_gateway_key_in_auth_header(self):
  key=Path(self.temp.name)/'key';key.write_text('unit-test-secret')
  with patch.object(m,'TEXT_KEY_FILE',str(key)):self.assertEqual(m.text_headers()['Authorization'],'Bearer unit-test-secret')
 def test_stream_through_gateway_with_selected_model_and_auth(self):
  q=m.TaskQueue(m.AppContext());stream=io.BytesIO(b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n');response=Mock(status=200);response.readline=stream.readline;conn=Mock();conn.getresponse.return_value=response
  with patch('task_queue.http.client.HTTPConnection',return_value=conn),patch.object(m,'text_headers',return_value={'Authorization':'Bearer unit-test-secret'}):out=q.text_request({'model':'Qwen3.8-27B','messages':[]},{'id':'test'})
  self.assertEqual(out['choices'][0]['message']['content'],'ok');args=conn.request.call_args.args;self.assertEqual(args[1],'/v1/chat/completions');self.assertEqual(json.loads(args[2])['model'],'Qwen3.8-27B');self.assertEqual(args[3]['Authorization'],'Bearer unit-test-secret')
 def test_direct_provider_uses_own_endpoint_without_gateway_key(self):
  self.path.write_text(json.dumps({'models':[{'id':'Flash Next','chat_url':'http://flash:30000/v1/chat/completions'}]}))
  self.assertEqual(m.llm_endpoint('Flash Next'),'http://flash:30000/v1/chat/completions');self.assertEqual(m.llm_endpoint('Qwen3.8-27B'),m.TEXT)
  key=Path(self.temp.name)/'key';key.write_text('unit-test-secret')
  with patch.object(m,'TEXT_KEY_FILE',str(key)):self.assertNotIn('Authorization',m.text_headers(m.llm_endpoint('Flash Next')));self.assertIn('Authorization',m.text_headers(m.TEXT))
if __name__=='__main__':unittest.main()
