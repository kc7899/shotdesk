import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('shotdesk',Path(__file__).resolve().parents[2]/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ProjectDelete(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.patch=patch.object(m,'DATA',Path(self.tmp.name));self.patch.start();self.pid='c'*32;self.root=Path(self.tmp.name)/self.pid;(self.root/'jobs').mkdir(parents=True);(self.root/'media').mkdir();self.p={'id':self.pid,'name':'待删除项目','assets':[],'shots':[]};m.save(self.root/'project.json',self.p);(self.root/'media/file.png').write_bytes(b'media')
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def test_move_to_trash_and_hide_from_project_scan(self):
  result=m.delete_project(self.pid,'待删除项目');self.assertTrue(result['deleted']);self.assertFalse(self.root.exists());self.assertEqual(list(m.DATA.glob('*/project.json')),[]);archived=next((m.DATA/'.trash').iterdir());self.assertEqual((archived/'media/file.png').read_bytes(),b'media');self.assertEqual(json.loads((archived/'deletion.json').read_text())['project_id'],self.pid)
 def test_reject_wrong_confirmation(self):
  with self.assertRaises(ValueError):m.delete_project(self.pid,'其他项目')
  self.assertTrue(self.root.exists())
 def test_block_all_unfinished_states(self):
  for state in ('queued','running','cancelling'):
   with self.subTest(state=state),patch.object(m.Q,'list',return_value=[{'status':state}]),self.assertRaises(ValueError):m.delete_project(self.pid,'待删除项目')
  self.assertTrue(self.root.exists())
 def test_invalid_project_id_rejected(self):
  with self.assertRaises(ValueError):m.delete_project('../bad','待删除项目')
 def test_other_projects_preserved(self):
  other=m.DATA/('d'*32);other.mkdir();m.save(other/'project.json',dict(self.p,id='d'*32,name='其他项目'));m.delete_project(self.pid,'待删除项目');self.assertTrue((other/'project.json').exists())
if __name__=='__main__':unittest.main()
