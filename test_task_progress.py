import json,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from task_progress import launch,snapshot,_workers

class ProgressTests(unittest.TestCase):
 def wait_log_release(self,status):
  log=Path(status).parent/'log'
  for _ in range(50):
   try:log.unlink(missing_ok=True);return
   except PermissionError:time.sleep(.1)
  self.fail('Worker log is still open')
 def test_panels_distinguish_running_success_shortfall_and_error(self):
  from streamlit.testing.v1 import AppTest
  with tempfile.TemporaryDirectory() as d:
   status=Path(d)/'status.json'
   app=AppTest.from_string('from task_progress import panel\nfrom pathlib import Path\npanel(Path('+repr(str(status))+'),"测试采集")')
   for state,kind,text in [('running','info','正在运行'),('passed','success','验收通过'),('incomplete','warning','未达到目标'),('failed','error','异常终止')]:
    status.write_text(json.dumps({'state':state,'target':100,'eligible_unique':7}),encoding='utf-8')
    app.run(timeout=15)
    self.assertEqual(len(app.exception),0)
    self.assertTrue(any(text in x.value for x in app.get(kind)))

 def wait_exit(self,status):
  deadline=time.time()+15
  while time.time()<deadline:
   data=snapshot(status)
   if data[1].get('state')=='exited':
    process=_workers.get(data[1]['pid'])
    if process:process.wait(timeout=5)
    self.wait_log_release(status)
    return data
   time.sleep(.1)
  self.fail('Worker did not finish')

 def test_real_worker_heartbeat_and_completion(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);status=root/'status.json';script=root/'fixture.py'
   script.write_text("import time,json\nfrom pathlib import Path\np=Path("+repr(str(status))+")\np.write_text(json.dumps({'state':'running','message':'fixture'}))\ntime.sleep(3)\np.write_text(json.dumps({'state':'finished'}))",encoding='utf-8')
   self.assertIsInstance(launch([sys.executable,str(script)],status,root/'log'),int)
   deadline=time.time()+10
   while time.time()<deadline and snapshot(status)[1].get('state')!='running':time.sleep(.1)
   first=snapshot(status)[1]['heartbeat'];time.sleep(2.2)
   self.assertGreater(snapshot(status)[1]['heartbeat'],first)
   task,runtime,state,message=self.wait_exit(status)
   self.assertEqual(state,'finished');self.assertEqual(runtime['exit_code'],0)

 def test_exception_and_abrupt_exit_are_not_success(self):
  for source in ["raise RuntimeError('fixture failure')","import os;os._exit(7)"]:
   with self.subTest(source=source),tempfile.TemporaryDirectory() as d:
    root=Path(d);status=root/'status.json';script=root/'fixture.py';script.write_text(source,encoding='utf-8')
    pid=launch([sys.executable,str(script)],status,root/'log')
    if 'RuntimeError' in source:
     task,runtime,state,message=self.wait_exit(status)
     self.assertEqual(state,'failed');self.assertIn('fixture failure',message)
    else:
     runtime=status.with_suffix('.runtime.json');deadline=time.time()+10
     while time.time()<deadline and snapshot(status)[1].get('state')=='starting':time.sleep(.1)
     data=json.loads(runtime.read_text(encoding='utf-8'));data['heartbeat']=time.time()-20
     runtime.write_text(json.dumps(data),encoding='utf-8')
     self.assertEqual(snapshot(status)[2],'unresponsive')
     process=_workers.get(pid)
     if process:process.wait(timeout=5)
     self.wait_log_release(status)
