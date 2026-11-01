import importlib.util,json,tempfile,unittest,datetime,time
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('shotdesk',Path(__file__).with_name('server.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class TrashTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.patch=patch.object(m,'DATA',Path(self.temp.name));self.patch.start();self.now=time.time();self.manager=m.TrashManager(m.AppContext())
 def tearDown(self):self.patch.stop();self.temp.cleanup()
 def archive(self,pid='a'*32,age=1):
  folder=m.DATA/pid;(folder/'jobs').mkdir(parents=True);(folder/'media').mkdir();m.save(folder/'project.json',{'id':pid,'name':'Trash '+pid[:1],'assets':[],'shots':[]});(folder/'media/test.png').write_bytes(b'keep pixels');m.delete_project(pid,'Trash '+pid[:1]);entry=next((m.DATA/'.trash').glob(pid+'-*'));meta=json.loads((entry/'deletion.json').read_text());meta['deleted_at']=self.now-age*86400;m.save(entry/'deletion.json',meta);return entry
 def test_auto_only_removes_seven_day_old_projects(self):
  old=self.archive(age=8);recent=self.archive('b'*32,age=6);result=self.manager.purge(automatic=True,now=self.now);self.assertEqual(result['count'],1);self.assertFalse(old.exists());self.assertTrue(recent.exists());self.assertEqual(self.manager.logs()[0]['action'],'automatic_cleanup')
 def test_restore_retains_project_id_and_files(self):
  entry=self.archive();result=self.manager.restore(entry.name);self.assertEqual(result['project_id'],'a'*32);self.assertEqual((m.DATA/('a'*32)/'media/test.png').read_bytes(),b'keep pixels');self.assertFalse((m.DATA/('a'*32)/'deletion.json').exists());self.assertEqual(self.manager.logs()[0]['action'],'restore')
 def test_restore_conflict_never_overwrites(self):
  entry=self.archive();existing=m.DATA/('a'*32);existing.mkdir();(existing/'sentinel').write_text('preserve')
  with self.assertRaises(ValueError):self.manager.restore(entry.name)
  self.assertTrue(entry.exists());self.assertEqual((existing/'sentinel').read_text(),'preserve')
 def test_manual_purge_requires_current_confirmation(self):
  self.archive();token=self.manager.listing()['confirm_token'];self.archive('b'*32)
  with self.assertRaises(ValueError):self.manager.purge(token)
  self.assertEqual(self.manager.listing()['count'],2)
 def test_clear_and_audit_survives(self):
  self.archive();self.archive('b'*32);snapshot=self.manager.listing();self.assertGreater(snapshot['bytes'],0);result=self.manager.purge(snapshot['confirm_token']);self.assertEqual(result['count'],2);self.assertEqual(self.manager.listing()['count'],0);self.assertEqual(self.manager.logs()[0]['count'],2)
 def test_unverified_or_symlink_entries_never_deleted(self):
  entry=self.archive(age=8);(entry/'deletion.json').write_text('{}');outside=m.DATA/'other';outside.mkdir();(outside/'keep').write_text('yes');(self.manager.root()/('c'*32+'-123-12345678')).symlink_to(outside,target_is_directory=True)
  result=self.manager.purge(automatic=True,now=self.now);self.assertEqual(result['count'],0);self.assertEqual(result['ignored'],2);self.assertTrue(entry.exists());self.assertEqual((outside/'keep').read_text(),'yes')
 def test_scheduler_uses_beijing_four_and_once_daily(self):
  tz=datetime.timezone(datetime.timedelta(hours=8));before=datetime.datetime(2026,10,22,3,59,tzinfo=tz).timestamp();after=datetime.datetime(2026,10,22,4,0,tzinfo=tz).timestamp()
  with patch.object(self.manager,'purge',return_value={}) as cleanup:
   self.assertFalse(self.manager.daily_tick(before));self.assertTrue(self.manager.daily_tick(after));self.assertFalse(self.manager.daily_tick(after+100));cleanup.assert_called_once_with(automatic=True,now=after)
 def test_bad_entry_id_rejected(self):
  with self.assertRaises(ValueError):self.manager.restore('../active')
if __name__=='__main__':unittest.main()
