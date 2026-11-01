import json,unittest
from unittest.mock import patch
import server as app
class ScriptOutput(unittest.TestCase):
 def test_preserves_literal_invalid_backslash_and_real_newline(self):
  self.assertEqual(app.decode_script_response('{"script":"杯沿\\*反光\\q，\\u不是编码\n结束。"}')['script'],'杯沿\\*反光\\q，\\u不是编码\n结束。')
 def test_valid_escaped_backslash_unicode_and_quotes_stay_exact(self):
  content='路径 \\cup；原文 "你好"\n第二行。';self.assertEqual(app.decode_script_response(json.dumps({'script':content}))['script'],content)
  self.assertEqual(app.decode_script_response('{"script":"\\u676f"}')['script'],'杯')
 def test_missing_or_nontext_script_rejected(self):
  for raw in ['{"script":null}','{"script":[]}','{"script":""}','not json']:
   with self.assertRaises(ValueError):app.decode_script_response(raw)
 def test_format_retry_bounded_and_frozen_skill_used(self):
  good={'choices':[{'message':{'content':'{"script":"杯子静置。"}'},'finish_reason':'stop'}]};bad={'choices':[{'message':{'content':'bad'},'finish_reason':'stop'}]}
  task={'model':'test','script_skill_text':'frozen'}
  with patch.object(app.Q,'text_request',side_effect=[bad,good]) as request:
   self.assertEqual(app.plan({'content':'杯子','assets':[]},task),{'script':'杯子静置。'});self.assertEqual(request.call_count,2);self.assertEqual(request.call_args.args[0]['messages'][0]['content'],'frozen')
  with patch.object(app.Q,'text_request',return_value=bad) as request:
   with self.assertRaisesRegex(ValueError,'原剧本保持不变'):app.plan({'content':'杯子','assets':[]},task)
   self.assertEqual(request.call_count,2)
