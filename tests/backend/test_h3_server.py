import copy, unittest
from unittest.mock import patch
from tests.backend import test_queue
import storyboard as b
from tests.backend import test_h3_structured as fx
m = test_queue.m


class Server(unittest.TestCase):
    setUp = test_queue.QueueContracts.setUp
    tearDown = test_queue.QueueContracts.tearDown

    def test_default_scheme_and_model_switch_marks_prompts_stale(self):
        p = m.load(self.pid)
        self.assertEqual(b.project_scheme(p), 'h3-structured-v2')
        p['shots'] = [{'id': 's1', 'title': 'a', 'duration': 8, 'video_prompt': '旧提示词', 'prompt_format': 'huobao-native-v1'}]
        p['video_model'] = 'MiniMaxH3-R2V-8step-768p'; p['video_mode'] = 'reference'
        with patch.object(m.Q, 'list', return_value=[]):
            m.merge_save(p, {'video_model': 'Pika-H3-Flex-6step-R2V'})
        shot = p['shots'][0]
        self.assertIn('Pika-H3-Flex-6step-R2V', shot['prompt_stale']['reason'])
        self.assertEqual(shot['prompt_stale']['from'], 'MiniMaxH3-R2V-8step-768p')
        with patch.object(m.Q, 'list', return_value=[]):
            m.merge_save(p, {'video_model': 'MiniMaxH3-R2V-8step-768p'})
        self.assertNotIn('prompt_stale', p['shots'][0])
        with patch.object(m.Q, 'list', return_value=[]), self.assertRaises(ValueError):
            m.merge_save(p, {'storyboard_scheme': 'nope'})
        with patch.object(m.Q, 'list', return_value=[]):
            m.merge_save(p, {'storyboard_scheme': 'huobao-native-v1'})
        self.assertEqual(b.project_scheme(p), 'huobao-native-v1')

    def test_check_existing_reports_v2_stale(self):
        p = fx.project(); q = fx.FakeQ([fx.profiles_response(p), fx.good_rows()])
        shots = fx.H.plan(fx.Api(q), p, {'model': 'm', 'storyboard_skill': {'video_mode': 'reference', 'video_model': p['video_model']}})['shots']
        p['shots'] = shots; p['video_model'] = 'Pika-H3-Flex-6step-R2V'
        res = b.check_existing(m, p)
        text = str(res)
        self.assertIn('需重新生成', text)


if __name__ == '__main__':
    unittest.main()
