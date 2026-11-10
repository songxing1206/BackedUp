import json,tempfile,unittest
from pathlib import Path
from app.tasks import TaskStore
from app.history_delete import delete_record

class HistoryDeleteTests(unittest.TestCase):
 def test_delete_persists_and_keeps_shared_assets(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);store=TaskStore(root/'tasks');a=store.create('One (Smith, 2023).',[]);b=store.create('Two (Doe, 2020).',[])
   for folder in ['assets','checks','evidence']:(root/folder).mkdir()
   (root/'assets/shared.pdf').write_bytes(b'pdf')
   (root/'checks/job.json').write_text(json.dumps({'task_id':a['id'],'status':'partial'}))
   (root/'evidence'/f"{a['id']}.json").write_text('{}')
   self.assertTrue(delete_record(root,a['id'])['ok'])
   self.assertEqual([x['id'] for x in TaskStore(root/'tasks').history()],[b['id']])
   self.assertTrue((root/'assets/shared.pdf').exists());self.assertFalse((root/'checks/job.json').exists())
   self.assertFalse((root/'evidence'/f"{a['id']}.json").exists())
   with self.assertRaisesRegex(ValueError,'记录已删除'):store.save(a)
 def test_active_older_job_blocks_delete(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);store=TaskStore(root/'tasks');a=store.create('One (Smith, 2023).',[]);(root/'checks').mkdir()
   for name,status,date in [('old','running','2020'),('new','partial','2021')]:
    (root/'checks'/f'{name}.json').write_text(json.dumps({'id':name,'task_id':a['id'],'status':status,'created_at':date}))
   self.assertTrue(store.history()[0]['is_checking'])
   with self.assertRaisesRegex(ValueError,'正在检查，请稍后'):delete_record(root,a['id'])
   self.assertTrue(store.path(a['id']).exists())
 def test_rejects_invalid_id(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):delete_record(Path(d),'../../anything')
