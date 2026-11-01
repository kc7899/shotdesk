"""Focused contracts: literal request transport, edit concurrency, local reference boundary."""
import importlib.util,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('shotdesk',Path(__file__).resolve().parents[2]/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Contracts(unittest.TestCase):
 def test_background_result_survives_prompt_edit(self):
  p={'assets':[],'shots':[{'id':'s','image':'new.png','versions':[{'id':'v2'}]}]}
  m.merge_save(p,{'shots':[{'id':'s','image':'old.png','image_prompt':'edited','versions':[{'id':'v1'}]}],'_media_base':{'s':{'image':'old.png'}}})
  self.assertEqual(p['shots'][0]['image'],'new.png');self.assertEqual(len(p['shots'][0]['versions']),2)
 def test_deliberate_version_selection_preserved(self):
  p={'assets':[],'shots':[{'id':'s','image':'new.png','versions':[]}]}
  m.merge_save(p,{'shots':[{'id':'s','image':'older.png','versions':[]}],'_media_base':{'s':{'image':'new.png'}}})
  self.assertEqual(p['shots'][0]['image'],'older.png')
 def test_reference_path_boundary(self):
  with self.assertRaises(ValueError):m.local_file('/media/../../server.py')
 def test_literal_prompt_and_duration(self):
  with tempfile.TemporaryDirectory() as d, patch.object(m,'DATA',Path(d)):
   pid='a'*32;root=Path(d)/pid;(root/'jobs').mkdir(parents=True);(root/'media').mkdir()
   text='  Keep EXACT wording.\n中文台词「再见」。  '
   m.save(root/'project.json',{'name':'contract','assets':[],'shots':[{'id':'s','image_prompt':text,'duration':3}],'image_model':'Flux2-Klein-4B-4step-1K','ratio':'16:9'})
   with patch.object(m.threading,'Thread'):
    j=m.launch(pid,'shot','s','image')
   j=json.loads(m.job_path(pid,j['id']).read_text());self.assertEqual(j['request']['prompt'],text)
   with self.assertRaises(ValueError):m.launch(pid,'shot','s','image')
class DurationContracts(unittest.TestCase):
 def test_duration_edit_only_changes_metadata(self):
  old={'duration':4,'video_prompt':'Duration: 4s\nAt 2 seconds, turn left. 台词保持。'}
  shot=dict(old,duration=5.5);m.sync_duration(shot,old)
  self.assertEqual(shot['video_prompt'],'Duration: 5.5s\nAt 2 seconds, turn left. 台词保持。')
 def test_prompt_edit_updates_numeric_field(self):
  old={'duration':4,'video_prompt':'Duration: 4s\nAct.'}
  shot=dict(old,video_prompt='Duration: 6.5s\nAct.');m.sync_duration(shot,old)
  self.assertEqual(shot['duration'],6.5)
 def test_missing_duration_derived_from_prompt(self):
  shot={'video_prompt':'时长：3.5秒\nMove.'};m.sync_duration(shot)
  self.assertEqual(shot,{'duration':3.5,'video_prompt':'Duration: 3.5s\nMove.'})
 def test_numeric_wins_when_both_change(self):
  shot={'duration':7,'video_prompt':'Duration: 6s\nAct.'};m.sync_duration(shot,{'duration':4,'video_prompt':'Duration: 4s\nAct.'})
  self.assertEqual(shot['video_prompt'],'Duration: 7s\nAct.')
 def test_invalid_duration_rejected(self):
  for value in ('',0,-1,True,'abc',float('nan'),float('inf')):
   with self.subTest(value=value),self.assertRaises(ValueError):m.sync_duration({'duration':value})
 def test_duration_has_no_platform_ten_second_ceiling(self):
  for value in (0.5,1,11,15,30,120):
   shot={'duration':value,'video_prompt':'A quiet room.'};m.sync_duration(shot);self.assertEqual(shot['duration'],value);self.assertIn(f'Duration: {value:g}s',shot['video_prompt'])
 def test_new_model_output_gets_line_without_rewriting(self):
  shot={'duration':3,'video_prompt':'Keep this exactly. 中文。'};m.sync_duration(shot)
  self.assertEqual(shot['video_prompt'],'Duration: 3s\nKeep this exactly. 中文。')
class GenerationDurationContract(unittest.TestCase):
 def test_synced_duration_reaches_generation_request(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'DATA',Path(d)):
   pid='b'*32;root=Path(d)/pid;(root/'jobs').mkdir(parents=True);(root/'media').mkdir()
   p={'name':'contract','assets':[],'shots':[{'id':'s','duration':4,'video_prompt':'Duration: 4s\nAct.','image':'/media/local.png'}],'video_model':'MiniMaxH3-8step-I2V','ratio':'16:9'}
   m.merge_save(p,{'shots':[dict(p['shots'][0],video_prompt='Duration: 6.5s\nAct.')]});m.save(root/'project.json',p)
   with patch.object(m.threading,'Thread'),patch.object(m,'reference',return_value='data:image/png;base64,dGVzdA=='):
    job=m.launch(pid,'shot','s','video')
   job=json.loads(m.job_path(pid,job['id']).read_text());self.assertEqual(job['request']['duration'],6.5)
   self.assertEqual(job['request']['prompt'],'Duration: 6.5s\nAct.')
if __name__=='__main__':unittest.main()
