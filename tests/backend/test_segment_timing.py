import copy,unittest
import segment_timing as T

def budget(script,quote,seconds=120,mode='minimum',ident='b',start=None):
 start=script.index(quote) if start is None else start
 return {'id':ident,'quote':quote,'start':start,'end':start+len(quote),'before':script[max(0,start-80):start],'after':script[start+len(quote):start+len(quote)+80],'seconds':seconds,'mode':mode}
def row(duration=5,key='b'):
 return {'title':'Observe action','description_zh':'Continuous action','duration':duration,'clips':[{'start':0,'end':duration,'line_ids':[]}], '_timing_constraint_id':key}
class SegmentTiming(unittest.TestCase):
 def test_anchor_relocates_after_prepend_and_rejects_changed_quote(self):
  script='场景 1\n\n甲开始练拳。\n\n甲离开。';b=budget(script,'甲开始练拳。');self.assertEqual(T.locate('前言\n'+script,b)[0],b['start']+3);self.assertIsNone(T.locate(script.replace('练拳','喝水'),b))
 def test_repeated_text_uses_context_not_first_occurrence(self):
  script='早晨\n甲等待。\n甲离开。\n晚上\n甲等待。\n灯熄灭。';start=script.rindex('甲等待。');b=budget(script,'甲等待。',start=start);self.assertEqual(T.locate(script,b)[0],start)
  b.update(before='',after='');self.assertIsNone(T.locate(script,b))
 def test_overlaps_invalid_before_model_calls(self):
  script='甲练拳后离开。';a=budget(script,'甲练拳');b=budget(script,'练拳后',ident='c');p={'script':script,'segment_timings':[a,b]}
  with self.assertRaisesRegex(ValueError,'重叠'):T.resolved(p,True)
 def test_partition_has_selected_passage_only_and_keeps_other_text(self):
  from h3_structured import chunks
  script='场景 1\n\n日 · 内\n练功房\n\n甲开始练拳。\n\n甲离开。';b=budget(script,'甲开始练拳。');p={'script':script,'segment_timings':[b]};parts=T.partition(p,chunks)
  timed=[x for x in parts if x.get('timing_constraint')];self.assertEqual(len(timed),1);self.assertEqual(timed[0]['text'],b['quote']);self.assertEqual(timed[0]['heading'],'场景 1');self.assertTrue(any('甲离开。' in x['text'] and not x.get('timing_constraint') for x in parts))
 def test_120_seconds_expands_to_real_rows_then_legal_clip_durations(self):
  script='甲练拳。';p={'script':script,'segment_timings':[budget(script,script)]};calls=[]
  def ask(b,old,seconds,count):calls.append((seconds,count));return [row() for _ in range(count)]
  original=[row()];rows,report=T.expand(p,original,{'max':15,'min':4,'integer':False},ask)
  self.assertGreaterEqual(sum(r['duration'] for r in rows),120);self.assertGreaterEqual(len(rows),8);self.assertTrue(all(4<=r['duration']<=15 for r in rows));self.assertTrue(report[0]['met']);self.assertEqual(original[0]['duration'],5);self.assertTrue(calls)
  self.assertTrue(all(r['clips'][-1]['end']==r['duration'] for r in rows))
 def test_other_passages_cannot_count_toward_budget(self):
  script='甲练拳。';p={'script':script,'segment_timings':[budget(script,script)]};rows,reports=T.expand(p,[row(15),row(200,None)],{'max':15,'min':4,'integer':False},lambda *a:[row(15) for _ in range(a[-1])]);self.assertGreaterEqual(reports[0]['planned_seconds'],120);self.assertEqual(next(r for r in rows if r['_timing_constraint_id'] is None)['duration'],200)
 def test_approximate_can_shorten_silent_beats_without_cutting_speech(self):
  script='甲练拳。';p={'script':script,'segment_timings':[budget(script,script,120,'approximate')]};rows,report=T.expand(p,[row(15) for _ in range(10)],{'max':15,'min':4,'integer':True},lambda *a:[]);self.assertAlmostEqual(sum(r['duration'] for r in rows),120);self.assertTrue(report[0]['met'])
 def test_unmet_constraint_never_marked_success(self):
  script='甲练拳。';p={'script':script,'segment_timings':[budget(script,script)]}
  with self.assertRaisesRegex(ValueError,'未达到要求'):T.expand(p,[row()],{'max':15,'min':4,'integer':False},lambda *a:[])
 def test_unicode_positions_and_validation(self):
  script='🙂甲练拳。';b=budget(script,'甲练拳。');self.assertEqual(T.resolved({'script':script,'segment_timings':[b]},True)[0]['start'],1)
  for change in ({'seconds':True},{'seconds':601},{'end':99},{'mode':'bad'}):
   with self.assertRaises(ValueError):T.validate([{**b,**change}])

