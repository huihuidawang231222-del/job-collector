import json,tempfile,unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
import core
import feed_collect as task
from public_feeds import lever_config,normalize_lever,documented_lever_policy,read_lever_page
from collection_safety import SafetyStop,CollectionGuard
from urllib.error import HTTPError,URLError
from unittest.mock import Mock
SOURCE={'company':'测试雇主','url':'https://jobs.lever.co/example'}
def posting(i,city='Guangzhou'):
 return dict(id=str(i),text='Analyst '+str(i),categories={'location':city},descriptionPlain='SQL Python analysis. '*10,
 lists=[{'text':'Requirements','content':'<li>本科</li><li>分析经验</li>'}],additionalPlain='Additional information',hostedUrl='https://jobs.lever.co/example/'+str(i))
class FeedTests(unittest.TestCase):
 def test_failed_host_cools_down_across_employers_and_restart(self):
  failures=[HTTPError('https://api.lever.co',500,'error',{},None),
            HTTPError('https://api.lever.co',503,'error',{'Retry-After':'900'},None),
            URLError('connection failed'),TimeoutError(),ConnectionResetError()]
  for failure in failures:
   with self.subTest(failure=type(failure).__name__),tempfile.TemporaryDirectory() as directory:
    now=100000
    guard=CollectionGuard('api.lever.co',directory,clock=lambda:now,policy=documented_lever_policy)
    opener=Mock();opener.open.side_effect=failure
    with self.assertRaises(SafetyStop):read_lever_page(lever_config(SOURCE['url']),0,1,guard,opener)
    delay=900 if isinstance(failure,HTTPError) and failure.code==503 else 300
    self.assertEqual(guard.state['cooldown_until'],now+delay)
    restarted=CollectionGuard('api.lever.co',directory,clock=lambda:now,policy=documented_lever_policy)
    with self.assertRaises(SafetyStop):read_lever_page(lever_config('https://jobs.lever.co/another'),0,1,restarted,opener)
    self.assertEqual(opener.open.call_count,1)
    CollectionGuard('api.eu.lever.co',directory,clock=lambda:now).checkpoint()
    CollectionGuard('api.lever.co',directory,clock=lambda:now+delay).checkpoint()

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
  self.assertEqual(result['sources'][0]['excluded']['city_mismatch'],100)
  self.assertIn('地区不匹配100条',result['message'])
  self.assertEqual(result['sources'][0]['end_reason'],'已读完来源公开列表')
 def test_gis_not_logistics(self):
  from official_careers import matches
  self.assertFalse(matches({'title':'Logistics Analyst','jd':'logistics','location':'Guangzhou'},'GIS','广州'))
