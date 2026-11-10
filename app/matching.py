"""Conservative identity matching. Intentionally does not take a fuzzy winner."""
import re,unicodedata

def author_key(value):
 """Comparison key only; keep original spelling in stored metadata."""
 text=unicodedata.normalize('NFKD',value or '')
 return re.sub(r'[^\w]','',''.join(c for c in text if not unicodedata.combining(c))).casefold()

def first_author(authors):
 text=unicodedata.normalize('NFKC',authors or '').strip()
 text=re.split(r'\s+(?:and|&)\s+|;',text,flags=re.I)[0]
 return re.split(r'\bet\s+al\b',text,flags=re.I)[0].strip(' .')

def surname(authors):
 # Comma format explicitly declares the family name; other compound names stay intact.
 return author_key(first_author(authors).split(',')[0])

def possible_family(authors):
 """Unstructured full-name suffix is only a candidate, never an identity proof."""
 first=first_author(authors)
 words=first.split()
 if ',' in first or not 2<=len(words)<=4:return ''
 if any(author_key(w) in {'association','society','university','committee','group','organization','organisation','institute','consortium'} for w in words):return ''
 return author_key(words[-1])

def filename_identity(member,source):
 """Return a conservative local identity hint from a user-named PDF.

 The surname must be the leading filename field (not merely occur somewhere in
 a descriptive filename), and the cited year must be corroborated either by
 that filename or by the year extracted from the PDF.  This remains a
 provisional identity: it is useful for selecting one readable PDF without
 pretending that its bibliographic metadata has been fully verified.
 """
 if source.get('attachment_status')!='available':return None
 name=unicodedata.normalize('NFKC',str(source.get('filename','')))
 stem=re.sub(r'\.pdf\s*$','',name,flags=re.I).strip()
 cited,cited_suffix=year_parts(member.get('year'))
 author=surname(member.get('author'))
 first_year=re.search(r'(?<!\d)((?:19|20)\d{2})([a-z]?)(?!\d)',stem,re.I)
 if not author or not first_year:return None
 leading=author_key(stem[:first_year.start()].strip(' ,;._-–—()[]{}'))
 if leading!=author:return None
 file_year,file_suffix=first_year.groups();stored_year,stored_suffix=year_parts(source.get('year'))
 filename_year_ok=file_year==cited and (not cited_suffix or file_suffix.casefold()==cited_suffix.casefold())
 extracted_year_ok=stored_year==cited and (not cited_suffix or stored_suffix.casefold()==cited_suffix.casefold())
 if not filename_year_ok and not extracted_year_ok:return None
 basis='文件名作者与年份' if filename_year_ok else '文件名作者与 PDF 解析年份'
 return dict(basis=basis,cited_year=str(member.get('year','')),filename_year=file_year,source_year=str(source.get('year','')))

def year_parts(value):
 m=re.fullmatch(r'\s*(\d{4})([a-z]?)\s*',str(value or ''),re.I)
 return m.groups() if m else (str(value or '').casefold(),'')

def diagnose_citation_year(member,source):
 """Diagnose a year difference without treating string inequality as error."""
 cited=str(member.get('year','')).strip();stored=str(source.get('year','')).strip()
 if cited.casefold()==stored.casefold():return dict(status='consistent',cited_year=cited,source_year=stored,reason='引用年份与已确认来源一致')
 verification=source.get('year_verification') if isinstance(source.get('year_verification'),dict) else {}
 applicable=str(verification.get('applicable_year','')).strip()
 if verification.get('status')=='confirmed' and applicable and cited.casefold()!=applicable.casefold():
  return dict(status='confirmed_error',cited_year=cited,source_year=stored,applicable_year=applicable,basis=verification.get('basis','已核验书目记录'),reason=f'可靠书目依据确认适用年份为 {applicable}，当前引用为 {cited}')
 online=str(source.get('online_year','')).strip();publication=str(source.get('publication_year','')).strip()
 if online and publication and online!=publication and cited in {online,publication}:
  return dict(status='ambiguous',cited_year=cited,source_year=stored,online_year=online,publication_year=publication,reason='Online First 年份与正式出版年份不同；需按适用引用规范人工确认')
 if not source.get('metadata_verified') or source.get('metadata_source')=='pdf_hints':
  return dict(status='unconfirmed',cited_year=cited,source_year=stored,reason='PDF 自动识别年份尚未形成可靠书目依据')
 cy,cs=year_parts(cited);sy,ss=year_parts(stored)
 if cy==sy and cs!=ss:return dict(status='ambiguous',cited_year=cited,source_year=stored,reason='年份后缀不同，可能属于同年多篇文献的引用格式差异')
 return dict(status='mismatch',cited_year=cited,source_year=stored,reason=f'作者相符，但引用年份为 {cited}、已上传 PDF 年份为 {stored}；没有 Online First 或正式出版双年份依据，不能视为同一来源')

