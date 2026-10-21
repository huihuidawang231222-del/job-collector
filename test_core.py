import tempfile,unittest
from pathlib import Path
import core
class CoreTests(unittest.TestCase):
    def test_salary(self):
        self.assertEqual(core.salary('8千-1.2万·13薪'),(8000,12000))
        self.assertEqual(core.salary('8-12K'),(8000,12000))
        self.assertEqual(core.salary('20-30万/年'),(None,None))
        self.assertEqual(core.salary('200-300元/天'),(None,None))
        self.assertEqual(core.salary('面议'),(None,None))
    def test_database(self):
        original=core.DB
        try:
            with tempfile.TemporaryDirectory() as d:
                core.DB=Path(d)/'jobs.sqlite3'
                r=dict(title='分析师',company='测试公司',url='https://example.com/job/1',salary='8-12K',raw='双休')
                self.assertEqual(core.save([r,{'title':''}]),(1,0,1))
                first=core.load()[0]['first_seen']
                r['salary']='10-15K'
                self.assertEqual(core.save([r]),(0,1,0))
                rows=core.load()
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]['salary_min'],10000)
                self.assertEqual(rows[0]['first_seen'],first)
        finally: core.DB=original

class ClassificationTests(unittest.TestCase):
    def test_classify_and_export(self):
        from classify import enrich,export_rows
        r=enrich(dict(title='Python工程师',location='广州·天河区',jd='本科，1-3年经验，SQL，五险一金',industry_raw='机械制造',salary='8-12K·13薪'))
        self.assertEqual(r['industry'],'制造业')
        self.assertEqual(r['city'],'广州')
        self.assertEqual(r['district'],'天河区')
        self.assertEqual(r['salary_months'],13)
        self.assertEqual(r['education'],'本科')
        self.assertIn('SQL',r['skills'])
        self.assertEqual(export_rows([r])[0]['岗位JD'],r['jd'])
    def test_no_invented_industry_or_jd(self):
        from classify import enrich
        r=enrich(dict(title='软件工程师',raw='软件开发，互联网，五险一金'))
        self.assertEqual(r['industry'],'未说明')
        self.assertEqual(r['jd_status'],'未获取详情')

class AutomaticCollectionTests(unittest.TestCase):
    def test_inline_login_gate_does_not_read_clipped_jd(self):
        from unittest.mock import MagicMock
        import auto_collect as ac
        page=MagicMock();panel=page.locator.return_value
        link=MagicMock();link.count.return_value=1;link.get_attribute.return_value='https://www.zhaopin.com/jobdetail/example.htm'
        gate=MagicMock();gate.is_visible.return_value=True
        gates=MagicMock();gates.all.return_value=[gate]
        def locate(selector):
            if selector.startswith('a[href'):
                found=MagicMock();found.first=link;return found
            if 'guest-clamp' in selector:return gates
            self.fail('Login-clipped JD must not be read')
        panel.locator.side_effect=locate
        row=dict(title='测试岗位',list_index=0)
        ac.capture_inline(page,row,True)
        self.assertEqual(row['jd_access'],'需登录查看完整JD')
        self.assertNotIn('jd',row)
        self.assertEqual(row['url'],'https://www.zhaopin.com/jobdetail/example.htm')

    def test_limit_and_automatic_scroll(self):
        from unittest.mock import patch,MagicMock
        import auto_collect as ac
        page=MagicMock()
        batches=iter([{'rows':[dict(title='A',url='https://example.com/1')]},{'rows':[dict(title='B',url='https://example.com/2')]}])
        def evaluate(script):
            if script.startswith('() => {window.scrollTo'):return None
            return next(batches)
        page.evaluate.side_effect=evaluate;out=[]
        with patch.object(ac,'stopped',return_value=False),patch.object(ac,'blocked',return_value=False),patch.object(ac,'status'):
            n,why=ac.collect(page,{'host':'example.com'},'分析',2,10,False,emit=lambda r:out.extend(r))
        self.assertEqual(n,2);self.assertEqual(why,'达到数量上限')
        self.assertEqual(len(out),2)
        self.assertTrue(any('scrollTo' in c.args[0] for c in page.evaluate.call_args_list))
    def test_validation_pauses_before_capture(self):
        from unittest.mock import patch,MagicMock
        import auto_collect as ac
        page=MagicMock()
        with patch.object(ac,'stopped',return_value=False),patch.object(ac,'blocked',return_value=True),patch.object(ac,'pause',return_value=False):
            n,why=ac.collect(page,{'host':'example.com'},'分析',2,10,False)
        self.assertEqual(n,0);page.evaluate.assert_not_called()

if __name__=='__main__':unittest.main()
