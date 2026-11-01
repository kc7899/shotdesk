"""User setup uses guarded APIs; diagnostic and failure paths never mutate user projects."""
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from tests.backend import test_portable as fixtures
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('shotdesk_setup',ROOT/'scripts/shotdesk_setup.py');setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup);sys.modules['shotdesk_setup']=setup
spec=importlib.util.spec_from_file_location('shotdesk_smoke',ROOT/'scripts/shotdesk_smoke.py');smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
class SetupTools(unittest.TestCase):
 setUp=fixtures.Portable.setUp
 req=fixtures.Portable.req
 def test_read_only_doctor_distinguishes_connected_from_generation(self):
  self.settings.update({'comfy_url':fixtures.engine.COMFY})
  report=setup.doctor(setup.Client(self.base));self.assertTrue(report['diagnostics_complete']);self.assertEqual(report['services']['comfy']['status'],'connected');self.assertEqual(report['services']['llm']['status'],'not_configured');self.assertFalse(report['generated_media_verified']);self.assertFalse(report['ready_for_generation_test']);self.assertEqual(self.req('/api/projects'),[])
 def test_configuration_preflight_and_server_busy_guard(self):
  path=self.root/'private.json';path.write_text(json.dumps({'comfy_url':fixtures.engine.COMFY}))
  self.assertTrue(setup.configure(setup.Client(self.base),path)['saved'])
  before=self.settings.read();path.write_text(json.dumps({'comfy_url':'http://127.0.0.1:1'}))
  with self.assertRaisesRegex(ValueError,'no configuration was saved'):setup.configure(setup.Client(self.base),path)
  self.assertEqual(self.settings.read(),before)
  path.write_text(json.dumps({'not_a_setting':'private-secret'}))
  with self.assertRaisesRegex(ValueError,'Unsupported'):setup.configure(setup.Client(self.base),path)
 def test_authenticated_diagnostics_never_echo_credentials(self):
  self.settings.update({'access_password':'private-passphrase','llm_api_key':'private-key'})
  report=setup.doctor(setup.Client(self.base));self.assertEqual(report['studio']['status'],'unreachable');self.assertNotIn('private-key',json.dumps(report));self.assertIn('Authentication',report['studio']['error'])
  report=setup.doctor(setup.Client(self.base,'private-passphrase'));self.assertTrue(report['diagnostics_complete']);self.assertNotIn('private-key',json.dumps(report))
 def test_setup_guide_discoverable_through_http(self):
  info=self.req('/api/agent-info');self.assertEqual(info['version'],'0.1.0-preview.1')
  with self.op.open(self.base+info['setup_guide']) as r:self.assertIn(b'shotdesk_setup.py',r.read())
 def test_smoke_opt_in_and_timeout_stop_only_owned_job(self):
  class Fake:
   def __init__(self):self.calls=[]
   def call(self,path,body=None):
    self.calls.append((path,body))
    if path=='/api/model-catalog':return {'images':[{'id':'image'}],'videos':[{'id':'video'}]}
    if path=='/api/projects':return {'id':'new-test-project','reset_epochs':{}}
    if path=='/api/projects/new-test-project':return {'reset_epochs':{}}
    if path.endswith('/generate'):return {'id':'own-job','kind':'image'}
    return {}
  args=SimpleNamespace(report=str(self.root/'smoke.json'),allow_generate=False,image_model='image',video_model='video',video_mode='text',width=512,height=288,duration=2,llm_model=None,with_llm=False,timeout=0)
  c=Fake();self.assertFalse(smoke.run(c,args)['success']);self.assertEqual(c.calls,[])
  args.allow_generate=True;c=Fake();r=smoke.run(c,args);self.assertFalse(r['success']);self.assertEqual(r['project_id'],'new-test-project');self.assertTrue(any(path.endswith('/own-job/stop') for path,_ in c.calls));self.assertFalse(any('stop-all' in path for path,_ in c.calls));self.assertTrue(all('/existing' not in path for path,_ in c.calls))
 def test_url_secrets_rejected(self):
  with self.assertRaises(ValueError):setup.Client('http://user:secret@localhost:1258')
