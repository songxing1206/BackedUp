"""Task persistence, stable identifiers and post-report assignments."""
from .text_io import read_text_compat, write_text_utf8
import json,re,uuid,threading,copy
from datetime import datetime,timezone
from pathlib import Path
from .citations import extract_locations
from .matching import match_member

class TaskStore:
 def __init__(self,root,split_grouped=True):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self.split_grouped=split_grouped
 def path(self,task_id):
  if not re.fullmatch(r'[a-f0-9]{32}',task_id):raise ValueError('无效任务ID')
  return self.root/(task_id+'.json')
 def save(self,task):
  target=self.path(task['id']);
  if target.with_suffix('.deleted').exists():raise ValueError('记录已删除')
  tmp=target.with_suffix('.tmp');write_text_utf8(tmp, json.dumps(task,ensure_ascii=False,indent=2));tmp.replace(target)
 def get(self,task_id):
  try:
   from .evidence import normalize_legacy_task
   return normalize_legacy_task(json.loads(read_text_compat(self.path(task_id))))
  except FileNotFoundError:raise ValueError('任务不存在') from None
 def history(self):
  rows=[];jobs={};active_jobs=[]
  for path in (self.root.parent/'checks').glob('*.json'):
   try:
    job=json.loads(read_text_compat(path));active_jobs.append(job);tid=job.get('task_id')
    if tid and job.get('created_at','')>jobs.get(tid,{}).get('created_at',''):jobs[tid]=job
   except (ValueError,OSError):continue
  with self.lock:
   for path in self.root.glob('*.json'):
    try:
     from .evidence import normalize_legacy_task
     task=normalize_legacy_task(json.loads(read_text_compat(path)))
     if not re.fullmatch(r'[a-f0-9]{32}',task.get('id','')):continue
     if task.get('id')=='a99e8f9e1f35484db7bc895dd56b10f4' or any(s.get('metadata_source')=='demo' or s.get('filename') in ('smith-2023-demo.pdf','doe-2021-demo.pdf') for s in task.get('sources',[])):continue
     # History contains only summary data; no keys, manuscript body or evidence excerpts.
     title=next((line.strip().lstrip('#').strip() for line in task.get('text','').splitlines() if line.strip()),'未命名稿件')[:80]
     rows.append(dict(id=task['id'],check_id=jobs.get(task['id'],{}).get('id'),created_at=task.get('created_at',''),title=title,is_checking=any(j.get('task_id')==task['id'] and j.get('status') in {'queued','running'} for j in active_jobs),
      locations=[dict(id=l['id'],members=[dict(author=m.get('author',''),year=m.get('year',''),match=m['match']) for m in l['members']]) for l in task.get('locations',[])],
      evidence_review=dict(locations=[dict(location_id=r['location_id'],state=r.get('state'),material_complete=r.get('material_complete'),combined=dict(status=r.get('combined',{}).get('status')),display_result=copy.deepcopy(r.get('display_result'))) for r in task.get('evidence_review',{}).get('locations',[])])))
    except (ValueError,KeyError,TypeError,OSError):continue
  return sorted(rows,key=lambda r:r['created_at'],reverse=True)
 def summarize(self,task):
  summary={x:0 for x in ['matched','needs_assignment','unmatched','missing_attachment']}
  for loc in task['locations']:
   for member in loc['members']:summary[member['match']['status']]+=1
  task['summary']=summary;task['summary']['locations']=len(task['locations']);task['summary']['members']=sum(summary[x] for x in ['matched','needs_assignment','unmatched','missing_attachment'])
  task['state']='finished_partial' if any(summary[x] for x in ['needs_assignment','unmatched','missing_attachment']) else 'finished'
 def create(self,text,sources):
  with self.lock:
   if not isinstance(text,str) or not text.strip():raise ValueError('请提供待检验文本')
   if len(text)>300000:raise ValueError('稿件超过300,000字符，请拆分；未截断或部分处理。')
   parsed=extract_locations(text,self.split_grouped)
   task=dict(schema_version=1,citation_unit_version=parsed.get('citation_unit_version',1),id=uuid.uuid4().hex,created_at=datetime.now(timezone.utc).isoformat(),text=text,sources=copy.deepcopy(sources),locations=parsed['locations'],warnings=parsed['warnings'],assignment_history=[],revision=1)
   for loc in task['locations']:
    for member in loc['members']:member['match']=match_member(member,task['sources'])
   self.summarize(task);self.save(task);return task
 def assign(self,task_id,member_id,source_id):
  with self.lock:
   task=self.get(task_id);source=next((s for s in task['sources'] if s['id']==source_id),None)
   if not source:raise ValueError('来源不属于当前任务')
   selected=next((m for l in task['locations'] for m in l['members'] if m['id']==member_id),None)
   if not selected:raise ValueError('引用成员不存在')
   if not all(source.get(f) for f in ['title','authors','year']):raise ValueError('请先补全候选来源的标题、作者与年份，不能只按文件名指定。')
   # Same bibliographic marker re-used in this task resolves together.
   changed=[]
   for loc in task['locations']:
    for member in loc['members']:
     if member['author']==selected['author'] and member['year']==selected['year']:
      previous=copy.deepcopy(member['match'])
      member['match']=dict(status='matched' if source.get('attachment_status')=='available' else 'missing_attachment',source_id=source_id,reason='作者二次指定来源；未进行语义核查。',candidates=previous['candidates'],assigned_by_user=True)
      changed.append(dict(member_id=member['id'],previous=previous))
   from .evidence import invalidate_review
   invalidate_review(task,{loc['id'] for loc in task['locations'] if any(m['id'] in {x['member_id'] for x in changed} for m in loc['members'])})
   task['assignment_history'].append(dict(source_id=source_id,changes=changed,at=datetime.now(timezone.utc).isoformat()))
   task['revision']+=1;self.summarize(task);self.save(task);return task
 def update_source(self,task_id,source_id,fields):
  with self.lock:
   task=self.get(task_id);source=next((x for x in task['sources'] if x['id']==source_id),None)
   if not source:raise ValueError('来源不属于任务')
   for field in ['title','authors','year','doi']:source[field]=str(fields.get(field,source.get(field,'')))[:2000]
   from .evidence import invalidate_review
   invalidate_review(task,{l['id'] for l in task['locations'] if any(m['match'].get('source_id')==source_id for m in l['members'])})
   source['metadata_verified']=bool(all(source.get(f) for f in ['title','authors','year']));source['metadata_source']='user_confirmed'
   for loc in task['locations']:
    for m in loc['members']:
     if not m['match'].get('assigned_by_user'):m['match']=match_member(m,task['sources'])
   task['revision']+=1;self.summarize(task);self.save(task);return task
