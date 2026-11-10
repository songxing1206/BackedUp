import json,tempfile,unittest,zipfile,hashlib,os
from pathlib import Path
from app.backup import create_backup,restore_backup

class BackupTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.original=self.root/'data-v1';self.original.mkdir()
  (self.original/'storage.json').write_text('{"data_version":1}')
  for name in ['assets','tasks','settings']:(self.original/name).mkdir()
  (self.original/'assets/a.pdf').write_bytes(b'fictional PDF bytes')
  (self.original/'tasks/a.json').write_text(json.dumps({'schema_version':1,'path':str(self.original/'assets/a.pdf'),'text':'fictional manuscript'}))
  (self.original/'settings/model.json').write_text(json.dumps({'provider':'openai','model':'fixture','api_key':'never-backup-this-key'}))
  self.backup=self.root/'backup.zip'
 def tearDown(self):self.temp.cleanup()
 def test_restore_preserves_bytes_history_and_rewrites_paths(self):
  create_backup(self.original,self.backup);target=self.root/'restored';restore_backup(self.backup,target)
  self.assertEqual((target/'assets/a.pdf').read_bytes(),(self.original/'assets/a.pdf').read_bytes())
  self.assertEqual(json.loads((target/'tasks/a.json').read_text())['path'],str((target/'assets/a.pdf').resolve()))
  self.assertNotIn('never-backup', (target/'settings/model.json').read_text());self.assertTrue((self.original/'tasks/a.json').exists())
 def test_existing_target_and_backup_not_overwritten(self):
  create_backup(self.original,self.backup)
  with self.assertRaises(ValueError):create_backup(self.original,self.backup)
  with self.assertRaises(ValueError):restore_backup(self.backup,self.original)
 def test_corrupt_backup_does_not_publish_target(self):
  create_backup(self.original,self.backup);bad=self.root/'corrupt.zip'
  with zipfile.ZipFile(self.backup) as source,zipfile.ZipFile(bad,'w') as output:
   for name in source.namelist():output.writestr(name,b'changed' if name.endswith('.pdf') else source.read(name))
  target=self.root/'restored'
  with self.assertRaisesRegex(ValueError,'完整性'):restore_backup(bad,target)
  self.assertFalse(target.exists());self.assertTrue((self.original/'assets/a.pdf').exists())
 def test_incompatible_version_rejected_without_overwriting(self):
  create_backup(self.original,self.backup)
  with self.assertRaisesRegex(ValueError,'不兼容'):restore_backup(self.backup,self.root/'v2',expected_version=2)
 def test_zip_traversal_rejected(self):
  payload=b'unsafe';manifest={'backup_version':1,'data_version':1,'original_root':str(self.original),'files':[{'path':'../escape','bytes':6,'sha256':hashlib.sha256(payload).hexdigest()}]}
  with zipfile.ZipFile(self.backup,'w') as archive:archive.writestr('manifest.json',json.dumps(manifest));archive.writestr('../escape',payload)
  with self.assertRaisesRegex(ValueError,'路径'):restore_backup(self.backup,self.root/'restored')
  self.assertFalse((self.root/'escape').exists())
 def test_external_attachment_and_running_check_rejected(self):
  task=self.original/'tasks/a.json';task.write_text(json.dumps({'path':str(self.root/'external.pdf')}))
  with self.assertRaisesRegex(ValueError,'外部|缺失'):create_backup(self.original,self.backup)
  self.assertFalse(self.backup.exists())
  task.write_text('{}');(self.original/'checks').mkdir();(self.original/'checks/running.json').write_text('{"status":"running"}')
  with self.assertRaisesRegex(ValueError,'取消'):create_backup(self.original,self.backup)
 def test_symlink_directory_rejected(self):
  (self.root/'outside').mkdir()
  try:(self.original/'evidence').symlink_to(self.root/'outside',target_is_directory=True)
  except OSError as error:
   if os.name=='nt' and getattr(error,'winerror',None)==1314:self.skipTest('Windows 当前账户没有创建符号链接权限')
   raise
  with self.assertRaisesRegex(ValueError,'符号链接'):create_backup(self.original,self.backup)
