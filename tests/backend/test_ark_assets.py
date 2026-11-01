"""Local HTTP checks for optional AIGC sync. No live upload or review is claimed."""
import hashlib,json,threading,time,unittest,urllib.parse,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from tests.backend import test_portable as fx
import ark_assets as aa
app=fx.app
class FakeArk(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  action=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)['Action'][0];body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));self.server.calls.append((action,body))
  if action=='CreateAssetGroup':
   assert body['GroupType']=='AIGC';result={'Id':'group-test'}
  elif action=='CreateAsset':
   assert body['AssetType']=='Image';parsed=urllib.parse.urlsplit(body['URL'])
   with urllib.request.urlopen(self.server.studio+parsed.path+'?'+parsed.query,timeout=5) as r:assert r.read().startswith(b'\x89PNG')
   result={'Id':'asset-'+str(len(self.server.calls))}
  else:result={'Id':body['Id'],'Status':self.server.status,'Error':{'Code':'ContentRestricted'} if self.server.status=='Failed' else {}}
  data=json.dumps({'Result':result}).encode();self.send_response(200);self.end_headers();self.wfile.write(data)
class ArkAssets(unittest.TestCase):
 setUp=fx.Portable.setUp
 req=fx.Portable.req
 def setup_ark(self):
  service=ThreadingHTTPServer(('127.0.0.1',0),FakeArk);service.calls=[];service.status='Active';service.studio=self.base;threading.Thread(target=service.serve_forever,daemon=True).start();self.addCleanup(service.shutdown);self.addCleanup(service.server_close)
  guard=patch.object(aa,'ENDPOINT','http://127.0.0.1:'+str(service.server_port));guard.start();self.addCleanup(guard.stop)
  profile={'id':'ark','protocol':'ark','url':'https://ark.cn-beijing.volces.com/api/v3','model':'doubao-seedance-2-0-260128','api_key':'video-private-key','asset_access_key':'AK-private-test','asset_secret_key':'SK-private-test','asset_project':'default','public_media_url':'https://studio.example.org','resolution':'720p','modes':['reference'],'max_references':9}
  self.req('/api/settings',{'video_providers':[profile]});self.provider=self.settings.read()['video_providers'][0]
  p=self.req('/api/projects',{'name':'Asset sync'});self.pid=p['id'];self.image=f'/media/{self.pid}/media/character.png';(app.project(self.pid).parent/'media/character.png').write_bytes(fx.PNG)
  self.req('/api/projects/'+self.pid+'/save',{'assets':[{'id':'a','type':'角色','name':'Test character','image':self.image,'default_look_id':'look','looks':[{'id':'look','name':'Default look','image':self.image}]}],'reset_epochs':p.get('reset_epochs',{})})
  return service
 def sync(self,resource='look'):
  job=self.req('/api/projects/'+self.pid+'/sync-ark-asset',{'resource_id':resource,'model':'cloud-ark'})
  for _ in range(200):
   current=next(x for x in self.req('/api/projects/'+self.pid+'/jobs') if x['id']==job['id'])
   if current['status'] in ('completed','failed'):return current
   time.sleep(.02)
  self.fail('Sync job did not terminate')
 def test_sync_review_reference_and_refresh_without_reupload(self):
  service=self.setup_ark();job=self.sync();self.assertEqual(job['status'],'completed',job)
  item={'asset_id':'a','look_id':'look','name':'Test character','url':self.image};self.assertTrue(aa.image_input(app.AppContext(),self.pid,self.provider,item).startswith('asset://asset-'))
  self.assertEqual([x[0] for x in service.calls],['CreateAssetGroup','CreateAsset','GetAsset'])
  app.update(self.pid,lambda p:p.update(video_model='cloud-ark',video_mode='reference',shots=[{'id':'s','title':'Test','duration':5,'video_prompt':'The character enters.','asset_ids':['a'],'character_looks':{'a':'look'},'versions':[]}]))
  with patch.object(self.q,'reject_duplicate'),patch.object(self.q,'enqueue',side_effect=lambda pid,j:j):submitted=app.launch(self.pid,'shot','s','video')
  self.assertTrue(submitted['request']['image'][0].startswith('asset://'));self.assertEqual(submitted['image_inputs'][0]['url'],self.image)
  self.assertEqual(self.sync()['status'],'completed');self.assertEqual([x[0] for x in service.calls].count('CreateAsset'),1)
  old=aa.read(app.AppContext(),self.pid)['resources']['ark:look']['asset_id'];new=f'/media/{self.pid}/media/new.png';(app.project(self.pid).parent/'media/new.png').write_bytes(fx.PNG+b'new')
  app.update(self.pid,lambda p:p['assets'][0]['looks'][0].update(image=new))
  self.assertTrue(self.req('/api/projects/'+self.pid+'/ark-assets')['resources']['ark:look']['stale'])
  with self.assertRaisesRegex(ValueError,'重新同步'):aa.image_input(app.AppContext(),self.pid,self.provider,{**item,'url':new})
  self.assertEqual(aa.read(app.AppContext(),self.pid)['resources']['ark:look']['asset_id'],old)
 def test_secrets_not_returned_and_blank_keeps_credentials(self):
  self.setup_ark();settings=self.req('/api/settings');raw=json.dumps(settings)
  for value in ('video-private-key','AK-private-test','SK-private-test'):self.assertNotIn(value,raw)
  self.assertTrue(settings['video_providers'][0]['asset_credentials_configured']);self.req('/api/settings',{'video_providers':settings['video_providers']});self.assertEqual(self.settings.read()['video_providers'][0]['asset_secret_key'],'SK-private-test')
 def test_review_rejection_visible_and_no_reupload_loop(self):
  service=self.setup_ark();service.status='Failed';job=self.sync();self.assertEqual(job['status'],'failed');self.assertIn('ContentRestricted',job['error']);self.assertEqual(self.sync()['status'],'failed');self.assertEqual([x[0] for x in service.calls].count('CreateAsset'),1)
 def test_control_plane_error_is_actionable_and_sanitized(self):
  import io,cloud_video
  error=urllib.error.HTTPError('https://example.org',403,'Forbidden',{},io.BytesIO(json.dumps({'ResponseMetadata':{'Error':{'Code':'AccessDenied','Message':'Missing Ark permission'},'RequestId':'req-ark'}}).encode()))
  message=cloud_video.provider_error(error,'secret');self.assertIn('AccessDenied',message);self.assertIn('Missing Ark permission',message);self.assertIn('req-ark',message)
 def test_signature_matches_official_sdk_reference_vector(self):
  _,_,headers=aa.sign('CreateAssetGroup',{'Name':'Example','GroupType':'AIGC','ProjectName':'default'},'AK-test','SK-test','20261102T080000Z')
  # Independently checked against volcengine/auth/SignerV4.py, not an app-generated expectation.
  self.assertTrue(headers['Authorization'].endswith('Signature=4df2b42f7f55f4db3f23b5a6e5a89b64619701317fff13d366540189047d53b9'))
 def test_same_character_identity_and_look_share_group(self):
  service=self.setup_ark();self.assertEqual(self.sync()['status'],'completed');self.assertEqual(self.sync('a')['status'],'completed');self.assertEqual([x[0] for x in service.calls].count('CreateAssetGroup'),1);self.assertEqual([x[0] for x in service.calls].count('CreateAsset'),2)
 def test_prerequisites_fail_before_upload(self):
  service=self.setup_ark();self.settings.update({'video_providers':[{**self.provider,'clear_asset_credentials':True}]})
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/projects/'+self.pid+'/sync-ark-asset',{'resource_id':'look','model':'cloud-ark'})
  self.assertEqual(service.calls,[])
 def test_ambiguous_create_does_not_retry(self):
  self.setup_ark()
  with patch.object(aa,'call',side_effect=ValueError('uncertain')) as call:
   self.assertEqual(self.sync()['status'],'failed');self.assertEqual(self.sync()['status'],'failed');self.assertEqual(call.call_count,1)
if __name__=='__main__':unittest.main()
