"""Public packages exclude private/upstream originals and cannot bypass integrity/readiness checks."""
import importlib.util,json,tempfile,unittest,hashlib
from pathlib import Path
spec=importlib.util.spec_from_file_location('release',Path(__file__).resolve().parents[2]/'scripts/export_release.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
class ReleasePackage(unittest.TestCase):
 def test_public_package_integrity_license_and_acceptance_gate(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'package';release.export(root)
   self.assertTrue((root/'LICENSE').exists());self.assertTrue((root/'scripts/shotdesk_setup.py').exists());self.assertTrue((root/'docs/skills/shotdesk-setup/SKILL.md').exists())
   self.assertFalse((root/'huobao_native.py').exists());self.assertFalse((root/'data').exists());self.assertFalse((root/'docs/skills/shotdesk-storyboard/references/h3-ref-en.txt').exists())
   check=release.check_ready(root);self.assertFalse(any('integrity' in b for b in check['blockers']))
   # Synthetic acceptance states in the isolated package; no GPU result asserted by this test.
   evidence=root/'docs/release-validation.json';evidence.write_text(json.dumps({'version':'0.1.0-preview.1','technical_acceptance_passed':False}))
   manifest=root/'release-manifest.json';m=json.loads(manifest.read_text());m['files'][str(evidence.relative_to(root))]=hashlib.sha256(evidence.read_bytes()).hexdigest();manifest.write_text(json.dumps(m))
   self.assertFalse(release.check_ready(root)['ready_for_publication'])
   original=release.ROOT;release.ROOT=root
   try:
    second=Path(t)/'second';release.export(second)
    for script in second.rglob('*.py'):compile(script.read_text(),str(script),'exec')
   finally:release.ROOT=original
   (root/'static/app.js').write_text('tampered')
   self.assertTrue(any('integrity' in b for b in release.check_ready(root)['blockers']))
