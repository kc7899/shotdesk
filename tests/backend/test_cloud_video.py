"""Provider contracts and real local HTTP/queue tests; no paid cloud generation."""
import copy,json,threading,time,unittest,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from tests.backend import test_portable as fx
import cloud_video as c
app=fx.app
class FakeCloud(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,data):
  raw=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}');self.server.calls.append((self.command,self.path,body,self.headers.get('Authorization')))
  self.send({'task_id':'task1','id':'task1','request_id':'task1'})
 def do_GET(self):
  self.server.calls.append((self.command,self.path,None,self.headers.get('Authorization')))
  if self.path=='/artifact.mp4':
   raw=b'fake-video-contract-output';self.send_response(200);self.end_headers();self.wfile.write(raw);return
  url='http://127.0.0.1:'+str(self.server.server_port)+'/artifact.mp4'
  if self.path.endswith('/status'):self.send({'status':'COMPLETED'});return
  self.send({'status':'succeeded','content':{'video_url':url},'task':{'status':'succeeded','content':{'url':url}},'output':url,'video':{'url':url}})
class CloudVideo(unittest.TestCase):
 setUp=fx.Portable.setUp
 req=fx.Portable.req
 def provider(self,protocol='minimax'):
  return {'id':'test-'+protocol,'name':'Test '+protocol,'protocol':protocol,'url':self.cloud_url,'model':'MiniMax-H3' if protocol=='minimax' else 'bytedance/seedance-2.5/reference-to-video' if protocol=='fal' else 'bytedance/seedance-2.5','resolution':'2K' if protocol=='minimax' else '720p','max_references':9,'api_key':'contract-only-secret','modes':['reference','first_frame','text']}
 def cloud(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),FakeCloud);server.calls=[];threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown);self.cloud_url='http://127.0.0.1:'+str(server.server_port);return server
 def test_credentials_redacted_preserved_and_cleared(self):
  self.cloud();p=self.provider();self.req('/api/settings',{'video_providers':[p]});data=self.req('/api/settings');self.assertNotIn('contract-only-secret',json.dumps(data));self.assertTrue(data['video_providers'][0]['key_configured'])
  self.req('/api/settings',{'video_providers':data['video_providers']});self.assertEqual(self.settings.read()['video_providers'][0]['api_key'],p['api_key'])
  data['video_providers'][0]['clear_key']=True;self.req('/api/settings',{'video_providers':data['video_providers']});self.assertFalse(self.req('/api/settings')['video_providers'][0]['key_configured'])
 def test_all_protocols_submit_poll_download_and_bind_selected_look(self):
  server=self.cloud()
  for protocol in ('ark','minimax','replicate','fal'):
   with self.subTest(protocol=protocol):
    provider=self.provider(protocol);self.req('/api/settings',{'video_providers':[provider]})
    cat=self.req('/api/model-catalog');model='cloud-'+provider['id'];self.assertIn(model,cat['strategies']['reference']['models']);self.assertIn(model,self.req('/api/video-modes')['first_frame'])
    p=self.req('/api/projects',{'name':'Cloud contract'});pid=p['id'];base='/api/projects/'+pid
    for name in ('face.png','look.png','scene.png'):(app.project(pid).parent/'media'/name).write_bytes(fx.PNG+name.encode())
    assets=[{'id':'person','type':'角色','name':'Person','image':f'/media/{pid}/media/face.png','default_look_id':'look','looks':[{'id':'look','name':'Uniform','image':f'/media/{pid}/media/look.png'}]},{'id':'scene','type':'场景','name':'Scene','image':f'/media/{pid}/media/scene.png'}]
    shot={'id':'s','title':'Test','duration':5,'asset_ids':['scene','person'],'character_looks':{'person':'look'},'video_prompt':'Person enters the scene.','versions':[]}
    self.req(base+'/save',{'assets':assets,'shots':[shot],'video_model':model,'video_mode':'reference','reset_epochs':p.get('reset_epochs',{})})
    preview=self.req(base+'/preview-prompt',{'shot_id':'s','kind':'video'})
    before=len(server.calls);job=self.req(base+'/generate',{'target':'shot','id':'s','kind':'video'})
    for _ in range(100):
     current=next(x for x in self.req(base+'/jobs') if x['id']==job['id'])
     if current['status'] in ('failed','completed'):break
     time.sleep(.02)
    self.assertEqual(current['status'],'completed',current);self.assertEqual(current['cloud_task_id'],'task1');self.assertEqual(current['transport'],'cloud')
    self.assertEqual([x['asset_id'] for x in current['image_inputs']],['scene','person']);self.assertTrue(current['source_images'][1].endswith('look.png'))
    calls=server.calls[before:];posts=[x for x in calls if x[0]=='POST'];self.assertEqual(len(posts),1)
    payload=posts[0][2].get('input',posts[0][2]);self.assertEqual(payload['content'][0]['text'] if 'content' in payload else payload['prompt'],preview['compiled_prompt']);self.assertEqual(payload['duration'],'5' if protocol=='fal' else 5)
    refs=[x['image_url']['url'] for x in payload['content'] if x['type']=='image_url'] if protocol in ('ark','minimax') else payload['image_urls' if protocol=='fal' else 'reference_images']
    self.assertNotEqual(refs[0],refs[1]);self.assertTrue(refs[0].startswith('data:image/'));self.assertIn('Scene',payload['content'][0]['text'] if 'content' in payload else payload['prompt'])
    self.assertEqual(len(self.req(base)['shots'][0]['versions']),1);self.assertNotIn('contract-only-secret',json.dumps(self.req(base+'/jobs')))
 def test_cloud_modes_with_legacy_local_descriptors(self):
  self.cloud();provider=self.provider('ark');self.settings.update({'video_providers':[provider]})
  legacy={'images':[],'videos':[{'id':'legacy-local','modes':['reference'],'supports_resolution':False}], 'strategies':{'reference':{'models':['legacy-local'],'inputs':['assets']},'first_frame':{'models':[],'inputs':['first_frame']}},'unmapped_videos':[]}
  with patch.object(app,'local_model_catalog',return_value=legacy):
   modes=self.req('/api/video-modes')
  self.assertIn('cloud-test-ark',modes['reference']);self.assertIn('legacy-local',modes['reference']);self.assertIn('cloud-test-ark',modes['first_frame'])
 def test_ark_mixed_media_roles_and_watermark(self):
  self.cloud();p=self.provider('ark');b={'prompt':'图片1中的人物跟随视频1动作，音频1作背景音乐。','duration':11,'image':['data:image/png;base64,YQ==','data:image/png;base64,Yg=='],'metadata':{'reference_videos':['https://example.org/signed.mp4'],'reference_audios':['data:audio/wav;base64,Yw==']}}
  data=c.payload(p,b);self.assertEqual([x.get('role') for x in data['content']],[None,'reference_image','reference_image','reference_video','reference_audio']);self.assertFalse(data['watermark'])
  with self.assertRaises(ValueError):c.payload(p,{**b,'first_frame_image':'data:image/png;base64,YQ=='})
 def test_signed_local_video_is_private_scoped_and_expires(self):
  import urllib.request,urllib.parse
  self.cloud();provider=self.provider('ark');provider['public_media_url']='https://studio.example.org';p=self.req('/api/projects',{'name':'Signed references'});pid=p['id'];url=f'/media/{pid}/media/ref.mp4'
  file=app.project(pid).parent/'media/ref.mp4';file.write_bytes(b'contract-only-video');self.settings.update({'access_password':'long-test-password'})
  j={'id':'b'*32,'kind':'video','status':'running','request':{'model':'cloud-test-ark','cloud_video_sources':[url]}}
  body=c.prepare_media(self.q,pid,j,provider);signed=body['metadata']['reference_videos'][0];parsed=urllib.parse.urlsplit(signed)
  with self.op.open(self.base+parsed.path+'?'+parsed.query,timeout=5) as r:self.assertEqual(r.read(),b'contract-only-video')
  with self.op.open(self.base+url,timeout=5) as response:self.assertIn('/login',response.url);self.assertNotEqual(response.read(),b'contract-only-video')
  with self.assertRaises(urllib.error.HTTPError):self.op.open(self.base+parsed.path+'?'+parsed.query.replace('signature=','signature=bad'),timeout=5)
  query=urllib.parse.parse_qs(parsed.query)
  with patch.object(c.time,'time',return_value=int(query['expires'][0])+1):
   with self.assertRaises(ValueError):c.granted_media(app.AppContext(),parsed.path,query)
  file.write_bytes(b'changed')
  with self.assertRaises(ValueError):c.granted_media(app.AppContext(),parsed.path,query)
 def test_missing_public_media_url_never_submits_video(self):
  self.cloud();p=self.provider('ark');j={'request':{'cloud_video_sources':['/media/x/media/ref.mp4']}}
  with self.assertRaisesRegex(ValueError,'公网HTTPS'):c.prepare_media(self.q,'x',j,p)
 def test_shot_launch_only_uses_explicit_media_flags(self):
  self.cloud();provider=self.provider('ark');provider['public_media_url']='https://studio.example.org';self.settings.update({'video_providers':[provider]})
  p=self.req('/api/projects',{'name':'Explicit references'});pid=p['id'];root=app.project(pid).parent/'media'
  for name in ('asset.png','voice.wav','motion.mp4'):(root/name).write_bytes(fx.PNG)
  image=f'/media/{pid}/media/asset.png';audio=f'/media/{pid}/media/voice.wav';video=f'/media/{pid}/media/motion.mp4'
  shot={'id':'s','title':'Test','duration':5,'asset_ids':['a'],'video_prompt':'Use audio 1 and video 1.','audio_source':{'type':'upload','url':audio},'reference_video':video}
  self.req('/api/projects/'+pid+'/save',{'video_mode':'reference','video_model':'cloud-test-ark','assets':[{'id':'a','type':'场景','name':'Room','image':image}],'shots':[shot],'reset_epochs':p.get('reset_epochs',{})})
  with patch.object(self.q,'reject_duplicate'),patch.object(self.q,'enqueue',side_effect=lambda pid,j:j):
   first=app.launch(pid,'shot','s','video');self.assertNotIn('cloud_video_sources',first['request']);self.assertNotIn('reference_audios',first['request'].get('metadata',{}))
   app.update(pid,lambda project:project['shots'][0].update(cloud_use_audio=True,cloud_use_video=True))
   second=app.launch(pid,'shot','s','video');self.assertEqual(second['request']['cloud_video_sources'],[video]);self.assertTrue(second['request']['metadata']['reference_audios'][0].startswith('data:audio/wav;'));self.assertEqual(second['source_audio'],audio);self.assertEqual(second['source_video'],video)
 def test_restart_reuses_remote_task_without_resubmitting(self):
  self.cloud();provider=self.provider();self.settings.update({'video_providers':[provider]});p=self.req('/api/projects',{'name':'Resume'});pid=p['id'];j={'id':'a'*32,'kind':'video','request':{'model':'cloud-test-minimax'},'cloud_task_id':'known-task','cloud_provider':{k:provider[k] for k in ('id','protocol','url','model')},'transport':'cloud','status':'running'};self.q.events[j['id']]=threading.Event()
  with patch.object(c,'submit') as submit,patch.object(c,'poll',return_value=('completed',self.cloud_url+'/artifact.mp4')),patch.object(app,'finish_job'),patch.object(self.q,'done') as done:
   c.run(self.q,pid,j);submit.assert_not_called();done.assert_called_once()
 def test_full_h3_resolution_and_duration_reject_before_paid_submission(self):
  self.cloud();p=self.provider();b={'prompt':'Test','duration':5}
  self.assertEqual(c.payload(p,b)['resolution'],'2K')
  for bad in ({'duration':3},{'duration':5.5},{'cloud_resolution':'720p'},{'image':['one']*10}):
   with self.assertRaises(ValueError):c.payload(p,{**b,**bad})
 def test_h3_running_stop_waits_for_upstream_without_deleting_output(self):
  self.cloud();p=self.provider()
  with patch.object(c,'poll',return_value=('running',None)),patch.object(c,'request') as req:
   self.assertFalse(c.cancel(p,'task1'));req.assert_not_called()
  with patch.object(c,'poll',return_value=('completed','https://example.org/video.mp4')),patch.object(c,'request') as req:
   self.assertTrue(c.cancel(p,'task1'));req.assert_not_called()
 def test_fal_queue_paths_use_base_model_and_not_generation_subpath(self):
  self.cloud();p=self.provider('fal');self.assertEqual(c.task_path(p,'task1'),'/bytedance/seedance-2.5/requests/task1')
 def test_submission_failure_is_not_retried(self):
  self.cloud();p=self.provider()
  with patch.object(c,'request',side_effect=ValueError('ambiguous')) as req:
   with self.assertRaises(ValueError):c.submit(p,{'prompt':'test','duration':5})
   self.assertEqual(req.call_count,1)
if __name__=='__main__':unittest.main()
