"""Clean-install HTTP tests with a real local fake ComfyUI; no GPU or sibling repo."""
import base64,copy,hashlib,json,tempfile,threading,time,unittest,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import server as app
import workflow_transport as engine
from runtime_config import RuntimeConfig
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB1sAAAAASUVORK5CYII=')
def definition():
 return {'id':'test-image','kind':'image','output_node':'2','bindings':{'prompt':[['1','text']],'seed':[['1','seed']],'width':[['1','width']],'height':[['1','height']]},'graph':{'1':{'class_type':'FakeImage','inputs':{'text':'initial','seed':1,'width':512,'height':512}},'2':{'class_type':'SaveImage','inputs':{'images':['1',0],'filename_prefix':'test'}}}}
class FakeComfy(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,value):
  raw=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if self.path=='/object_info':return self.reply({'FakeImage':{'input':{'required':{}}},'SaveImage':{'input':{'required':{}}}})
  if self.path.startswith('/history/'):return self.reply({'fake-prompt':{'status':{'completed':True,'messages':[['execution_start',{'timestamp':int(time.time()*1000)}]]},'outputs':{'2':{'images':[{'filename':'result.png','subfolder':'','type':'output'}]}}}})
  if self.path.startswith('/view?'):self.send_response(200);self.send_header('Content-Length',str(len(PNG)));self.end_headers();self.wfile.write(PNG);return
  return self.reply({'queue_running':[],'queue_pending':[]})
 def do_POST(self):
  body=self.rfile.read(int(self.headers.get('Content-Length',0)))
  if self.path=='/prompt':self.server.last_graph=json.loads(body)['prompt'];return self.reply({'prompt_id':'fake-prompt'})
  return self.reply({'ok':True})
