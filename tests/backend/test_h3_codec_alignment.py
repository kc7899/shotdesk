import copy,unittest
from task_queue import align_h3_encoder_inputs,comfy_error
class H3CodecAlignment(unittest.TestCase):
 def test_align_intermediate_video_before_encoding_and_idempotent(self):
  graph={'scale':{'class_type':'ImageScaleBy','inputs':{'scale_by':1.65}},'encoder':{'class_type':'BlehTAEVideoEncode','inputs':{'latent_type':'minimaxh3video','image':['scale',0]}}}
  align_h3_encoder_inputs(graph);key=graph['encoder']['inputs']['image'][0]
  self.assertEqual(graph[key]['inputs'],{'image':['scale',0],'width':0,'height':0,'upscale_method':'bilinear','keep_proportion':False,'divisible_by':32,'crop':'disabled'})
  previous=copy.deepcopy(graph);align_h3_encoder_inputs(graph);self.assertEqual(previous,graph)
 def test_other_codecs_unchanged(self):
  graph={'a':{'class_type':'BlehTAEVideoEncode','inputs':{'latent_type':'other','image':['b',0]}}};previous=copy.deepcopy(graph);align_h3_encoder_inputs(graph);self.assertEqual(graph,previous)
 def test_error_preserves_cause_not_tensor_dump(self):
  error={'node_id':'105:961','node_type':'BlehTAEVideoEncode','exception_message':'height 461 is not divisible by 2','current_inputs':{'image':'tensor'+('0.12 '*5000)}}
  result=comfy_error({'status':{'messages':[['execution_error',error],['execution_cached',{}]]}})
  self.assertIn('height 461',result);self.assertIn('105:961',result);self.assertNotIn('tensor',result);self.assertLess(len(result),200)
