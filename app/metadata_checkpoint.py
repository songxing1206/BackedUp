"""Durable bibliography request checkpoints; retries never resubmit uncertain work."""
from .request_budget import BudgetExceeded
from datetime import datetime,timezone

def resolve_metadata(source,sha,text,request,verify,save):
 attempt=source.get('metadata_attempt',{})
 if attempt.get('pdf_sha256')!=sha:attempt={}
 if attempt.get('state') in {'requested','failed'}:
  raise ValueError('书目信息尚未确认：上次请求失败或中断，已停止重复自动调用；请打开PDF并手动确认标题、作者和年份')
 if 'response' not in attempt:
  attempt=dict(pdf_sha256=sha,state='requested',created_at=datetime.now(timezone.utc).isoformat())
  source['metadata_attempt']=attempt;save(source)
  try:
   attempt['response']=request();attempt['state']='received';save(source)
  except BudgetExceeded:
   attempt['state']='budget_paused';save(source);raise
  except Exception:
   attempt['state']='failed';save(source);raise
 try:
  fields=verify(attempt['response'],text)
 except Exception:
  attempt['state']='failed';save(source);raise
 source.update(fields);source['metadata_pdf_sha256']=sha;attempt['state']='verified';save(source)
