import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from collection_safety import (CollectionGuard, SafetyStop, check_policy,
                               robots_allowed, single_collector)


class PolicyTests(unittest.TestCase):
    def test_wildcards_queries_specific_agents_and_allow_ties(self):
        rules='User-agent: *\nDisallow: /*?*\nDisallow: /private\nAllow: /private/public$'
        self.assertFalse(robots_allowed(rules,'https://example.com/jobs?query=test'))
        self.assertTrue(robots_allowed(rules,'https://example.com/'))
        self.assertTrue(robots_allowed(rules,'https://example.com/private/public'))
        self.assertFalse(robots_allowed(rules,'https://example.com/private/public/other'))
        self.assertTrue(robots_allowed('User-agent: *\nDisallow: /x\nAllow: /x','https://example.com/x'))
        self.assertFalse(robots_allowed('User-agent: *\nAllow: /\nUser-agent: JobCollector\nDisallow: /','https://example.com/'))

    def test_html_challenge_is_unknown_not_permission_and_cached(self):
        class Response(io.BytesIO):
            url='https://example.com/robots.txt'
        with tempfile.TemporaryDirectory() as directory, patch('collection_safety.urlopen') as fetch:
            fetch.return_value=Response(b'<html>Security Verification</html>')
            for _ in range(2):
                with self.assertRaises(SafetyStop):check_policy('https://example.com/jobs',directory,now=100000)
            self.assertEqual(fetch.call_count,1)
            cache=json.loads((Path(directory)/'policy-cache.json').read_text(encoding='utf-8'))
            self.assertEqual(cache['https://example.com']['status'],'unknown')

    def test_real_boss_query_restriction_blocks_before_action(self):
        class Response(io.BytesIO):
            url='https://www.zhipin.com/robots.txt'
        with tempfile.TemporaryDirectory() as directory, patch('collection_safety.urlopen') as fetch:
            fetch.return_value=Response(b'User-agent: *\nDisallow: /*?*\n')
            guard=CollectionGuard('zhipin.com',directory)
            with self.assertRaises(SafetyStop):guard.before('search','https://www.zhipin.com/web/geek/job?query=test')
            self.assertEqual(guard.actions,0)


class GuardTests(unittest.TestCase):
    def test_pacing_persistence_budget_and_audit_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            now=[100000.0]
            def sleep(seconds):now[0]+=seconds
            options=dict(clock=lambda:now[0],sleeper=sleep,policy=lambda *a,**k:None)
            guard=CollectionGuard('example.com',directory,**options)
            guard.before('detail','https://example.com/job/1?token=PRIVATE')
            restarted=CollectionGuard('example.com',directory,**options)
            restarted.before('capture','https://example.com/job/1')
            self.assertEqual(now[0],100010)
            self.assertNotIn('PRIVATE',(Path(directory)/'collection-events.jsonl').read_text())
            restarted.state['daily_actions']=40
            with self.assertRaises(SafetyStop):restarted.before('scroll','https://example.com/jobs')

    def test_platform_declared_interval_is_not_shortened(self):
        with tempfile.TemporaryDirectory() as directory:
            now=[100000.0]
            guard=CollectionGuard('example.com',directory,clock=lambda:now[0],
                sleeper=lambda seconds:now.__setitem__(0,now[0]+seconds),
                policy=lambda *a,**k:{'text':'User-agent: *\nCrawl-delay: 30'})
            guard.before('capture','https://example.com/jobs')
            guard.before('scroll','https://example.com/jobs')
            self.assertEqual(now[0],100030)

    def test_retry_after_and_repeated_challenges_persist_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            guard=CollectionGuard('example.com',directory,clock=lambda:100000)
            response=SimpleNamespace(status=429,headers={'retry-after':'7200'})
            with self.assertRaises(SafetyStop):guard.response(response)
            self.assertEqual(guard.state['cooldown_until'],107200)
            with self.assertRaises(SafetyStop):CollectionGuard('example.com',directory,clock=lambda:100100).checkpoint()
        with tempfile.TemporaryDirectory() as directory:
            guard=CollectionGuard('example.com',directory,clock=lambda:100000)
            guard.challenge()
            with self.assertRaises(SafetyStop):guard.challenge()

    def test_session_deadline_and_shared_process_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            now=[100000]
            guard=CollectionGuard('example.com',directory,clock=lambda:now[0])
            now[0]+=300
            with self.assertRaises(SafetyStop):guard.checkpoint()
            @single_collector(directory)
            def second():self.fail('Concurrent collector must not run')
            @single_collector(directory)
            def first():
                with self.assertRaises(SafetyStop):second()
                self.assertTrue((Path(directory)/'worker.lock').exists())
            first()
            self.assertFalse((Path(directory)/'worker.lock').exists())


if __name__=='__main__':unittest.main()
