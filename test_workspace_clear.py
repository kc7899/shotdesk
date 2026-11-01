import copy,json,unittest
from unittest.mock import patch
import test_queue
m=test_queue.m

class WorkspaceClearContracts(unittest.TestCase):
 setUp=test_queue.QueueContracts.setUp
 tearDown=test_queue.QueueContracts.tearDown
 def prepare(self):
  m.update(self.pid,lambda p:p.update(script='保留剧本',film='film.mp4',assets=[{'id':'person','name':'林岚','type':'角色','prompt':'角色描述','image':'face.png','versions':[],'looks':[{'id':'look','name':'常服','prompt':'衬衫','image':'look.png','versions':[]}],'default_look_id':'look','voices':[{'id':'voice','name':'默认声线','asset_id':'sound'}],'default_voice_id':'voice'},{'id':'room','name':'客厅','type':'场景','prompt':'场景','versions':[]},{'id':'sound','name':'声音','type':'音频','audio':'voice.wav','versions':[]}],shots=[{'id':'shot','title':'镜头','duration':6,'image':'frame.png','video':'clip.mp4','audio':'dialogue.wav','versions':[],'asset_ids':['person','room'],'character_looks':{'person':'look'},'prompt_mentions':{'林岚·常服':{'asset_id':'person','look_id':'look'}},'image_prompt':'@林岚·常服 在 @客厅','video_prompt':'@林岚·常服 说话，@客厅。联系 a@b.com，@@普通符号','speaker_id':'person','voice_id':'voice','audio_source':{'type':'asset','asset_id':'sound'}}]))
  (self.root/'media'/'keep.png').write_bytes(b'keep')
  return m.load(self.pid)
 def clear(self,kind):
  p=m.load(self.pid);return m.clear_workspace(self.pid,kind,{'confirm_name':p['name'],'expected_updated':p['updated']})
 def test_clear_shots_preserves_assets_script_and_files(self):
  before=self.prepare();result=self.clear('shots');after=result['project'];self.assertEqual(after['shots'],[]);self.assertEqual(after['assets'],before['assets']);self.assertEqual(after['script'],before['script']);self.assertNotIn('film',after);self.assertTrue((self.root/'media'/'keep.png').is_file());self.assertFalse(result['media_files_deleted']);self.assertEqual(after['reset_epochs']['shots'],1)
  backup=json.loads((m.DATA/result['backup_file']).read_text());self.assertEqual(backup,before)
 def test_clear_assets_detaches_links_and_keeps_shot_media(self):
  before=self.prepare();result=self.clear('assets');after=result['project'];self.assertEqual(after['assets'],[]);self.assertEqual(after['script'],before['script']);self.assertEqual(after['film'],before['film']);shot=after['shots'][0]
  for field in ('image','video','audio','versions','title'):self.assertEqual(shot[field],before['shots'][0][field])
  self.assertEqual(shot['asset_ids'],[]);self.assertEqual(shot['character_looks'],{});self.assertEqual(shot['prompt_mentions'],{});self.assertNotIn('speaker_id',shot);self.assertNotIn('voice_id',shot);self.assertIsNone(shot['audio_source']);self.assertEqual(shot['image_prompt'],'林岚·常服 在 客厅');self.assertIn('a@b.com，@@普通符号',shot['video_prompt']);m.validate_resources(after)
 def test_uploaded_audio_source_is_preserved(self):
  self.prepare();m.update(self.pid,lambda p:p['shots'][0].update(audio_source={'type':'upload','url':'reference.wav'}));after=self.clear('assets')['project'];self.assertEqual(after['shots'][0]['audio_source'],{'type':'upload','url':'reference.wav'})
 def test_clear_requires_name_and_current_revision(self):
  before=self.prepare()
  for body in ({},{'confirm_name':'wrong','expected_updated':before['updated']},{'confirm_name':before['name'],'expected_updated':0}):
   with self.assertRaises(ValueError):m.clear_workspace(self.pid,'shots',body)
  self.assertEqual(m.load(self.pid),before);self.assertFalse((self.root/'backups').exists())
 def test_any_active_project_task_blocks_clear(self):
  self.prepare()
  for kind in ('text','image','video','audio','compose'):
   with self.subTest(kind=kind):
    job=test_queue.QueueContracts.job(self,kind=kind)
    with self.assertRaisesRegex(ValueError,'未结束任务'):self.clear('assets')
    m.job_path(self.pid,job['id']).unlink()
 def test_terminal_history_does_not_block_or_get_deleted(self):
  self.prepare();job=test_queue.QueueContracts.job(self,kind='image',status='completed');path=m.job_path(self.pid,job['id']);before=path.read_bytes();self.clear('shots');self.assertEqual(path.read_bytes(),before)
 def test_other_project_activity_is_not_cleared_or_blocked(self):
  self.prepare();other='b'*32;root=m.DATA/other;(root/'jobs').mkdir(parents=True);m.save(root/'project.json',dict(m.load(self.pid),id=other));m.job_save(other,{'id':'other','kind':'text','status':'running','target_id':'project'});self.clear('shots');self.assertEqual(len(m.load(other)['shots']),1)
 def test_stale_browser_cannot_restore_shots(self):
  old=self.prepare();self.clear('shots')
  with self.assertRaisesRegex(ValueError,'分镜已清空'):m.update(self.pid,lambda p:m.merge_save(p,old))
  self.assertEqual(m.load(self.pid)['shots'],[])
 def test_stale_browser_cannot_restore_assets(self):
  old=self.prepare();self.clear('assets')
  with self.assertRaisesRegex(ValueError,'参考资产已清空'):m.update(self.pid,lambda p:m.merge_save(p,old))
  self.assertEqual(m.load(self.pid)['assets'],[])
 def test_fresh_save_after_clear_is_allowed(self):
  self.prepare();self.clear('assets');fresh=m.load(self.pid);fresh['script']='修改后的剧本';m.update(self.pid,lambda p:m.merge_save(p,fresh));self.assertEqual(m.load(self.pid)['script'],'修改后的剧本')
 def test_old_candidate_cannot_recreate_cleared_assets(self):
  before=self.prepare();job={'id':m.uid(),'operation':'extract_assets','kind':'text','status':'completed','result':{'source_script':before['script'],'prompt_skill':{'name':'skill'},'candidates':[]}};m.job_save(self.pid,job);self.clear('assets')
  with self.assertRaisesRegex(ValueError,'资产已清空'):m.apply_asset_extraction(self.pid,{'job_id':job['id'],'selections':[]})
 def test_late_storyboard_result_cannot_undo_empty_clear(self):
  self.prepare();m.update(self.pid,lambda p:p.update(shots=[]));snapshot=m.load(self.pid);self.clear('shots');job={'id':m.uid(),'kind':'text','target':'project','target_id':'project','status':'queued','operation':'generate_storyboard','model':'local','snapshot':snapshot}
  with patch.object(m,'plan_storyboard',return_value={'shots':[{'id':'new'}]}):self.q.worker(self.pid,job)
  self.assertEqual(m.load(self.pid)['shots'],[]);self.assertEqual(json.loads(m.job_path(self.pid,job['id']).read_text())['status'],'failed')

if __name__=='__main__':unittest.main()
