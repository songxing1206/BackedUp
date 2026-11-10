"""Deterministic normalization for the fixed review JSON protocol.

This module never creates a semantic judgment or evidence quotation.  It only
maps explicit unambiguous aliases, fills mechanically derivable fields and
aggregates a missing top-level label from a complete judgment matrix.
"""
import copy,re

STATUSES={'支持','部分支持','不支持','存在矛盾','无法判断'}
ROLES={'支持','限制','矛盾'}

def _key(value):
 return re.sub(r'[\s_-]+','',str(value or '').strip().casefold())

STATUS_ALIASES={
 '支持':'支持','support':'支持','supported':'支持','fullysupported':'支持','fullsupport':'支持',
 '部分支持':'部分支持','partial':'部分支持','partialsupport':'部分支持','partiallysupported':'部分支持','partiallysupported':'部分支持',
 '不支持':'不支持','unsupported':'不支持','notsupported':'不支持','doesnotsupport':'不支持',
 '存在矛盾':'存在矛盾','contradiction':'存在矛盾','contradicted':'存在矛盾','contradicts':'存在矛盾','conflict':'存在矛盾',
 '无法判断':'无法判断','unknown':'无法判断','uncertain':'无法判断','inconclusive':'无法判断','insufficientevidence':'无法判断','notenoughevidence':'无法判断',
 # Absence from a supplied passage is not proof of whole-paper non-support.
 'notinpaper':'无法判断','notfound':'无法判断','absent':'无法判断','notmentioned':'无法判断',
}
ROLE_ALIASES={
 '支持':'支持','support':'支持','supporting':'支持',
 '限制':'限制','limitation':'限制','limit':'限制','qualifier':'限制','qualification':'限制',
 '矛盾':'矛盾','contradiction':'矛盾','contradicting':'矛盾','conflict':'矛盾',
}

def normalize_status(value):return STATUS_ALIASES.get(_key(value),value)
def normalize_role(value):return ROLE_ALIASES.get(_key(value),value)

def aggregate_status(claims,allowed=None):
 """Aggregate only a complete matrix of explicit, normalized judgments."""
 if not isinstance(claims,list) or not claims:return None
 statuses=[]
 for claim in claims:
  judgments=claim.get('source_judgments') if isinstance(claim,dict) else None
  if not isinstance(judgments,list) or not judgments:return None
  if allowed is not None:
   ids=[j.get('source_id') for j in judgments if isinstance(j,dict)]
   if len(ids)!=len(allowed) or set(ids)!=set(allowed):return None
  for judgment in judgments:
   status=judgment.get('status') if isinstance(judgment,dict) else None
   if status not in STATUSES:return None
   statuses.append(status)
 if not statuses:return None
 if '无法判断' in statuses:return '无法判断'
 if '存在矛盾' in statuses:return '存在矛盾'
 if all(status=='支持' for status in statuses):return '支持'
 if all(status=='不支持' for status in statuses):return '不支持'
 return '部分支持'

def normalize_review_response(row,allowed=None):
 """Return a compatibility-normalized copy and preserve original labels."""
 if not isinstance(row,dict):return row
 result=copy.deepcopy(row);adjusted_for_evidence=False
 claims=result.get('claims')
 if isinstance(claims,list):
  for claim in claims:
   if not isinstance(claim,dict):continue
   judgments=claim.get('source_judgments')
   if not isinstance(judgments,list):continue
   for judgment in judgments:
    if not isinstance(judgment,dict):continue
    original=judgment.get('status');status=normalize_status(original)
    if status!=original:
     judgment['model_original_status']=original;judgment['status']=status;judgment['label_adjustment']='explicit_status_alias'
    evidences=judgment.get('evidence')
    if isinstance(evidences,list):
     for evidence in evidences:
      if not isinstance(evidence,dict):continue
      role=evidence.get('role');normalized_role=normalize_role(role)
      if normalized_role!=role:
       evidence['model_original_role']=role;evidence['role']=normalized_role
      if not evidence.get('role') and judgment.get('status') in {'支持','存在矛盾'}:
       evidence['role']='支持' if judgment['status']=='支持' else '矛盾'
       evidence['role_adjustment']='derived_from_unambiguous_judgment'
    if judgment.get('status') in {'支持','部分支持','存在矛盾'} and not evidences:
     judgment['model_original_status']=judgment['status'];judgment['status']='无法判断'
     judgment['reason']='模型给出了肯定性语义判断，但没有返回可验证证据；该子判断未恢复。'
     judgment['protocol_error']='required_evidence_missing';adjusted_for_evidence=True
 combined=result.get('combined')
 if not isinstance(combined,dict):combined={};result['combined']=combined
 original=combined.get('status');status=normalize_status(original)
 if status!=original and status in STATUSES:
  combined['model_original_status']=original;combined['status']=status;combined['label_adjustment']='explicit_status_alias'
 if not isinstance(combined.get('reason'),str):combined['reason']=''
 if adjusted_for_evidence:
  aggregated=aggregate_status(claims,allowed)
  if aggregated:
   combined.update(model_original=copy.deepcopy(combined),status=aggregated,reason='部分模型判断缺少必要证据；已保留可验证子判断，未验证部分标记为无法判断。',aggregation='complete_judgment_matrix')
 elif original in {None,''}:
  aggregated=aggregate_status(claims,allowed)
  if aggregated:
   combined.update(status=aggregated,reason=combined['reason'] or '顶层结论缺失；依据完整逐源子判断矩阵确定性聚合。',aggregation='complete_judgment_matrix')
 return result
