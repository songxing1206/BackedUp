"""Local source readiness diagnostics; never invokes a model."""
from pathlib import Path
from .citations import extract_locations
from .matching import match_member,surname,author_key,year_parts
from .text_io import repair_legacy_mojibake

def filename_candidates(member,sources):
 """Return filename hints that were not strong enough for automatic matching."""
 author=surname(member.get('author'));year=year_parts(member.get('year'))[0]
 if not author or not year:return []
 rows=[]
 for source in sources:
  name=source.get('filename','')
  if source.get('attachment_status')=='available' and author in author_key(name) and year in name:
   rows.append(dict(source_id=source['id'],title=source.get('title') or name,reason='文件名含作者与年份，但书目信息尚未确认'))
 return rows

def source_preflight(text, sources, location_limit=None):
 locations=extract_locations(text)['locations']
 if location_limit:locations=locations[:location_limit]
 issues=[];normalized=[]
 for source in sources:
  row=dict(source);row['filename']=repair_legacy_mojibake(row.get('filename',''));path=row.get('path')
  if row.get('attachment_status')=='available' and (not path or not Path(path).is_file()):row['attachment_status']='missing'
  normalized.append(row)
  if row.get('attachment_status')!='available':
   locked=any('密码' in w for w in row.get('warnings',[]))
   issues.append(dict(source_id=row['id'],kind='encrypted' if locked else 'unreadable' if row.get('attachment_status')=='unreadable' else 'missing_file',label=row.get('filename') or row.get('title') or row['id'],message='PDF 需要密码，无法读取' if locked else 'PDF 不可读' if row.get('attachment_status')=='unreadable' else 'PDF 文件缺失',advice='请替换为可正常打开的 PDF；本次跳过该文件。',action='replace_pdf' if locked or row.get('attachment_status')=='unreadable' else 'upload_pdf'))
 ready=0
 for loc in locations:
  available=False
  for member in loc['members']:
   match=match_member(member,normalized)
   if match['status']=='matched':available=True
   if match['status'] in {'unmatched','needs_assignment'}:
    candidates=match['candidates']
    if not candidates:candidates=filename_candidates(member,normalized)
    year=match.get('year_diagnosis',{})
    if year.get('status')=='confirmed_error':kind,message,advice,action='citation_year_error','引用年份错误',year['reason']+'；请修正文稿年份或确认其他来源。','resolve_identity'
    elif year.get('status')=='ambiguous' and candidates and year.get('cited_year')!=year.get('source_year'):kind,message,advice,action='year_ambiguous','引用年份存在歧义',year['reason']+'；请人工确认适用年份。','resolve_identity'
    elif year.get('status')=='mismatch':kind,message,advice,action='year_mismatch','PDF 年份不匹配',year['reason']+'；该 PDF 不会用于本条核查，请上传与引用年份一致的来源。','upload_pdf'
    elif len(candidates)>1:kind,message,advice,action='ambiguous_source','存在多个候选 PDF，来源有歧义','请选择与该引用对应的 PDF。','select_candidate'
    elif candidates:
     candidate=next((s for s in normalized if s['id']==candidates[0]['source_id']),{})
     if candidate.get('metadata_verified'):kind,message,advice,action='identity_conflict','PDF 身份信息与引用不完全一致','请核对作者、年份后手动指定或修正书目信息。','resolve_identity'
     else:kind,message,advice,action='uploaded_unmatched','PDF 已上传但尚未匹配','请确认该 PDF 的作者、标题及年份后重新匹配。','review_uploaded'
    else:kind,message,advice,action='missing_source','PDF 缺失','未找到与该作者和年份相关的候选文件；请上传对应来源 PDF。','upload_pdf'
    issues.append(dict(location_id=loc['id'],kind=kind,label=loc['id']+' · '+member['raw'],message=message,advice=advice,action=action,candidates=candidates))
  ready+=available
 return dict(issues=issues,locations=len(locations),ready_locations=ready,readable_files=sum(s.get('attachment_status')=='available' for s in normalized),model_calls=0)
