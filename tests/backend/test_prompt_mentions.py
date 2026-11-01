import unittest,copy,tempfile
from pathlib import Path
from unittest.mock import patch
import server as m
class PromptMentions(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);fix=patch.object(m,'DATA',Path(t.name));fix.start();self.addCleanup(fix.stop);self.pid='a'*32;m.project(self.pid).parent.mkdir()
  self.p={'id':self.pid,'name':'neutral','ratio':'16:9','image_model':'Qwen-Image-2.1-RedCraft-FixQW21T-FP8-8plus8step-2K','video_mode':'reference','video_model':'MiniMaxH3-RedCraft-A2A-beta1-8step-R2V-2K','assets':[{'id':'actor','name':'男主','type':'角色','image':'/face.png','default_look_id':'casual','looks':[{'id':'casual','name':'日常','image':'/casual.png','versions':[{'id':'look-v','kind':'image','url':'/casual.png'}]},{'id':'suit','name':'正装','image':'/suit.png'}]},{'id':'room','name':'客厅','type':'场景','image':'/room.png'},{'id':'cup','name':'杯子','type':'道具','image':'/cup.png'},{'id':'sound','name':'声音','type':'音频'}],'shots':[{'id':'s','title':'neutral','duration':4,'video_prompt':'Duration: 4s\n在@客厅，@男主·日常说：“你好”。','image_prompt':'@男主·日常站在@客厅。','asset_ids':['cup'],'versions':[]}]}
  self.shot=self.p['shots'][0]
 def launch(self,kind='video'):
  m.save(m.project(self.pid),self.p)
  with patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',side_effect=lambda u:'bytes:'+u):return m.launch(self.pid,'shot','s',kind)
 def test_save_binds_real_resources_and_keeps_manual_order(self):
  m.merge_save(self.p,{'shots':copy.deepcopy(self.p['shots'])});s=self.p['shots'][0];self.assertEqual(s['asset_ids'],['cup','actor','room']);self.assertEqual(s['character_looks'],{'actor':'casual'});self.assertEqual(s['prompt_mentions']['男主·日常']['look_id'],'casual');self.assertIn('@男主·日常',s['video_prompt'])
 def test_video_and_image_compile_against_actual_image_order(self):
  for kind in ['video','image']:
   j=self.launch(kind);self.assertNotIn('@',j['request']['prompt']);self.assertIn('参考图2中的男主（日常）',j['request']['prompt']);self.assertIn('参考图3中的客厅',j['request']['prompt']);self.assertEqual(j['request']['image'],['bytes:/cup.png','bytes:/casual.png','bytes:/room.png']);self.assertIn('@男主·日常',j['original_prompt'])
 def test_rename_preserves_id_and_original_template(self):
  m.sync_shot_mentions(self.p,self.shot);self.p['assets'][0]['name']='新名字';self.p['assets'][0]['looks'][0]['name']='新日常';compiled,_=m.compile_shot_prompt(self.p,self.shot,'video',m.image_resources(self.p,self.shot));self.assertIn('新名字（新日常）',compiled);self.assertIn('@男主·日常',self.shot['video_prompt'])
 def test_two_looks_for_one_actor_rejected(self):
  self.shot['video_prompt']+=' @男主·正装'
  with self.assertRaisesRegex(ValueError,'两个不同造型'):m.sync_shot_mentions(self.p,self.shot)
 def test_unknown_mention_is_draft_but_blocks_launch(self):
  self.shot['video_prompt']+=' @不存在';m.sync_shot_mentions(self.p,self.shot)
  with self.assertRaisesRegex(ValueError,'无法识别引用'):self.launch()
 def test_unknown_look_does_not_partially_match_actor(self):
  with self.assertRaisesRegex(ValueError,'无法识别引用'):m.scan_prompt_mentions(self.p,self.shot,'@男主·不存在',True)
 def test_email_escaped_at_and_plain_text_unchanged(self):
  text='Contact a@example.com. @@ordinary-user';self.assertEqual(m.scan_prompt_mentions(self.p,self.shot,text,True),[]);self.shot['video_prompt']=text;compiled,_=m.compile_shot_prompt(self.p,self.shot,'video',[]);self.assertEqual(compiled,'Contact a@example.com. @ordinary-user')
 def test_duplicate_names_require_pinned_identity(self):
  self.p['assets'].append({'id':'other','name':'客厅','type':'场景','image':'/other.png'})
  with self.assertRaisesRegex(ValueError,'重名'):m.scan_prompt_mentions(self.p,self.shot,'@客厅',True)
  self.shot['prompt_mentions']={'客厅':{'asset_id':'other','look_id':None}};self.assertEqual(m.scan_prompt_mentions(self.p,self.shot,'@客厅',True)[0]['asset_id'],'other')
 def test_removed_asset_or_look_fails_instead_of_guessing(self):
  m.sync_shot_mentions(self.p,self.shot);self.p['assets'][0]['looks']=[]
  with self.assertRaisesRegex(ValueError,'造型已删除'):m.sync_shot_mentions(self.p,self.shot)
 def test_removed_text_does_not_remove_manual_links(self):
  m.sync_shot_mentions(self.p,self.shot);ids=list(self.shot['asset_ids']);self.shot.update(image_prompt='A room.',video_prompt='Duration: 4s\nA room.');m.sync_shot_mentions(self.p,self.shot);self.assertEqual(self.shot['asset_ids'],ids)
 def test_first_frame_video_does_not_pretend_to_send_asset_refs(self):
  self.p.update(video_mode='first_frame',video_model='MiniMaxH3-8step-I2V');self.shot['image']='/still.png'
  with self.assertRaisesRegex(ValueError,'不直接传入资产'):self.launch()
 def test_missing_unmentioned_image_cannot_shift_indices(self):
  self.p['assets'][2]['image']=None
  with self.assertRaisesRegex(ValueError,'改变参考图序'):self.launch('image')
 def test_preview_does_not_mutate_project_or_submit(self):
  m.save(m.project(self.pid),self.p);before=m.project(self.pid).read_bytes()
  with patch.object(m.Q,'enqueue') as enqueue:r=m.preview_shot_prompt(self.pid,{'shot_id':'s','kind':'video'})
  self.assertIn('参考图2中的男主',r['compiled_prompt']);self.assertEqual(m.project(self.pid).read_bytes(),before);enqueue.assert_not_called()
 def test_version_preserves_template_and_resolved_bindings(self):
  j=self.launch()
  with patch.object(m,'job_save'):m.finish_job(self.pid,j,'/clip.mp4')
  v=m.load(self.pid)['shots'][0]['versions'][0];self.assertIn('@',v['original_prompt']);self.assertEqual(v['reference_bindings'][0]['reference_index'],3)
 def test_incomplete_at_blocks_submission(self):
  self.shot['video_prompt']='Duration: 4s\nA room @'
  with self.assertRaisesRegex(ValueError,'无法识别引用'):self.launch()
 def test_preview_enforces_reference_count(self):
  self.p['video_model']='MiniMaxH3-RedCraft-Package-4step-R2V-1K'
  for n in range(3):self.p['assets'].append({'id':str(n),'name':'道具'+str(n),'type':'道具','image':'/prop.png'})
  self.shot['asset_ids']=['cup','actor','room','0','1','2'];m.save(m.project(self.pid),self.p)
  with self.assertRaisesRegex(ValueError,'模型上限'):m.preview_shot_prompt(self.pid,{'shot_id':'s'})
 def test_first_frame_preview_lists_only_actual_first_frame(self):
  self.p.update(video_mode='first_frame',video_model='MiniMaxH3-8step-I2V');self.shot.update(video_prompt='Duration: 4s\nA person speaks.',image='/still.png');m.save(m.project(self.pid),self.p)
  result=m.preview_shot_prompt(self.pid,{'shot_id':'s','kind':'video'});self.assertEqual(result['image_inputs'],[{'asset_id':None,'name':'当前首帧','url':'/still.png'}])
if __name__=='__main__':unittest.main()
