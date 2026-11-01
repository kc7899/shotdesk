import unittest
from types import SimpleNamespace
from unittest.mock import patch
import server as m
class OfficialImageCatalog(unittest.TestCase):
 def test_display_names_preserve_stable_ids_and_official_reference_limit(self):
  official='Qwen-Image-2.1-Official-Turbo-8step-2K';legacy='Qwen-Image-2.1-Turbo'
  engine=SimpleNamespace(IMAGE_MODELS={official:2048,legacy:1024},VIDEO_MODELS={},recipes=SimpleNamespace(IMAGES={}),OFFICIAL_QWEN_TURBO={official:2048},IMAGE_LABELS={official:'官方八步',legacy:'Viggle 六步'})
  with patch.object(m.Q,'engine',return_value=engine):catalog=m.model_catalog()['images']
  self.assertEqual([x['id'] for x in catalog],[official,legacy]);self.assertEqual(catalog[0]['max_references'],16);self.assertEqual(catalog[0]['display_name'],'官方八步');self.assertEqual(catalog[1]['display_name'],'Viggle 六步')
if __name__=='__main__':unittest.main()
