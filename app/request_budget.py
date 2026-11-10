"""Persist a conservative per-run allowance before any model request."""
from .text_io import write_text_utf8
import json
from pathlib import Path

class BudgetExceeded(ValueError):pass

def atomic_json(path,value):
 path=Path(path);temp=path.with_suffix('.tmp');write_text_utf8(temp, json.dumps(value,ensure_ascii=False));temp.replace(path)

def reserve(job,input_bound,output_bound):
 usage=job.setdefault('budget_usage',dict(requests=0,reserved_tokens=0))
 request_limit=job.get('max_requests');token_limit=job.get('token_budget')
 if (request_limit is not None and usage['requests']>=request_limit) or (token_limit is not None and usage['reserved_tokens']+input_bound+output_bound>token_limit):
  raise BudgetExceeded('已达到本轮调用／token预算，已完成结果保留；请查看用量后再决定是否继续')
 usage['requests']+=1;usage['reserved_tokens']+=input_bound+output_bound
