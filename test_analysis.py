import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import core
import analysis_api as api


class AnalysisTests(unittest.TestCase):
    def test_resume_is_opt_in_and_input_versions_stay_distinct(self):
        result = dict(choices=[dict(message=dict(content='合成分析'), finish_reason='stop')])
        resume = dict(filename='synthetic.pdf', text='原始提取文字', reviewed_text='核对后的简历文字')
        for selected_resume in [None, resume]:
            with patch.object(api, 'build_opener') as opener:
                opener.return_value.open.return_value = io.BytesIO(json.dumps(result).encode())
                record = api.analyze({'title': '测试岗位'}, 'test-only-key', resume=selected_resume)
                payload = json.loads(opener.return_value.open.call_args.args[0].data)
                user = json.loads(payload['messages'][1]['content'])
                self.assertEqual('简历文字（用户核对后）' in user, selected_resume is not None)
                if selected_resume:
                    self.assertEqual(user['简历文字（用户核对后）'], resume['reviewed_text'])
                    self.assertEqual(record['resume_snapshot']['text'], '原始提取文字')
                else:
                    self.assertIsNone(record['resume_snapshot'])

    def test_request_and_append_history_preserve_original(self):
        row = dict(title='分析师', url='https://example.com/1', jd='SQL，本科')
        result = dict(choices=[dict(message=dict(content='测试分析'), finish_reason='stop')],
                      usage=dict(total_tokens=100))
        with patch.object(api, 'build_opener') as opener:
            opener.return_value.open.return_value = io.BytesIO(json.dumps(result).encode())
            record = api.analyze(row, 'test-only-secret')
            request = opener.return_value.open.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(body['model'], 'glm-4.7-flash')
            self.assertEqual(body['max_tokens'], 1200)
            self.assertEqual(body['thinking'], {'type': 'disabled'})
            self.assertNotIn('test-only-secret', json.dumps(record))
        original = core.DB
        try:
            with tempfile.TemporaryDirectory() as directory:
                core.DB = Path(directory) / 'jobs.sqlite3'
                core.save([row])
                before = core.load()
                api.save_analysis(record)
                api.save_analysis({**record, 'id': 'another-analysis'})
                self.assertEqual(len(api.load_analyses(row)), 2)
                self.assertEqual(core.load(), before)
                self.assertEqual(api.load_analyses(row)[0]['source_snapshot']['jd'], row['jd'])
        finally:
            core.DB = original

    def test_invalid_configuration_never_calls_api(self):
        with patch.object(api, 'build_opener') as opener:
            for key, base in [('', api.DEFAULT_BASE_URL), ('test', 'http://example.com'),
                              ('test', 'https://example.com/?key=secret')]:
                with self.assertRaises(ValueError):
                    api.analyze({'title': 'A'}, key, base)
            opener.assert_not_called()

    def test_errors_are_redacted_and_not_retried(self):
        for error in [HTTPError(api.DEFAULT_BASE_URL, 401, 'test-secret', {}, None),
                      URLError('test-secret')]:
            with patch.object(api, 'build_opener') as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(ValueError) as caught:
                    api.analyze({'title': 'A'}, 'test-secret')
                self.assertNotIn('test-secret', str(caught.exception))
                self.assertEqual(opener.return_value.open.call_count, 1)

    def test_incomplete_and_malformed_response_rejected(self):
        for result in [{}, {'choices': []},
                       {'choices': [{'message': {'content': ''}}]},
                       {'choices': [{'message': {'content': '部分分析'}, 'finish_reason': 'length'}]}]:
            with patch.object(api, 'build_opener') as opener:
                opener.return_value.open.return_value = io.BytesIO(json.dumps(result).encode())
                with self.assertRaises(ValueError):
                    api.analyze({'title': 'A'}, 'test-secret')


if __name__ == '__main__':
    unittest.main()
