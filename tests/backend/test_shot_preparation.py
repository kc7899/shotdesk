import copy,json,unittest
from types import SimpleNamespace
from unittest.mock import Mock
import shot_preparation as sp
class ShotPreparation(unittest.TestCase):
 def setUp(self):
  self.p={'assets':[{'id':'a','name':'Alex','type':'角色','default_look_id':'l','looks':[{'id':'l','name':'Work'}]}],
    'shots':[{'id':'s','title':'One','description':'Alex enters.','duration':4,'asset_ids':[],'character_looks':{},'video_prompt':'','image_prompt':''},
             {'id':'t','title':'Two','description':'Alex waits.','duration':4,'asset_ids':[],'character_looks':{},'video_prompt':'','image_prompt':''}], 'video_model':'test','video_mode':'reference','prompt_language':'zh'}
  self.q=SimpleNamespace(check=Mock(),persist=Mock(),text_request=Mock())
  self.api=SimpleNamespace(Q=self.q,load=lambda pid:copy.deepcopy(self.p),update=lambda pid,fn:fn(self.p),LOCK=__import__('threading').RLock(),video_mode=lambda s,p:'reference',video_model=lambda s,p:'test',sync_shot_mentions=lambda p,s,strict:None)
  self.j={'id':'j','model':'llm','shot_ids':['s','t'],'scope':'missing','preparation_operation':'prepare','preparation_results':[]}
 def response(self,obj):return {'choices':[{'message':{'content':json.dumps(obj)},'finish_reason':'stop'}]}
 def test_chain_partial_failure_progress_and_resume(self):
  match={'asset_ids':['a'],'character_looks':{'a':'l'},'warnings':[]};prompt={'video_prompt':'0–4s Alex enters.','image_prompt':'Alex in doorway.','warnings':[]}
  self.q.text_request.side_effect=[self.response(match),self.response(prompt),ValueError('offline')]
  result=sp.run(self.api,'p',self.j)
  self.assertEqual(result['completed'],1);self.assertEqual(result['failed'],1);self.assertEqual(self.p['shots'][0]['asset_ids'],['a']);self.assertTrue(self.p['shots'][0]['video_prompt'].startswith('Duration: 4s'))
  self.q.text_request.side_effect=[self.response(match),self.response(prompt)]
  result=sp.run(self.api,'p',self.j)
  self.assertTrue(any(r['shot_id']=='t' and r['status']=='completed' for r in self.j['preparation_results']))
  self.assertEqual(self.q.text_request.call_count,5)
 def test_manual_results_preserved_default_and_explicit_overwrite(self):
  s=self.p['shots'][0];s.update(asset_ids=['a'],character_looks={'a':'l'},video_prompt='My manual prompt',image_prompt='Keep my image')
  self.j['shot_ids']=['s'];sp.run(self.api,'p',self.j);self.q.text_request.assert_not_called();self.assertEqual(s['video_prompt'],'My manual prompt')
 def test_current_description_invalidates_prepared_result(self):
  s=self.p['shots'][0];s['preparation']={'assets':{'input':sp.fingerprint(self.p,s,'assets'),'output':sp.output_hash(s,'assets')}}
  self.assertTrue(sp.current(self.p,s,'assets'));s['description']='Alex exits.';self.assertFalse(sp.current(self.p,s,'assets'))
 def test_invalid_look_never_committed(self):
  self.q.text_request.return_value=self.response({'asset_ids':['a'],'character_looks':{'a':'somebody-elses-look'},'warnings':[]})
  self.j.update(shot_ids=['s'],preparation_operation='assets');sp.run(self.api,'p',self.j)
  self.assertEqual(self.p['shots'][0]['asset_ids'],[]);self.assertEqual(self.j['preparation_results'][0]['status'],'failed');self.assertEqual(self.q.text_request.call_count,2)
 def test_concurrent_edit_is_preserved(self):
  def answer(*args):self.p['shots'][0]['description']='User edit';return self.response({'asset_ids':['a'],'character_looks':{'a':'l'},'warnings':[]})
  self.q.text_request.side_effect=answer;self.j.update(shot_ids=['s'],preparation_operation='assets');sp.run(self.api,'p',self.j)
  self.assertEqual(self.p['shots'][0]['asset_ids'],[]);self.assertIn('已被修改',self.j['preparation_results'][0]['error'])
 def test_stop_never_swallowed(self):
  self.q.check.side_effect=RuntimeError('stop')
  with self.assertRaisesRegex(RuntimeError,'stop'):sp.run(self.api,'p',self.j)

from tests.backend import test_portable as fixture
from unittest.mock import patch
import server as server
class PreparationHTTP(unittest.TestCase):
 setUp=fixture.Portable.setUp
 req=fixture.Portable.req
 def test_real_queue_prepares_one_shot_without_touching_other_media(self):
  p=self.req('/api/projects',{'name':'Preparation test'});pid=p['id']
  server.update(pid,lambda p:p.update(assets=[{'id':'a','name':'Alex','type':'角色','looks':[{'id':'l','name':'Work'}],'default_look_id':'l'}],shots=[{'id':'s','title':'One','description':'Alex enters.','duration':4,'asset_ids':[],'versions':[],'image_prompt':'','video_prompt':''},{'id':'t','title':'Keep','description':'Unchanged','duration':4,'asset_ids':[],'versions':[],'video':'existing.mp4'}]))
  def reply(body,j):
   value={'asset_ids':['a'],'character_looks':{'a':'l'},'warnings':[]} if '匹配员' in body['messages'][0]['content'] else {'video_prompt':'0–4秒 @Alex·Work 进入房间。','image_prompt':'@Alex·Work 站在门口。','warnings':[]}
   return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}
  import time
  with patch.object(server,'llm_model',return_value='mock-llm'),patch.object(self.q,'text_request',side_effect=reply):
   job=self.req('/api/projects/'+pid+'/prepare-shots',{'operation':'prepare','shot_ids':['s']})
   for _ in range(200):
    row=next(j for j in self.req('/api/projects/'+pid+'/jobs') if j['id']==job['id'])
    if row['status'] not in ('queued','running','cancelling'):break
    time.sleep(.01)
  self.assertEqual(row['status'],'completed',row);self.assertEqual(row['result']['failed'],0,row)
  p=self.req('/api/projects/'+pid);self.assertEqual(p['shots'][0]['asset_ids'],['a']);self.assertIn('@Alex·Work',p['shots'][0]['video_prompt']);self.assertEqual(p['shots'][1]['video'],'existing.mp4')
 def test_existing_orphan_does_not_block_asset_save_but_new_orphan_rejected(self):
  p=self.req('/api/projects',{'name':'Legacy links'});pid=p['id']
  server.update(pid,lambda p:p.update(shots=[{'id':'s','title':'Legacy','asset_ids':['old-missing'],'duration':4,'description':'A room','versions':[]}]))
  body=self.req('/api/projects/'+pid);body['assets'].append({'id':'a','name':'Alex','type':'角色','looks':[{'id':'l','name':'Work'}],'default_look_id':'l'})
  self.req('/api/projects/'+pid+'/save',body);self.assertEqual(len(self.req('/api/projects/'+pid)['assets']),1)
  body=self.req('/api/projects/'+pid);body['shots'][0]['asset_ids'].append('new-missing')
  import urllib.error
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/projects/'+pid+'/save',body)
