import copy, json, unittest
import h3_structured as H

SCRIPT = """场景 1

日 · 内
银行营业大厅

老黑戴面罩冲进大厅。

老黑：都别动！抢劫！

小刘：您取号了吗？

经理、小刘、老赵同时抬头。

三人：又来啦？！
"""


def project():
    return {'name': 't', 'script': SCRIPT, 'video_mode': 'reference', 'video_model': 'MiniMaxH3-R2V-8step-768p', 'shots': [],
            'assets': [
                {'id': 'liu', 'type': '角色', 'name': '小刘', 'prompt': '年轻女柜员', 'default_look_id': 'l1', 'looks': [{'id': 'l1', 'name': '日常制服', 'prompt': '蓝色制服', 'image': '/m/l1.png'}]},
                {'id': 'hei', 'type': '角色', 'name': '老黑', 'prompt': '青年男子', 'default_look_id': 'h1', 'looks': [{'id': 'h1', 'name': '劫匪装束', 'prompt': '黑面罩', 'image': '/m/h1.png'}, {'id': 'h2', 'name': '次日入职', 'prompt': '银行马甲', 'image': '/m/h2.png'}]},
                {'id': 'zhao', 'type': '角色', 'name': '老赵', 'prompt': '保安', 'default_look_id': 'z1', 'looks': [{'id': 'z1', 'name': '保安制服', 'prompt': '', 'image': '/m/z1.png'}]},
                {'id': 'jl', 'type': '角色', 'name': '经理', 'prompt': '经理', 'default_look_id': 'j1', 'looks': [{'id': 'j1', 'name': '经理制服', 'prompt': '', 'image': '/m/j1.png'}]},
                {'id': 'hall', 'type': '场景', 'name': '银行营业大厅', 'prompt': '大厅', 'image': '/m/hall.png'},
                {'id': 'gun', 'type': '道具', 'name': '道具枪', 'prompt': '黑色手枪', 'image': '/m/gun.png'}]}


def good_rows():
    return {'shots': [
        {'title': '闯入', 'description_zh': '老黑冲进来', 'image_prompt_zh': '大厅全景', 'duration': 8, 'scene': 'A5',
         'cast': [{'asset': 'A2', 'look': 'A2-1'}, {'asset': 'A1', 'look': 'A1-1'}], 'props': ['A6'],
         'summary_en': '#A2 bursts into #A5 and #A1 calmly answers.', 'look_en': 'Bright cool bank lighting.',
         'clips': [{'start': 0, 'end': 4, 'new_cut': True, 'shot_size': 'wide shot', 'camera': 'static camera',
                    'subject_ids': ['A5', 'A2', 'A6'], 'action': '#A2 bursts in raising #A6; the screen shows "正在加载……99%".',
                    'line_ids': ['L1'], 'delivery': 'shouting'},
                   {'start': 4, 'end': 8, 'new_cut': True, 'shot_size': 'medium close-up', 'camera': 'slow push-in',
                    'subject_ids': ['A1'], 'action': '#A1 looks up from the counter.', 'line_ids': ['L2'], 'delivery': 'flatly'}],
         'soundscape_en': 'Door bang, quiet hall tone.', 'music_en': 'N/A'},
        {'title': '又来啦', 'description_zh': '三人齐声', 'image_prompt_zh': '三人抬头', 'duration': 5, 'scene': 'A5',
         'cast': [{'asset': 'A4', 'look': 'A4-1'}, {'asset': 'A1', 'look': 'A1-1'}, {'asset': 'A3', 'look': 'A3-1'}], 'props': [],
         'summary_en': '#A4, #A1 and #A3 look up together.', 'look_en': 'Same lighting.',
         'clips': [{'start': 0, 'end': 5, 'new_cut': True, 'shot_size': 'medium wide shot', 'camera': 'static camera',
                    'subject_ids': ['A4', 'A1', 'A3'], 'action': 'All three look up at once.', 'line_ids': ['L3'], 'delivery': None}],
         'soundscape_en': 'Room tone.', 'music_en': 'N/A'}]}


class FakeQ:
    def __init__(self, responses):
        self.responses = list(responses); self.bodies = []
    def text_request(self, body, task):
        self.bodies.append(copy.deepcopy(body))
        return {'choices': [{'message': {'content': json.dumps(self.responses.pop(0), ensure_ascii=False)}, 'finish_reason': 'stop'}]}
    def check(self, task): pass
    def persist(self, pid, task): pass


