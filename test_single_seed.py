import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import server as m
class SingleSeed(unittest.TestCase):
 def test_single_image_asset_video_random_seeds(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'DATA',Path(d)),patch.object(m.Q,'reject_duplicate'),patch.object(m.Q,'enqueue',side_effect=lambda pid,j:j),patch.object(m,'reference',return_value='data:image/png;base64,test'):
   pid='a'*32;m.project(pid).parent.mkdir()
   m.save(m.project(pid),{'ratio':'16:9','image_model':'test','video_model':'MiniMaxH3-8step-I2V','assets':[{'id':'a','name':'a','prompt':'same'}],'shots':[{'id':'s','image_prompt':'same','video_prompt':'Duration: 4s\nAct','duration':4,'seed':42,'image':'/media/test.png','versions':[]}]})
   for target,kind,id in [('shot','image','s'),('asset','image','a'),('shot','video','s')]:
    tasks=[m.launch(pid,target,id,kind) for _ in range(3)]
    seeds=[t['request']['seed'] for t in tasks]
    self.assertEqual(len(set(seeds)),3)
    self.assertTrue(all(isinstance(seed,int) and 0<=seed<2**32 for seed in seeds))
if __name__=='__main__':unittest.main()
