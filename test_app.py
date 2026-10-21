"""Local Streamlit integration checks with an isolated synthetic database."""
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest
import core


class AppTests(unittest.TestCase):
    def test_empty_populated_and_zero_result_views(self):
        previous = core.DB
        try:
            with tempfile.TemporaryDirectory() as directory:
                core.DB = Path(directory) / 'jobs.sqlite3'
                app = AppTest.from_file(str(Path(__file__).with_name('app.py'))).run(timeout=30)
                self.assertEqual(len(app.exception), 0)
                self.assertTrue(any(x.label == '选择 PDF 简历' for x in app.get('file_uploader')))
                self.assertTrue(next(x for x in app.button if x.label == '解析简历').disabled)
                self.assertTrue(next(x for x in app.checkbox if x.label == '使用上方核对后的简历做匹配分析').disabled)
                self.assertTrue(any(x.label == 'API Key（仅在本次本地会话使用，不写入文件）' for x in app.text_input))
                self.assertTrue(next(x for x in app.button if x.label == '分析此岗位').disabled)
                core.save([dict(title='合成测试分析师', company='测试公司', location='广州',
                                url='https://example.com/test-job', jd='本科 SQL')])
                app.run(timeout=30)
                self.assertEqual(len(app.exception), 0)
                self.assertTrue(any(x.label == '分析此岗位' for x in app.button))
                next(x for x in app.button if x.label == '分析此岗位').click().run(timeout=30)
                self.assertTrue(any('请先确认发送范围' in x.value for x in app.error))
                next(x for x in app.checkbox if x.label == '同意将选中岗位、偏好及勾选的简历文字发送给以上 API 服务').check()
                next(x for x in app.button if x.label == '分析此岗位').click().run(timeout=30)
                self.assertTrue(any('有效 API Key' in x.value for x in app.error))
                self.assertEqual(core.load()[0]['jd'], '本科 SQL')
                search = next(x for x in app.text_input if x.label == '岗位 / 公司 / 描述关键词')
                search.set_value('没有匹配的合成岗位').run(timeout=30)
                self.assertEqual(len(app.exception), 0)
                self.assertTrue(any('筛选结果：0 条' in x.value for x in app.markdown))
                self.assertTrue(next(x for x in app.button if x.label == '分析此岗位').disabled)
        finally:
            core.DB = previous


if __name__ == '__main__':
    unittest.main()