def match_member(member,sources):
 cy,cs=year_parts(member['year']);author=surname(member['author'])
 candidates=[];year_candidates=[]
 for source in sources:
  sy,ss=year_parts(source.get('year'))
  exact=surname(source.get('authors'))==author
  provisional=filename_identity(member,source)
  if not exact and possible_family(source.get('authors'))!=author and not provisional:continue
  diagnosis=diagnose_citation_year(member,source)
  if sy!=cy and not provisional:
   year_candidates.append(dict(source_id=source['id'],title=source.get('title',''),reason=diagnosis['reason'],year_diagnosis=diagnosis));continue
  if cs and ss and cs.lower()!=ss.lower() and not provisional:
   year_candidates.append(dict(source_id=source['id'],title=source.get('title',''),reason=diagnosis['reason'],year_diagnosis=diagnosis));continue
  if provisional:
   diagnosis=dict(status='provisional_consistent',cited_year=str(member.get('year','')),source_year=str(source.get('year','')),reason=provisional['basis']+'唯一对应可读 PDF；书目信息仍会在核查流程中确认')
  candidates.append(dict(source_id=source['id'],title=source.get('title','') or source.get('filename',''),reason=(provisional['basis']+'唯一对应' if provisional else '作者与年份相符' if exact else '全名末词与引用姓氏相符，需确认作者归属')+('；年份后缀尚不完整' if not provisional and cs.lower()!=ss.lower() else ''),year_diagnosis=diagnosis,identity_basis=('verified_filename' if source.get('metadata_verified') else 'filename_provisional') if provisional else 'metadata'))
 if not candidates and year_candidates:
  confirmed=[c for c in year_candidates if c['year_diagnosis']['status']=='confirmed_error']
  ambiguous=[c for c in year_candidates if c['year_diagnosis']['status']=='ambiguous']
  if confirmed or ambiguous:
   diagnosis=(confirmed or ambiguous)[0]['year_diagnosis']
   return dict(status='needs_assignment',source_id=None,reason=diagnosis['reason'],candidates=year_candidates,year_diagnosis=diagnosis)
  diagnosis=year_candidates[0]['year_diagnosis']
  return dict(status='unmatched',source_id=None,reason=diagnosis['reason'],candidates=year_candidates,year_diagnosis=diagnosis)
 if not candidates:return dict(status='unmatched',source_id=None,reason='未找到作者与年份相符的来源，需要二次指定。',candidates=[],year_diagnosis={'status':'unconfirmed','reason':'来源尚未确认，不能判断引用年份是否错误'})
 if len(candidates)>1:
  verified=[c for c in candidates if next(x for x in sources if x['id']==c['source_id']).get('metadata_verified')]
  if len(verified)==1:candidates=verified
  else:return dict(status='needs_assignment',source_id=None,reason='存在多个同作者同年份候选；未自动选择，其他引用已继续处理。',candidates=candidates,year_diagnosis={'status':'ambiguous','reason':'多个候选来源，年份依据尚不唯一'})
 source=next(x for x in sources if x['id']==candidates[0]['source_id'])
 sy,ss=year_parts(source.get('year'))
 filename_basis=candidates[0].get('identity_basis') in {'filename_provisional','verified_filename'}
 provisional=candidates[0].get('identity_basis')=='filename_provisional'
 if not filename_basis and (surname(source.get('authors'))!=author or cs.lower()!=ss.lower() or not source.get('metadata_verified')):
  return dict(status='needs_assignment',source_id=None,reason='身份信息尚不足以自动确认，请核对候选后指定。',candidates=candidates,year_diagnosis=candidates[0]['year_diagnosis'])
 available=source.get('attachment_status')=='available'
 reason=candidates[0]['reason']+'可读 PDF；采用临时匹配，核查时继续确认书目信息。' if provisional else '所提供来源中作者及年份唯一匹配；已确认来源元数据。'
 return dict(status='matched' if available else 'missing_attachment',source_id=source['id'],reason=reason if available else '文献身份已匹配，但没有可读取PDF附件。',candidates=candidates,year_diagnosis=candidates[0]['year_diagnosis'],identity_basis='filename_provisional' if provisional else 'verified_metadata')
