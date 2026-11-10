import io,json,os,tempfile,unittest,zipfile,shutil
from pathlib import Path
from unittest.mock import patch
from app import storage
from app.report_archive import write_report
from test_evidence import EvidenceTests
from test_evidence_http import HttpTests

class StorageTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.env=patch.dict(os.environ,{'BACKEDUP_DATA_HOME':str(self.root/'user'),'BACKEDUP_CACHE_HOME':str(self.root/'cache')});self.env.start()
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def test_migrate_once_preserves_original_and_excludes_key(self):
  old=self.root/'output';(old/'assets').mkdir(parents=True);(old/'private').mkdir();(old/'assets/a.pdf').write_bytes(b'pdf')
  (old/'assets/a.json').write_text(json.dumps({'path':str(old/'assets/a.pdf')}))
  (old/'private/model.json').write_text(json.dumps({'provider':'openai','model':'test','api_key':'private'}))
  target=storage.initialize(old)
  self.assertTrue((old/'assets/a.pdf').exists());self.assertEqual(json.loads((target/'assets/a.json').read_text())['path'],str(target/'assets/a.pdf'))
  self.assertNotIn('private', (target/'settings/model.json').read_text());self.assertEqual(json.loads((target/'settings/model.json').read_text())['api_key'],'')
  (old/'assets/a.pdf').write_bytes(b'new');storage.initialize(old);self.assertEqual((target/'assets/a.pdf').read_bytes(),b'pdf')
 def test_format_versions_are_isolated(self):
  one=storage.initialize()
  with patch('app.storage.DATA_VERSION',2):two=storage.initialize()
  self.assertNotEqual(one,two);self.assertTrue(one.exists());self.assertEqual(storage.history_namespaces(),['data-v1','data-v2'])
 def test_data_root_is_private(self):
  storage.initialize()
  if os.name!='nt':self.assertEqual(storage.data_home().stat().st_mode&0o777,0o700)
 def test_failed_import_does_not_publish_or_remove_original(self):
  old=self.root/'output';(old/'assets').mkdir(parents=True);(old/'assets/a.json').write_text('invalid')
  with self.assertRaises(ValueError):storage.initialize(old)
  self.assertFalse(storage.data_dir().exists());self.assertTrue((old/'assets/a.json').exists())
 def test_reject_namespace_traversal(self):
  storage.initialize()
  with self.assertRaises(ValueError):storage.namespace_dir('../outside')

class ArchiveTests(unittest.TestCase):
 def setUp(self):
  self.fixture=EvidenceTests();self.fixture.setUp();f=self.fixture
  for source in f.s:
   old=Path(source['path']);new=f.assets.root/old.name;old.rename(new);source['path']=str(new);f.assets.save(source)
  f.t=f.tasks.get(f.t['id']);f.t['sources']=f.s;f.tasks.save(f.t)
 def tearDown(self):self.fixture.tearDown()
 def test_backup_restore_keeps_report_pdf_and_verified_highlight(self):
  from app.backup import create_backup,restore_backup
  from app.tasks import TaskStore
  f=self.fixture;task=f.service.import_result(f.t['id'],f.result())
  (f.root/'storage.json').write_text('{"data_version":1}')
  with tempfile.TemporaryDirectory() as d:
   backup=Path(d)/'backup.zip';target=Path(d)/'restored';create_backup(f.root,backup);restore_backup(backup,target)
   restored=TaskStore(target/'tasks').get(task['id']);self.assertTrue(TaskStore(target/'tasks').history())
   output=io.BytesIO();write_report(restored,target,output)
   with zipfile.ZipFile(output) as archive:
    self.assertTrue(any(n.endswith('.pdf') for n in archive.namelist()));self.assertTrue(any(n.endswith('.png') for n in archive.namelist()))
   self.assertTrue(Path(task['sources'][0]['path']).exists())
 def test_portable_report_has_pdf_and_highlight_no_backend_or_paths(self):
  f=self.fixture;task=f.service.import_result(f.t['id'],f.result());task['text']='<script>bad()</script>';task['locations'][0]['sentence']='<script>bad()</script>'
  output=io.BytesIO();write_report(task,f.assets.root.parent,output)
  with zipfile.ZipFile(output) as archive:
   names=archive.namelist();markup=archive.read('report.html').decode()
   self.assertTrue(any(n.endswith('.pdf') for n in names));self.assertTrue(any(n.endswith('.png') for n in names));self.assertNotIn('127.0.0.1',markup);self.assertNotIn(str(f.assets.root),markup);self.assertNotIn('<script>',markup);self.assertIn('&lt;script&gt;',markup)
   with tempfile.TemporaryDirectory() as d:
    archive.extractall(d);moved=Path(d)/'report.html';self.assertTrue(moved.exists());self.assertTrue(all((Path(d)/n).exists() for n in names))
 def test_changed_pdf_never_exports_old_highlight(self):
  f=self.fixture;task=f.service.import_result(f.t['id'],f.result());source=task['sources'][0];path=Path(source['path']);path.write_bytes(path.read_bytes()+b'changed')
  with self.assertRaisesRegex(ValueError,'变化|指纹'):write_report(task,f.assets.root.parent,io.BytesIO())
 def test_stale_result_not_presented_as_current_verdict(self):
  f=self.fixture;task=f.service.import_result(f.t['id'],f.result());task['evidence_review']['locations'][0]['state']='stale';output=io.BytesIO();write_report(task,f.root,output)
  with zipfile.ZipFile(output) as archive:
   markup=archive.read('report.html').decode();self.assertIn('综合结论：尚未完成',markup);self.assertFalse(any(n.endswith('.png') for n in archive.namelist()))
 def test_arbitrary_file_not_exported(self):
  f=self.fixture;task=f.service.import_result(f.t['id'],f.result());task['sources'][0]['path']='/etc/hosts'
  with self.assertRaisesRegex(ValueError,'目录'):write_report(task,f.assets.root.parent,io.BytesIO())

class HistoryHttpTests(HttpTests):
 def setUp(self):
  super().setUp();f=self.env
  for source in f.s:
   old=Path(source['path']);new=f.assets.root/old.name;old.rename(new);source['path']=str(new);f.assets.save(source)
  f.t=f.tasks.get(f.t['id']);f.t['sources']=f.s;f.tasks.save(f.t)
  f.service.import_result(f.t['id'],f.result())
  self.cache=patch('server.cache_dir',return_value=f.root/'test-cache');self.cache.start()
 def tearDown(self):self.cache.stop();super().tearDown()
 def test_report_bundle_http(self):
  status,body=self.request('GET',f'/api/tasks/{self.env.t["id"]}/report-bundle');self.assertEqual(status,200)
  with zipfile.ZipFile(io.BytesIO(body)) as archive:self.assertIn('report.html',archive.namelist())
 def test_older_namespace_is_read_only(self):
  f=self.env
  with patch('server.namespace_dir',return_value=f.root):
   status,body=self.request('GET',f'/api/history/data-v0/{f.t["id"]}/report');self.assertEqual(status,200);self.assertIn('只读归档'.encode(),body)
   status,_=self.request('POST',f'/api/history/data-v0/{f.t["id"]}/report',{});self.assertEqual(status,404)
