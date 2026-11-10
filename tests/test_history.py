import json,tempfile,unittest
from pathlib import Path
from app.tasks import TaskStore
class HistoryTests(unittest.TestCase):
 def test_persistent_history_is_compact_and_excludes_demo(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);store=TaskStore(root/'tasks');task=store.create('Private manuscript (Smith, 2023).',[])
   task['evidence_review']={'locations':[{'location_id':'C001','state':'complete','combined':{'status':'支持'},'claims':[{'secret':'quote'}]}]};store.save(task)
   jobs=root/'checks';jobs.mkdir();(jobs/'job.json').write_text(json.dumps({'id':'a'*32,'task_id':task['id'],'created_at':'2026-10-07','key':'secret-key','text':'private body'}))
   demo=store.create('Example (Smith, 2023).',[]);demo['sources']=[{'filename':'smith-2023-demo.pdf'}];store.save(demo)
   rows=TaskStore(root/'tasks').history();self.assertEqual(len(rows),1);self.assertEqual(rows[0]['check_id'],'a'*32)
   self.assertNotIn('text',rows[0]);self.assertNotIn('secret-key',json.dumps(rows));self.assertNotIn('claims',rows[0]['evidence_review']['locations'][0])
