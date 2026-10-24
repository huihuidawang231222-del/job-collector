import json, tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from official_careers import canonical,public_url,linked_scope,tenant,matches,listing_state,official_policy
from collection_safety import SafetyStop
class OfficialTests(unittest.TestCase):
 def test_url_and_tenant_boundaries(self):
  self.assertFalse(public_url('http://127.0.0.1/x'))
  self.assertFalse(public_url('https://localhost/'))
  self.assertFalse(public_url('file:///etc/passwd'))
  self.assertFalse(public_url('https://user:secret@example.com'))
  self.assertTrue(public_url('https://example.com/jobs'))
  self.assertEqual(canonical('https://example.com/job?id=7&utm_source=x#foo'),'https://example.com/job?id=7')
  roots=['https://example.com/careers'];tenants={tenant('https://jobs.smartrecruiters.com/Example/1')}
  self.assertTrue(linked_scope('https://jobs.smartrecruiters.com/Example/2',roots,tenants))
  self.assertFalse(linked_scope('https://jobs.smartrecruiters.com/Other/2',roots,tenants))
  self.assertFalse(linked_scope('https://example.com.evil.test/jobs',roots,tenants))
 def test_city_and_keywords_do_not_use_company_address(self):
  row={'title':'Data Analyst','jd':'Python SQL','company':'广州公司','location':'Shanghai'}
  self.assertFalse(matches(row,'analyst','广州'))
  row['location']='Guangzhou, China';self.assertTrue(matches(row,'GIS,analyst','广州'))
  self.assertFalse(matches(row,'GIS','广州'))
  row['location']='未说明';self.assertFalse(matches(row,'analyst','广州'))
 def test_expiry(self):
  self.assertEqual(listing_state({'valid_through':'2000-01-01'}),'已过截止时间')
  self.assertIn('待核实',listing_state({}))
 def test_missing_robots_is_distinct_from_denial(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'policy-cache.json'
   for code in [404,403,429]:
    p.write_text(json.dumps({'https://example.com':{'status':'unknown','http_status':code}}))
    with patch('official_careers.check_policy',side_effect=SafetyStop('test')):
     if code==404:self.assertEqual(official_policy('https://example.com/jobs',d),{'text':''})
     else:
      with self.assertRaises(SafetyStop):official_policy('https://example.com/jobs',d)

 def test_export_city_and_foreign_currency(self):
  import core
  from classify import enrich
  self.assertEqual(enrich({'location':'China GD Guangzhou'})['city'],'广州')
  with tempfile.TemporaryDirectory() as d,patch.object(core,'DB',Path(d)/'jobs.sqlite3'):
   core.save([{'title':'Analyst','location':'Guangzhou','salary':'8-12K','currency':'USD','jd':'明确双休','url':'https://example.com/1'}])
   r=core.load()[0]
   self.assertIsNone(r['salary_min']);self.assertEqual(r['weekends'],'双休')
