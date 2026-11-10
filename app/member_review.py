"""Dependency checks and conservative merging for per-source retries."""
import copy,hashlib,json
from .evidence_storage import source_summary

def member_keys(loc,package,model,versions):
 return {sid:hashlib.sha256(json.dumps([loc.get('claim_text',loc['sentence']),loc['context'],[(m['author'],m['year'],m['match'].get('assigned_by_user',False)) for m in loc['members'] if m['match'].get('source_id')==sid],source_summary(package['sources'],sid)['sha256'],model,versions],ensure_ascii=False,sort_keys=True).encode()).hexdigest() for sid in {m['match']['source_id'] for m in loc['members'] if m['match']['status']=='matched'}}

def reusable_sources(previous,keys,verify):
 claims=previous.get('claims',[])
 if not claims:return set()
 reused=set()
 for sid,key in keys.items():
  if previous.get('member_keys',{}).get(sid)!=key:continue
  try:
   for claim in claims:
    judgments=[j for j in claim['source_judgments'] if j['source_id']==sid]
    if len(judgments)!=1 or judgments[0]['status'] not in {'支持','部分支持','存在矛盾','不支持'}:raise ValueError()
    if judgments[0].get('verification_error'):raise ValueError()
    if judgments[0]['status']!='不支持' and not judgments[0].get('evidence'):raise ValueError()
    for evidence in judgments[0].get('evidence',[]):verify(sid,evidence)
   reused.add(sid)
  except (ValueError,KeyError,TypeError):continue
 return reused

def merge_members(previous,new,reused,allowed):
 claims=copy.deepcopy(previous['claims']);updates={c['id']:c for c in new.get('claims',[])}
 # Keep the original claim partition: unmatched or altered claims cannot silently replace it.
 for claim in claims:
  update=updates.get(claim['id'],{})
  incoming=update.get('source_judgments',[]) if update.get('text')==claim['text'] else []
  retained=[j for j in claim['source_judgments'] if j['source_id'] in reused]
  claim['source_judgments']=retained+[j for j in incoming if j['source_id'] in allowed-reused]
  seen={j['source_id'] for j in claim['source_judgments']}
  claim['source_judgments'] += [dict(source_id=sid,status='无法判断',reason='本次补查尚未完成该来源判断',evidence=[]) for sid in sorted(allowed-seen)]
 statuses=[j['status'] for c in claims for j in c['source_judgments']]
 status='无法判断' if not statuses or '无法判断' in statuses else '存在矛盾' if '存在矛盾' in statuses else '支持' if all(any(j['status']=='支持' for j in c['source_judgments']) for c in claims) else '不支持' if all(s=='不支持' for s in statuses) else '部分支持'
 return dict(location_id=new.get('location_id',previous['location_id']),claims=claims,combined=dict(status=status,reason='已保留有效来源判断并合并本次补查；请查看逐来源证据及限制'),suggestion=None,coverage=new.get('coverage',previous.get('coverage','retrieved')))
