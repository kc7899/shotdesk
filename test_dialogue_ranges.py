import copy,unittest,json
from unittest.mock import patch
import storyboard as b
import test_queue
import test_storyboard_official as fixtures
m=test_queue.m
class DialogueRanges(unittest.TestCase):
 setUp=test_queue.QueueContracts.setUp
 tearDown=test_queue.QueueContracts.tearDown
 prepare=fixtures.OfficialStoryboard.prepare
 row=fixtures.OfficialStoryboard.row
 def ledger(self):return [{'id':'D'+str(i),'speaker':'林岚','text':'句'+str(i),'start':i} for i in range(1,6)]
 def test_program_consumes_each_line_once_even_with_repeated_boundary(self):
  obj={'shots':[{'dialogue_through':'D2','dialogue_delivery':{'D1':'疑问'}},{'dialogue_through':'D2'},{'dialogue_through':None},{'dialogue_through':'D5'}]}
  result=b.expand_dialogue_ranges(obj,self.ledger(),{})
  self.assertEqual([[d['line_id'] for d in s['dialogue']] for s in result['shots']],[['D1','D2'],[],[],['D3','D4','D5']]);self.assertEqual(result['shots'][0]['dialogue'][0]['delivery'],'疑问')
 def test_incomplete_backward_and_unknown_bounds_are_not_guessed(self):
  for ends in (['D2'],['D4','D2','D5'],['D7']):
   with self.subTest(ends=ends),self.assertRaises(b.PlanningDialogueError):b.expand_dialogue_ranges({'shots':[{'dialogue_through':e} for e in ends]},self.ledger(),{})
 def test_new_schema_has_no_model_written_dialogue_array(self):
  schema=b.output_schema('planning',[],True,self.ledger(),True)['properties']['shots']['items']
  self.assertIn('dialogue_through',schema['required']);self.assertNotIn('dialogue',schema['properties']);self.assertFalse(schema['additionalProperties'])
 def test_bad_range_splits_only_failed_source_range_after_bounded_retry(self):
  p=self.prepare();script='林岚：您好。\n'*300;segments=b.planning_segments(script);first={'start':0,'end':segments[0][1],'analysis':'saved','shots':[dict(self.row(),dialogue=[{'speaker':'林岚','text':'您好。'} for _ in range(script[:segments[0][1]].count('林岚：'))])]}
  task={'model':'local','storyboard_skill':{'planning_format':'unified-references-v1','dialogue_format':'source-lines-v2','dialogue_planning':'contiguous-v1'},'storyboard_seed_parts':[first]};attempts=0
  def answer(body,task):
   nonlocal attempts
   attempts+=1;payload=json.loads(body['messages'][1]['content']);source=payload['source_dialogue'];scope=payload['planning_scope'];row=self.row();row.pop('dialogue');row['references']=[{'asset_id':'person','look_id':'look'},{'asset_id':'room','look_id':None}];row.pop('asset_ids');row.pop('character_looks')
   row['dialogue_through']=source[0]['id'] if scope['start']==segments[1][0] and scope['end']==segments[1][1] else source[-1]['id']
   return {'choices':[{'message':{'content':json.dumps({'shots':[row]},ensure_ascii=False)}}]}
  with patch.object(self.q,'text_request',side_effect=answer):result=b.plan_in_parts(m.AppContext(),task,{'script':script,'assets':m.script_reference_context(p)},'planning')
  self.assertEqual(task['storyboard_resumed_segments'],1);self.assertTrue(any(x.get('repair_split') for x in task['storyboard_planning_checks']));self.assertEqual(sum(len(s['dialogue']) for s in result['shots']),300)
