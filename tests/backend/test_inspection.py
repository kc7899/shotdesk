import tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
import server as m
class Inspection(unittest.TestCase):
 def test_real_bytes_no_metadata_and_cache(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'DATA',Path(d)):
   pid='a'*32;root=Path(d)/pid;(root/'media').mkdir(parents=True)
   (root/'media'/'image.png').write_bytes(b'\x89PNG\r\n\x1a\nTEST')
   m.save(m.project(pid),{'assets':[],'shots':[{'id':'s','title':'SECRET_TITLE','description':'SECRET_STORY','duration':4,'image_completed':False,'versions':[{'id':'v','kind':'image','url':f'/media/{pid}/media/image.png','prompt':'SECRET_PROMPT'}]}]})
   answer={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'observation':'可见一人','out_of_frame':'右侧人物仅有腿','uncertain':'上衣不可判断'},ensure_ascii=False)}}]}
   with patch.object(m,'request',return_value=answer) as request:
    result=m.inspect_media(pid,{'version_id':'v'})
    payload=request.call_args.args[1];serialized=json.dumps(payload)
    for secret in ('SECRET_TITLE','SECRET_STORY','SECRET_PROMPT'):self.assertNotIn(secret,serialized)
    self.assertIn('data:image/png;base64,',serialized);self.assertEqual(len(payload['messages']),2)
    self.assertEqual(result['status'],'analyzed');self.assertIn('v',m.load(pid)['media_read'])
    self.assertFalse(m.load(pid)['shots'][0]['image_completed'])
    self.assertTrue(m.inspect_media(pid,{'version_id':'v'})['cached']);self.assertEqual(request.call_count,1)
    m.inspect_media(pid,{'version_id':'v','force':True});self.assertEqual(request.call_count,2)
   with patch.object(m,'request',return_value={'choices':[{'message':{'content':'not json'}}]}):
    with self.assertRaises(ValueError):m.inspect_media(pid,{'version_id':'v','force':True})
   with self.assertRaises(ValueError):m.inspect_media(pid,{'version_id':'missing'})
if __name__=='__main__':unittest.main()