class Api:
    def __init__(self, q):
        self.Q = q; self.n = 0
    def uid(self):
        self.n += 1; return 'shot%d' % self.n
    def video_mode(self, shot, p): return p['video_mode']
    def video_model(self, shot, p): return p['video_model']


def profiles_response(p):
    cat = H.catalog(p); keys = {}
    for r in cat:
        for k in ([l['handle'] for l in r['looks']] or [r['handle']]):
            keys[k] = {'en': 'a subject ' + k, 'short': 'the subject ' + k, 'voice': 'a calm voice' if r['type'] == '角色' else ''}
    return {'profiles': keys}


class T(unittest.TestCase):
    def setUp(self):
        self.p = project(); self.cat = H.catalog(self.p)
        self.lines = H.number_lines(H.dialogue_lines(self.p['script'], self.cat))
        self.rules = H.model_rules(self.p['video_model'])
    def check(self, rows, rules=None):
        errs = H.resolve_lines(rows, self.lines, self.cat)
        return errs + H.validate_rows(rows, self.cat, rules or self.rules, self.lines, self.lines)

    def test_good_rows_validate(self):
        self.assertEqual(self.check(good_rows()), [])

    def test_errors_detected(self):
        rows = good_rows(); s = rows['shots'][0]
        s['clips'][0]['line_ids'] = []  # missing L1
        rows['shots'][1]['clips'][0]['line_ids'] = ['L2']  # wrong place; L3 group without enough subjects
        s['clips'][1]['line_ids'] = ['L3']
        s['clips'][1]['end'] = 5; s['duration'] = 5
        s['props'] = ['A6', 'A6'] ; s['cast'].append({'asset': 'A4', 'look': 'A2-1'})
        s['clips'][1]['action'] = '小刘抬头'
        errs = '\n'.join(self.check(rows))
        for needle in ('遗漏台词编号', '群声', '造型', '须为英文', '没有在任何 clip'):
            self.assertIn(needle, errs)

    def test_refs_density_speakers(self):
        rows = good_rows(); s = rows['shots'][0]
        s['cast'] += [{'asset': 'A3', 'look': 'A3-1'}, {'asset': 'A4', 'look': 'A4-1'}]
        s['clips'][1]['start'] = 7.5; s['clips'][0]['end'] = 7.5
        errs = '\n'.join(self.check(rows))
        self.assertIn('超过 4 张', errs); self.assertIn('字/秒', errs)

    def test_number_lines_split_and_schema(self):
        long = [{'label': '经理', 'speakers': ['A4'], 'text': '各位客户请注意，本行今天系统升级。' * 3}]
        out = H.number_lines(long)
        self.assertGreater(len(out), 1); self.assertEqual(''.join(x['text'] for x in out), long[0]['text'])
        self.assertTrue(all(H.spoken_len(x['text']) <= H.MAX_LINE_PIECE for x in out))
        sch = H.schema(self.cat, self.rules, 12, ['L1', 'L2'])
        clip = sch['properties']['shots']['items']['properties']['clips']['items']
        self.assertNotIn('line', clip['properties']); self.assertEqual(clip['properties']['line_ids']['items']['enum'], ['L1', 'L2'])

    def test_mixed_speaker_clip_is_split_mechanically(self):
        rows = good_rows(); s = rows['shots'][0]
        s['clips'] = [dict(s['clips'][0], start=0, end=8, line_ids=['L1', 'L2'], subject_ids=['A5', 'A2', 'A1', 'A6'])]
        rows['shots'][0]['props'] = ['A6']
        self.assertEqual(self.check(rows), [])
        clips = rows['shots'][0]['clips']
        self.assertEqual([(c['line'], c['speaker_ids']) for c in clips], [('都别动！抢劫！', ['A2']), ('您取号了吗？', ['A1'])])
        self.assertEqual((clips[0]['start'], clips[-1]['end']), (0.0, 8.0)); self.assertEqual(clips[0]['end'], clips[1]['start'])

    def test_trim_refs_drops_prop_then_nonspeakers(self):
        rows = good_rows(); s0 = rows['shots'][0]
        s0['cast'] = s0['cast'] + [{'asset': 'A3', 'look': 'A3-1'}, {'asset': 'A4', 'look': 'A4-1'}]
        s0['props'] = ['A6']
        # After resolve, speakers are A2 then A1; A3/A4 nonspeakers + prop must go.
        H.resolve_lines(rows, self.lines, self.cat)
        H.drop_unused_props(rows); H.trim_refs(rows, self.cat)
        refs = ([s0['scene']] if s0.get('scene') else []) + [c['asset'] for c in s0['cast']] + s0['props']
        self.assertLessEqual(len(refs), H.MAX_REFS)
        self.assertIn('A1', [c['asset'] for c in s0['cast']]); self.assertIn('A2', [c['asset'] for c in s0['cast']]); self.assertNotIn('A3', [c['asset'] for c in s0['cast']])
        self.assertEqual(self.check(rows), [])

    def test_unused_prop_dropped(self):
        rows = good_rows(); rows['shots'][1]['props'] = ['A6']
        H.drop_unused_props(rows); self.assertEqual(rows['shots'][1]['props'], [])
        rows = good_rows(); H.drop_unused_props(rows); self.assertEqual(rows['shots'][0]['props'], ['A6'])

    def test_wrong_line_order_is_reordered_not_rejected(self):
        rows = good_rows()
        rows['shots'][0]['clips'][0]['line_ids'] = ['L2']
        rows['shots'][0]['clips'][1]['line_ids'] = ['L1']
        rows['shots'][1]['clips'][0]['line_ids'] = ['L3']
        self.assertTrue(H.reorder_line_ids(rows, self.lines))
        self.assertEqual([c['line_ids'] for c in rows['shots'][0]['clips']], [['L1'], ['L2']])
        self.assertEqual(self.check(rows), [])
        self.assertEqual(rows['shots'][0]['clips'][0]['line'], '都别动！抢劫！')

    def test_skip_chunk_continues_and_all_fail_raises(self):
        p = dict(self.p)
        p['script'] = '场景 1\n老黑：都别动！抢劫！\n小刘：您取号了吗？\n\n场景 2\n\n三人：又来啦？！\n'
        bad1 = {'shots': [dict(good_rows()['shots'][0], clips=[dict(good_rows()['shots'][0]['clips'][0], line_ids=[])])]}
        scene2 = {'shots': [{
            'title': '又来啦', 'description_zh': '三人齐声', 'image_prompt_zh': '三人抬头', 'duration': 5, 'scene': 'A5',
            'cast': [{'asset': 'A4', 'look': 'A4-1'}, {'asset': 'A1', 'look': 'A1-1'}, {'asset': 'A3', 'look': 'A3-1'}], 'props': [],
            'summary_en': '#A4, #A1 and #A3 look up together.', 'look_en': 'Same lighting.',
            'clips': [{'start': 0, 'end': 5, 'new_cut': True, 'shot_size': 'medium wide shot', 'camera': 'static camera',
                       'subject_ids': ['A4', 'A1', 'A3'], 'action': 'All three look up at once.', 'line_ids': ['L1'], 'delivery': None}],
            'soundscape_en': 'Room tone.', 'music_en': 'N/A'}]}
        task = {'model': 'm', 'storyboard_skill': {'video_mode': 'reference', 'video_model': p['video_model']}}
        q = FakeQ([profiles_response(p)] + [bad1] * 3 + [scene2])
        result = H.plan(Api(q), p, task)
        self.assertEqual(len(result['shots']), 1)
        self.assertEqual(len(task.get('h3v2_skipped') or []), 1)
        self.assertIn('片段1', task['h3v2_skipped'][0]['chunk'])
        self.assertIn('跳过', task.get('h3v2_warning', ''))
        q = FakeQ([profiles_response(p)] + [bad1] * 30)
        with self.assertRaises(H.StructuredOutputError):
            H.plan(Api(q), p, {'model': 'm', 'storyboard_skill': {'video_mode': 'reference', 'video_model': p['video_model']}})

    def test_cjk_in_english_fields_fixed_mechanically(self):
        rows = good_rows(); rows['shots'][0]['summary_en'] = '老黑 bursts in'
        rows['shots'][0]['clips'][1]['action'] = "#A1 stares at '正在加载' and 正在加载……99%"
        H.fix_cjk(rows, self.cat)
        self.assertEqual(rows['shots'][0]['summary_en'], '#A2 bursts in')
        self.assertTrue(H.english_only(rows['shots'][0]['clips'][1]['action']))
        self.assertEqual(self.check(rows), [])

    def test_pika_integer(self):
        rows = good_rows(); rows['shots'][0]['duration'] = 7.5; rows['shots'][0]['clips'][1]['end'] = 7.5
        errs = '\n'.join(self.check(rows, H.model_rules('Pika-H3-Flex-6step-R2V')))
        self.assertIn('整数', errs)

    def test_render_reference(self):
        q = FakeQ([profiles_response(self.p), good_rows()])
        api = Api(q); task = {'model': 'm', 'storyboard_skill': H.bundle(type('A', (), {'video_mode': lambda s, x, y: 'reference', 'VIDEO_STRATEGIES': {}})(), self.p)}
        result = H.plan(api, self.p, task)
        shots = result['shots']; self.assertEqual(len(shots), 2)
        text = shots[0]['video_prompt']
        for sec in ('subject_definitions:', 'summary:\n[reference generation]', 'retention_analysis:', 'detailed_description:', 'overall_soundscape:', 'non_diegetic_music:'):
            self.assertIn(sec, text)
        self.assertIn('<Subject 2> (S1), in a calm voice, says, shouting: <d>[Chinese] 都别动！抢劫！</d>', text)
        self.assertIn('[Shot 2] At 00:04.000, the shot cuts to a medium close-up, slow push-in.', text)
        self.assertIn('Source' if False else '<Picture 1>', text)
        self.assertNotIn('#A', text); self.assertNotIn('@', text); self.assertNotIn('..', text)
        self.assertIn('[Shot 1] A wide shot, static camera.', text)
        self.assertEqual(shots[0]['asset_ids'], ['hall', 'hei', 'liu', 'gun'])
        self.assertEqual(shots[0]['character_looks'], {'hei': 'h1', 'liu': 'l1'})
        self.assertIn('(S1,S2,S3) say together: <d>[Chinese] 又来啦？！</d>', shots[1]['video_prompt'])
        body = q.bodies[1]
        self.assertEqual((body['temperature'], body['top_p'], body['presence_penalty']), (0.3, 0.8, 1.0))
        # Compile re-renders with the actual picture order.
        inputs = [{'asset_id': 'liu', 'url': 'u1', 'name': '小刘'}, {'asset_id': 'hall', 'url': 'u2', 'name': '大厅'}, {'asset_id': 'hei', 'url': 'u3', 'name': '老黑'}, {'asset_id': 'gun', 'url': 'u4', 'name': '枪'}]
        compiled, bindings = H.compile(self.p, shots[0], 'video', inputs, 'reference', self.p['video_model'])
        self.assertIn('<Subject 2> is the environment shown in <Picture 2>', compiled)
        self.assertEqual([b['reference_index'] for b in bindings], [1, 2, 3, 4])
        # Model switch to Pika: 8s integer ok; staleness reported.
        self.assertIn('当前视频模型为', H.stale_reason(self.p, shots[0], 'reference', 'Pika-H3-Flex-6step-R2V'))
        shots[1]['duration'] = 4
        with self.assertRaises(ValueError):
            H.compile(dict(self.p, video_model='Pika-H3-Flex-6step-R2V'), shots[1], 'video', inputs, 'reference', 'Pika-H3-Flex-6step-R2V')

    def test_retry_feedback_bounded(self):
        bad = good_rows(); bad['shots'][0]['clips'][0]['line_ids'] = []
        q = FakeQ([profiles_response(self.p), bad, bad, good_rows()])
        api = Api(q); task = {'model': 'm', 'storyboard_skill': {'video_mode': 'reference', 'video_model': self.p['video_model']}}
        shots = H.plan(api, self.p, task)['shots']
        self.assertEqual(len(shots), 2)
        self.assertIn('程序校验未通过', q.bodies[2]['messages'][-1]['content'])
        q = FakeQ([profiles_response(self.p)] + [bad] * 6)
        with self.assertRaises(H.StructuredOutputError):
            H.plan(Api(q), self.p, {'model': 'm', 'storyboard_skill': {'video_mode': 'reference', 'video_model': self.p['video_model']}})

    def test_base_mode_render(self):
        q = FakeQ([profiles_response(self.p), good_rows()])
        task = {'model': 'm', 'storyboard_skill': {'video_mode': 'first_frame', 'video_model': 'MiniMaxH3-8step-I2V'}}
        text = H.plan(Api(q), dict(self.p, video_mode='first_frame'), task)['shots'][0]['video_prompt']
        self.assertTrue(text.startswith(H.FIRST_FRAME)); self.assertIn('integrated_multimodal_description:', text); self.assertNotIn('<Subject', text)


if __name__ == '__main__':
    unittest.main()
