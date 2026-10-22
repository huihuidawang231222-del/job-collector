import json,tempfile,unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
import core
import feed_collect as task
from public_feeds import lever_config,normalize_lever,documented_lever_policy
from collection_safety import SafetyStop
SOURCE={'company':'测试雇主','url':'https://jobs.lever.co/example'}
def posting(i,city='Guangzhou'):
 return dict(id=str(i),text='Analyst '+str(i),categories={'location':city},descriptionPlain='SQL Python analysis. '*10,
 lists=[{'text':'Requirements','content':'<li>本科</li><li>分析经验</li>'}],additionalPlain='Additional information',hostedUrl='https://jobs.lever.co/example/'+str(i))
class FeedTests(unittest.TestCase):
 def test_url_config_and_job_url_must_match_tenant(self):
  self.assertEqual(lever_config(SOURCE['url'])['api'],'api.lever.co')
  for url in ['http://jobs.lever.co/example','https://evil.test/example','https://jobs.lever.co/example/apply','https://jobs.lever.co/example?q=x']:
   with self.assertRaises(ValueError):lever_config(url)
  bad=posting(1);bad['hostedUrl']='https://jobs.lever.co/other/1'
  self.assertIsNone(normalize_lever(bad,SOURCE))
  with self.assertRaises(SafetyStop):documented_lever_policy('https://api.lever.co/admin',Path('.'))
 def test_full_description_and_multilocation(self):
  p=posting(1);p['openingPlain']='SQL Python analysis.';p['categories']['allLocations']=['Guangzhou','Shanghai','Guangzhou']
  row=normalize_lever(p,SOURCE)
  self.assertIn('本科',row['jd']);self.assertIn('Additional information',row['jd'])
  self.assertEqual(row['location'],'Guangzhou；Shanghai')
  self.assertIsNone(normalize_lever({**p,'text':'Talent Community'},SOURCE))
 def run_task(self,posts,target=100,city='',keyword=''):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);sources=root/'sources.json';sources.write_text(json.dumps([SOURCE]))
  # Decorator bypass is test-only, avoiding production paths while testing real writes/readback.
  args=Namespace(sources=str(sources),target=target,pages=1,city=city,keyword=keyword,refresh=False)
  with patch.object(core,'DB',root/'jobs.sqlite3'),patch.object(task,'DATA',root),patch.object(task,'STATUS',root/'status.json'),patch.object(task,'STOP',root/'stop'),patch.object(task,'read_lever_page',return_value=(posts,'https://api.lever.co/v0/postings/example',1000)):
   core.save([{'title':'Previously saved','url':'https://example.com/old','jd':'Old text '*20}])
   result=task.run.__wrapped__(args)
   self.assertEqual(len(core.load()),result['metrics']['saved_unique']+1)
  return result
 def test_accepts_100_distinct_real_writes_not_old_rows(self):
  result=self.run_task([posting(i) for i in range(100)])
  self.assertTrue(result['acceptance_passed']);self.assertEqual(result['writes']['added'],100)
  self.assertEqual(result['metrics']['complete_jd'],100);self.assertEqual(len(result['manifest']),100)
 def test_duplicates_do_not_meet_target(self):
  result=self.run_task([posting(i%5) for i in range(100)])
  self.assertFalse(result['acceptance_passed']);self.assertEqual(result['state'],'incomplete')
  self.assertEqual(result['metrics']['saved_unique'],5)
 def test_city_shortfall_not_filled_with_other_cities(self):
  result=self.run_task([posting(i,'Shanghai') for i in range(100)],city='广州')
  self.assertFalse(result['acceptance_passed']);self.assertEqual(result['metrics']['saved_unique'],0)
 def test_gis_not_logistics(self):
  from official_careers import matches
  self.assertFalse(matches({'title':'Logistics Analyst','jd':'logistics','location':'Guangzhou'},'GIS','广州'))