class Portable(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.settings=RuntimeConfig(self.root/'data');(self.root/'data').mkdir()
  self.comfy=ThreadingHTTPServer(('127.0.0.1',0),FakeComfy);threading.Thread(target=self.comfy.serve_forever,daemon=True).start();self.addCleanup(self.comfy.server_close);self.addCleanup(self.comfy.shutdown)
  for name,value in [('DATA',self.root/'data'),('SETTINGS',self.settings),('TEXT',''),('TEXT_KEY_FILE',''),('LLM_PROVIDERS_FILE',str(self.root/'no-models.json')),('INDEXTTS',''),('_llm_catalog_cache',None)]:
   guard=patch.object(app,name,value);guard.start();self.addCleanup(guard.stop)
  guard=patch.dict('os.environ',{'SHOTDESK_ACCESS_TOKEN':''});guard.start();self.addCleanup(guard.stop)
  guard=patch.object(engine,'ROOT',self.root/'workflows');guard.start();self.addCleanup(guard.stop)
  guard=patch.object(engine,'COMFY','http://127.0.0.1:'+str(self.comfy.server_port));guard.start();self.addCleanup(guard.stop)
  self.q=app.TaskQueue(app.AppContext());self.q.comfy=engine.COMFY
  guard=patch.object(app,'Q',self.q);guard.start();self.addCleanup(guard.stop)
  guard=patch.object(self.q,'engine',return_value=engine);guard.start();self.addCleanup(guard.stop)
  self.http=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=self.http.serve_forever,daemon=True).start();self.addCleanup(self.http.server_close);self.addCleanup(self.http.shutdown)
  self.base='http://127.0.0.1:'+str(self.http.server_port);self.op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 def req(self,path,body=None,headers=None):
  req=urllib.request.Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json',**(headers or {})})
  with self.op.open(req,timeout=5) as r:return json.load(r)
 def test_empty_install_crud_default_scheme_and_unconfigured_services(self):
  self.assertEqual(self.req('/api/model-catalog')['images'],[]);p=self.req('/api/projects',{'name':'示例短剧'});self.assertEqual(p['storyboard_scheme'],'h3-structured-v2');self.assertEqual(p['image_model'],'');self.assertEqual(p['assets'],[])
  self.req('/api/projects/'+p['id']+'/save',{'script':'一个人走进房间。'});self.assertEqual(self.req('/api/projects/'+p['id'])['script'],'一个人走进房间。')
 def test_import_dependency_check_and_real_queue_output(self):
  self.req('/api/workflows/import',{'workflow':definition()});check=self.req('/api/workflows/check',{'id':'test-image'});self.assertTrue(check['ok']);p=self.req('/api/projects',{'name':'镜头验收'});shot={'id':'s1','title':'杯子','image_prompt':'An exact prompt.','duration':4,'asset_ids':[],'versions':[]}
  self.req('/api/projects/'+p['id']+'/save',{'shots':[shot],'reset_epochs':p.get('reset_epochs',{})});job=self.req('/api/projects/'+p['id']+'/generate',{'target':'shot','id':'s1','kind':'image'})
  for _ in range(100):
   jobs=self.req('/api/projects/'+p['id']+'/jobs');current=next(j for j in jobs if j['id']==job['id'])
   if current['status'] in ('completed','failed'):break
   time.sleep(.02)
  self.assertEqual(current['status'],'completed',current);saved=self.req('/api/projects/'+p['id']);self.assertTrue(saved['shots'][0]['image']);self.assertEqual(self.comfy.last_graph['1']['inputs']['text'],'An exact prompt.');self.assertEqual(len(saved['shots'][0]['versions']),1);self.assertEqual(self.comfy.last_graph['1']['inputs']['seed'],json.loads(app.job_path(p['id'],job['id']).read_text())['request']['seed'])
 def test_settings_redaction_and_auth_for_projects_and_media(self):
  self.req('/api/settings',{'llm_url':'http://localhost:9999/v1','llm_api_key':'test-key','access_password':'a-long-test-password'})
  with self.assertRaises(urllib.error.HTTPError) as failure:self.req('/api/projects')
  self.assertEqual(failure.exception.code,401)
  result=self.req('/api/settings',headers={'Authorization':'Bearer a-long-test-password'});self.assertNotIn('test-key',json.dumps(result));self.assertNotIn('password_hash',result);self.assertTrue(result['api_key_configured'])
  request=urllib.request.Request(self.base+'/api/session',data=b'{"password":"a-long-test-password"}',headers={'Content-Type':'application/json'})
  with self.op.open(request,timeout=5) as r:cookie=r.headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
  self.assertEqual(self.req('/api/projects',headers={'Cookie':cookie.split(';')[0]}),[])
 def test_login_localization_public_but_project_data_protected(self):
  self.settings.update({'access_password':'correct-passphrase'})
  with self.op.open(self.base+'/i18n.js?v=test',timeout=5) as response:
   self.assertIn('javascript',response.headers['Content-Type']);self.assertIn(b'ShotdeskI18n',response.read())
  with self.assertRaises(urllib.error.HTTPError) as failure:self.req('/api/projects')
  self.assertEqual(failure.exception.code,401)
  with self.op.open(self.base+'/login',timeout=5) as response:self.assertIn(b'/i18n.js',response.read())
 def test_cross_origin_and_private_file_boundary(self):
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/projects',{'name':'bad'},{'Origin':'http://other-site.invalid'})
  with self.assertRaises(urllib.error.HTTPError):self.req('/../runtime_config.py')
 def test_import_rejects_ui_graph_and_silent_reference_loss(self):
  with self.assertRaises(ValueError):engine.validate({'nodes':[]})
  bad=definition();bad['max_references']=1
  with self.assertRaisesRegex(ValueError,'参考图名额'):engine.validate(bad)
  bad=definition();bad.update(kind='video',modes=['text'])
  with self.assertRaisesRegex(ValueError,'时长'):engine.validate(bad)
 def test_reference_file_not_interpreted_as_missing_checkpoint(self):
  value=definition();value['graph']['1']['inputs']['text']='new upload.png'
  info={'FakeImage':{'input':{'required':{'text':[['old.png']]}}},'SaveImage':{'input':{'required':{}}}}
  with patch.object(engine,'json_request',return_value=info):self.assertTrue(engine.check_definition(value)['ok'])
 def test_private_settings_and_password_cookie_tampering(self):
  self.settings.update({'access_password':'correct-passphrase','llm_api_key':'secret'});self.assertEqual(self.settings.path.stat().st_mode & 0o777,0o600)
  token=self.settings.issue_cookie();self.assertTrue(self.settings.authenticated({'Cookie':'shotdesk_session='+token}));self.assertFalse(self.settings.authenticated({'Cookie':'shotdesk_session='+token+'x'}))
 def test_seed_mapping_required_and_portrait_dimensions(self):
  bad=definition();bad['bindings'].pop('seed')
  with self.assertRaisesRegex(ValueError,'随机种子'):engine.validate(bad)
  engine.import_definition(definition())
  with patch.object(engine,'check_definition',return_value={'ok':True}):
   graph,_,_=engine.build_graph({'model':'test-image','prompt':'portrait','seed':42,'aspect_ratio':'3:4'},'job','image')
  self.assertEqual(graph['1']['inputs']['seed'],42);self.assertEqual((graph['1']['inputs']['width'],graph['1']['inputs']['height']),(384,512))
 def test_local_provider_table_survives_saving_unchanged_url(self):
  with patch.dict('os.environ',{'TEXT_API':'http://gateway:8010/v1/chat/completions'}):
   self.settings.update({'llm_url':'http://gateway:8010/v1'});self.assertTrue(app.use_provider_catalog())
   self.settings.update({'llm_url':'http://other:8000/v1'});self.assertFalse(app.use_provider_catalog())
 def test_optional_speech_connection_uses_supported_jobs_endpoint(self):
  with patch.object(app,'request',return_value=[]) as request:
   result=app.test_service_settings({'service':'speech','url':'http://speech:1249'})
  self.assertTrue(result['ok']);self.assertEqual(request.call_args.args[0],'http://speech:1249/api/jobs')
 def test_llm_discovery_dedicated_key_clear_does_not_reuse_saved_key(self):
  self.settings.update({'llm_api_key':'saved-secret'})
  with patch.object(app,'request',return_value={'data':[{'id':'only-model'}]}) as request:
   result=app.test_service_settings({'service':'llm','url':'http://test-llm/v1','clear_api_key':True})
  self.assertEqual(result['models'],['only-model']);self.assertNotIn('Authorization',request.call_args.kwargs.get('headers') or {})
if __name__=='__main__':unittest.main()
