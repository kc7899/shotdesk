import unittest
from types import SimpleNamespace
from unittest.mock import patch
import h3_structured as h
class SceneOnly(unittest.TestCase):
 def test_scene_only_storyboard_is_valid_without_fabricated_character(self):
  p={'assets':[{'id':'room','type':'场景','name':'桌面','prompt':'red cup on table','image':'/room.png'}],'script':'桌面上，杯子静置。','prompt_language':'en'}
  row={'title':'桌面','description_zh':'杯子静置','image_prompt_zh':'红杯木桌','duration':5,'scene':'A1','cast':[],'props':[],'summary_en':'A cup rests on a table.','look_en':'Soft daylight.','soundscape_en':'Quiet room.','music_en':'N/A','clips':[{'start':0,'end':5,'new_cut':False,'shot_size':'wide','camera':'static','subject_ids':['A1'],'action':'The cup rests on the table.','line':None,'speaker_ids':[],'delivery':None}]}
  task={'model':'test','storyboard_skill':{'video_mode':'reference','video_model':'test-h3'}}
  with patch.object(h,'asset_profiles',return_value={}),patch.object(h,'ask_rows',return_value=([row],1)),patch('storyboard.progress'):
   result=h.plan(SimpleNamespace(uid=lambda:'shot'),p,task)
  self.assertEqual(result['shots'][0]['asset_ids'],['room']);self.assertEqual(result['shots'][0]['character_looks'],{});self.assertEqual(result['shots'][0]['dialogue'],[])
  schema=h.schema(h.catalog(p),h.model_rules('test-h3'));self.assertEqual(schema['properties']['shots']['items']['properties']['cast']['maxItems'],0)
