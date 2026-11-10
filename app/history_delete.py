"""Delete one history task; shared source assets and reusable caches stay intact."""
from .text_io import read_text_compat
import json
from contextlib import nullcontext
from .tasks import TaskStore

def delete_record(root,task_id,queue=None):
 store=TaskStore(root/'tasks');target=store.path(task_id)
 with queue.lock if queue else nullcontext():
  with store.lock:
   store.get(task_id)
   jobs=[]
   for path in (root/'checks').glob('*.json'):
    try:job=json.loads(read_text_compat(path))
    except (ValueError,OSError):continue
    if job.get('task_id')==task_id:
     if job.get('status') in {'queued','running'}:raise ValueError('正在检查，请稍后')
     jobs.append(path)
   # Tombstone prevents stale writers from recreating a removed task.
   target.with_suffix('.deleted').touch()
   target.unlink()
   for path in jobs:path.unlink(missing_ok=True)
   for path in (root/'evidence').glob(task_id+'*'):
    if path.is_file():path.unlink()
 return {'ok':True,'deleted_id':task_id}
