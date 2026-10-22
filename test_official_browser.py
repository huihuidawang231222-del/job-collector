"""Offline DOM tests; no requests or live hiring data."""
import json,unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
class BrowserExtractionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=sync_playwright().start()
  try:cls.browser=cls.p.chromium.launch(headless=True)
  except Exception as e:
   cls.p.stop();raise unittest.SkipTest('Chromium未安装：'+str(e).splitlines()[0])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop()
 def extract(self,html):
  page=self.browser.new_page(java_script_enabled=False);page.route('**/*',lambda r:r.abort())
  try:
   page.set_content('<base href="https://example.com/jobs/1">'+html)
   return page.evaluate(Path(__file__).with_name('official_extract.js').read_text())['jobs']
  finally:page.close()
 def test_jsonld_graph_and_array_location(self):
  job={'@type':'JobPosting','title':'GIS分析师','description':'<p>负责数据分析</p>','hiringOrganization':{'name':'测试公司'},'jobLocation':[{'address':{'addressLocality':'广州'}}]}
  rows=self.extract('<script type="application/ld+json">'+json.dumps({'@graph':[job]},ensure_ascii=False)+'</script>')
  self.assertEqual(rows[0]['company'],'测试公司');self.assertEqual(rows[0]['location'],'广州');self.assertIn('负责数据分析',rows[0]['jd'])
 def test_microdata_ignores_empty_first_heading(self):
  rows=self.extract('''<h1></h1><div itemscope itemtype="https://schema.org/JobPosting"><h1 itemprop="title">Data Analyst</h1><div itemprop="hiringOrganization"><meta itemprop="name" content="Example"></div><div itemprop="jobLocation"><meta itemprop="addressLocality" content="Guangzhou"></div><div itemprop="description">SQL Python 工作职责和任职要求</div></div>''')
  self.assertEqual(rows[0]['title'],'Data Analyst');self.assertEqual(rows[0]['location'],'Guangzhou')
 def test_does_not_promote_whole_page_to_jd(self):
  self.assertEqual(self.extract('<h1>招聘列表</h1><main>公司地址广州。没有岗位JD。</main>'),[])
