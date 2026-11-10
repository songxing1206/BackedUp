import copy,hashlib,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import launcher
import app.storage as storage
from app.runtime import APP_VERSION,health
from app.model_settings import SettingsStore
from app.automatic_review import ReviewQueue,review_cache_key
from app.pdf_index import fingerprint
from test_automatic_review import AutoTests
from test_final_regressions import FinalRegressions
from test_evidence_http import HttpTests

class LauncherTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.env=patch.dict('os.environ',{'BACKEDUP_DATA_HOME':self.temp.name,'BACKEDUP_CACHE_HOME':self.temp.name+'/cache'});self.env.start()
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def test_only_reuse_same_checkout(self):
  other={**health(storage.data_dir()),'instance':'other'}
  with patch('launcher.PORTS',[8787,8788]),patch('launcher.probe',side_effect=[other,health(storage.data_dir())]):
   self.assertEqual(launcher.existing_service()[0],8788)
 def test_conflicting_port_uses_next(self):
  class Socket:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def setsockopt(self,*args):pass
   def listen(self,*args):pass
   def bind(self,address):
    if address[1]==8787:raise OSError('occupied')
  with patch('launcher.socket.socket',return_value=Socket()):self.assertEqual(launcher.free_port(),8788)
 def test_no_ports_has_clear_error(self):
  with patch('launcher.PORTS',[]):
   with self.assertRaisesRegex(RuntimeError,'端口均被占用'):launcher.free_port()
 def test_repeated_launch_does_not_spawn(self):
  with tempfile.TemporaryDirectory() as d,patch('launcher.ROOT',Path(d)),patch('launcher.dependencies',return_value=[]),patch('launcher.existing_service',return_value=(8787,{'version':APP_VERSION})),patch('launcher.open_page') as opened,patch('launcher.subprocess.Popen') as spawn:
   self.assertEqual(launcher.launch(False),0);spawn.assert_not_called();opened.assert_called_once_with(8787,False)
 def test_diagnostic_has_no_user_files_or_credentials(self):
  with patch('launcher.dependencies',return_value=[]),patch('launcher.existing_service',return_value=None):
   value=launcher.diagnostics();self.assertEqual(set(value),{'version','python','dependencies','service'});self.assertEqual(value['service'],{'status':'stopped'})
 def test_start_waits_for_matching_health_before_opening(self):
  process=unittest.mock.Mock();process.poll.return_value=None;process.wait.return_value=0
  sequence=[]
  def ready(_):sequence.append('ready');return health(storage.data_dir())
  with tempfile.TemporaryDirectory() as d,patch('launcher.ROOT',Path(d)),patch('launcher.dependencies',return_value=[]),patch('launcher.existing_service',return_value=None),patch('launcher.free_port',return_value=8788),patch('launcher.probe',side_effect=ready),patch('launcher.open_page',side_effect=lambda *_:sequence.append('open')),patch('launcher.subprocess.Popen',return_value=process):
   self.assertEqual(launcher.launch(False),0);self.assertEqual(sequence,['ready','open'])
 def test_start_failure_does_not_open_page(self):
  process=unittest.mock.Mock();process.poll.return_value=1
  with tempfile.TemporaryDirectory() as d,patch('launcher.ROOT',Path(d)),patch('launcher.dependencies',return_value=[]),patch('launcher.existing_service',return_value=None),patch('launcher.free_port',return_value=8788),patch('launcher.open_page') as opened,patch('launcher.subprocess.Popen',return_value=process):
   with self.assertRaisesRegex(RuntimeError,'后台启动失败'):launcher.launch(False)
   opened.assert_not_called()
 def test_streamed_fingerprint(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'file';p.write_bytes(b'pdf data'*10000)
   self.assertEqual(fingerprint(p),hashlib.sha256(p.read_bytes()).hexdigest())
 def test_new_key_is_session_only_by_default(self):
  with tempfile.TemporaryDirectory() as d:
   store=SettingsStore(Path(d)/'model.json');store.save({'provider':'openai','model':'test','api_key':'private'})
   self.assertFalse(store.path.exists());self.assertTrue(store.public()['session_only'])

class CacheTests(unittest.TestCase):
 setUp=AutoTests.setUp
 tearDown=AutoTests.tearDown
 client=FinalRegressions.client
 def test_prompt_and_algorithm_change_recheck_same_task(self):
  calls=[];q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{'provider':'fake','model':'test'},lambda _:self.client(calls))
  try:
   a=q.start('Training improved recall (Smith, 2023).',[self.s['id']]);q.wait(a['id']);task_id=q.get(a['id'])['task_id'];calls.clear()
   b=q.start('Training improved recall (Smith, 2023).',[self.s['id']],task_id);q.wait(b['id']);self.assertNotIn('review',calls)
   for field in ['REVIEW_PROMPT','REVIEW_VERSION','VERSION','PROMPT_VERSION']:
    calls.clear()
    with patch('app.automatic_review.'+field,'new-'+field):
     job=q.start('Training improved recall (Smith, 2023).',[self.s['id']],task_id);q.wait(job['id']);self.assertEqual(q.get(job['id'])['status'],'completed');self.assertIn('review',calls,field)
  finally:q.close()
 def test_scope_and_fingerprint_change_cache_key(self):
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'})
  task=self.tasks.create('Claim (Smith, 2023).',[self.s]);package=self.evidence.prepare(task['id']);loc=task['locations'][0];model={'name':'test'}
  key=review_cache_key(loc,package,model)
  altered={**loc,'claim_text':'Different claim'};self.assertNotEqual(key,review_cache_key(altered,package,model))
  package={**package,'sources':{sid:copy.deepcopy(package['sources'][sid]) for sid in package['sources']}}
  for source in package['sources'].values():source['sha256']='changed'
  self.assertNotEqual(key,review_cache_key(loc,package,model))
 def test_completed_jobs_release_secrets_and_events(self):
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{'provider':'fake','model':'test','api_key':'private'},lambda _:self.client([]))
  try:
   job=q.start('Claim (Smith, 2023).',[self.s['id']]);q.wait(job['id'])
   deadline=time.monotonic()+1
   while job['id'] in q.events and time.monotonic()<deadline:time.sleep(.01)
   self.assertNotIn(job['id'],q.events);self.assertNotIn(job['id'],q.snapshots)
  finally:q.close()
 def test_shutdown_marks_running_job_interrupted(self):
  entered=threading.Event()
  class Slow:
   def call(_,prompt,event):entered.set();event.wait(2);raise ValueError('cancelled')
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{'provider':'fake','model':'test'},lambda _:Slow())
  job=q.start('Claim (Smith, 2023).',[self.s['id']]);self.assertTrue(entered.wait(1));q.close()
  self.assertEqual(q.get(job['id'])['status'],'interrupted')

class HealthTests(HttpTests):
 def test_health_contains_no_credentials_paths_or_manuscripts(self):
  status,body=self.request('GET','/api/health');value=json.loads(body)
  self.assertEqual(status,200);self.assertEqual(set(value),{'app','version','instance','status'});self.assertEqual(value['status'],'ready')