class SegmentTimingIntegration(unittest.TestCase):
 def test_full_h3_planner_expands_and_tags_120_seconds(self):
  import h3_structured as H
  from tests.backend.test_h3_structured import Api,FakeQ,project,good_rows,profiles_response
  p=project();b=budget(p['script'],p['script']);b['script_fingerprint']=T.script_fingerprint(p['script']);p['segment_timings']=[b]
  extras=[]
  for i in range(4):
   r=copy.deepcopy(good_rows()['shots'][0]);r['title']='Continuation '+str(i)
   for c in r['clips']:c['line_ids']=[]
   extras.append(r)
  q=FakeQ([profiles_response(p),good_rows(),{'shots':copy.deepcopy(extras)},{'shots':copy.deepcopy(extras)}]);api=Api(q)
  task={'storyboard_skill':{'video_mode':p['video_mode'],'video_model':p['video_model']},'model':'fake'}
  result=H.plan(api,p,task);shots=result['shots'];self.assertGreaterEqual(sum(s['duration'] for s in shots),120);self.assertGreaterEqual(len(shots),8)
  self.assertTrue(all(s['timing_constraint_id']=='b' and s['timing_constraint_quote']==p['script'] for s in shots));self.assertTrue(task['segment_timing_report'][0]['met'])
  self.assertEqual(sum(len(s['dialogue']) for s in shots),3)
 def test_fingerprint_allows_explicit_position_in_repeated_context(self):
  script='甲等待。'*100;b=budget(script,'甲等待。',start=200);b['script_fingerprint']=T.script_fingerprint(script);self.assertEqual(T.locate(script,b),(200,204))

from tests.backend import test_portable as fixture
class SegmentTimingHTTP(unittest.TestCase):
 setUp=fixture.Portable.setUp
 req=fixture.Portable.req
 def test_roundtrip_and_unrelated_script_edit_keeps_requirement(self):
  p=self.req('/api/projects',{'name':'Passage timing'});pid=p['id'];script='🙂甲练拳。';b=budget(script,'甲练拳。');b['script_fingerprint']=T.script_fingerprint(script)
  self.req('/api/projects/'+pid+'/save',{'script':script,'segment_timings':[b]});saved=self.req('/api/projects/'+pid);self.assertEqual(saved['segment_timings'][0],b)
  self.req('/api/projects/'+pid+'/save',{'script':'引言\n'+script});saved=self.req('/api/projects/'+pid);self.assertEqual(T.resolved(saved,True)[0]['start'],4)
 def test_invalid_target_rejected_and_stale_anchor_blocks_submission(self):
  import urllib.error
  p=self.req('/api/projects',{'name':'Invalid passage timing'});pid=p['id'];b=budget('甲练拳。','甲练拳。')
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/projects/'+pid+'/save',{'segment_timings':[{**b,'seconds':999}]})
  self.req('/api/projects/'+pid+'/save',{'script':'甲离开。','segment_timings':[b]})
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/projects/'+pid+'/storyboard',{})
