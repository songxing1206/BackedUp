"""Unified, deterministic PDF document schema built on the raw PDFium index.

The raw page/character index remains authoritative for quotations and highlighting.
This module only adds reading order, paragraphs, sections, metadata candidates and a
Markdown projection; every structured paragraph keeps links to its raw PDF blocks.
"""
from pathlib import Path
import re,statistics
from pypdf import PdfReader

SCHEMA_VERSION='document-1'
PARSER_VERSION='pdfium-structured-1'
HEADING=re.compile(r'^(?:\d+(?:\.\d+)*\.?\s+)?(?:abstract|introduction|background|methods?|materials? and methods?|results?|discussion|conclusions?|limitations?|acknowledg(?:e)?ments?|references|bibliography|摘要|引言|背景|方法|结果|讨论|结论|参考文献)\s*$',re.I)
DOI=re.compile(r'10\.\d{4,9}/[^\s<>"\]]+',re.I)
YEAR=re.compile(r'\b(?:19|20)\d{2}\b')

def _clean(value):return re.sub(r'\s+',' ',str(value or '')).strip()

def _pdf_hints(path):
 try:
  with Path(path).open('rb') as stream:
   metadata=PdfReader(stream).metadata or {}
  return {'title':_clean(metadata.get('/Title')),'authors':_clean(metadata.get('/Author'))}
 except Exception:return {'title':'','authors':''}

def _box(block):
 box=block.get('box')
 return box if isinstance(box,list) and len(box)==4 else [0,0,0,0]

def _page_order(page):
 """Return raw line blocks in stable scholarly reading order.

 A page is treated as two-column only when both sides contain enough narrow lines.
 Full-width headings before/between columns are retained as anchors.
 """
 blocks=[b for b in page.get('blocks',[]) if _clean(b.get('text'))]
 width=float(page.get('width') or 1);middle=width/2
 narrow=[b for b in blocks if _box(b)[2] and _box(b)[2]<width*.62]
 left=[b for b in narrow if _box(b)[0]+_box(b)[2]/2<middle*.94]
 right=[b for b in narrow if _box(b)[0]+_box(b)[2]/2>middle*1.06]
 substantial_left=[b for b in left if _box(b)[2]>width*.15];substantial_right=[b for b in right if _box(b)[2]>width*.15]
 two_columns=len(substantial_left)>=3 and len(substantial_right)>=3
 if not two_columns:return sorted(blocks,key=lambda b:(_box(b)[1],_box(b)[0],b.get('char_start',0))),False
 # Do not mistake a narrow publisher/address sidebar for the second article column.
 column_top=max(min(_box(b)[1] for b in substantial_left),min(_box(b)[1] for b in substantial_right))
 before=sorted([b for b in blocks if _box(b)[1]<column_top],key=lambda b:(_box(b)[1],_box(b)[0]))
 remaining=[b for b in blocks if b not in before];left=[b for b in remaining if _box(b)[0]+_box(b)[2]/2<middle];right=[b for b in remaining if b not in left]
 ordered=before+sorted(left,key=lambda b:(_box(b)[1],_box(b)[0]))+sorted(right,key=lambda b:(_box(b)[1],_box(b)[0]))
 return list(dict.fromkeys(b['id'] for b in ordered)),True

def _ordered_blocks(page):
 ordered,two=_page_order(page)
 if ordered and isinstance(ordered[0],str):
  mapping={b['id']:b for b in page.get('blocks',[])};ordered=[mapping[i] for i in ordered if i in mapping]
 return ordered,two

def _join_lines(lines):
 raw='\n'.join(_clean(b.get('text')) for b in lines).strip()
 normalized=re.sub(r'(?<=\w)-\s*\n\s*(?=\w)','',raw)
 normalized=re.sub(r'\s*\n\s*',' ',normalized)
 return raw,_clean(normalized)

def _paragraph_groups(ordered):
 if not ordered:return []
 heights=[_box(b)[3] for b in ordered if _box(b)[3]>0]
 median=statistics.median(heights) if heights else 10
 groups=[];current=[]
 for block in ordered:
  text=_clean(block.get('text'))
  if not text:continue
  if not current:current=[block];continue
  previous=current[-1];gap=_box(block)[1]-(_box(previous)[1]+_box(previous)[3])
  same_column=abs(_box(block)[0]-_box(previous)[0])<max(35,(block.get('page_width') or 0)*.08)
  current_size=sum(len(_clean(item.get('text'))) for item in current)
  new=HEADING.match(text) or HEADING.match(_clean(previous.get('text'))) or gap>median*1.45 or not same_column or len(current)>=8 or current_size+len(text)>1200
  if new:groups.append(current);current=[block]
  else:current.append(block)
 if current:groups.append(current)
 return groups

def _metadata(index,hints):
 first=index.get('pages',[{}])[0] if index.get('pages') else {}
 ordered,_=_ordered_blocks(first);top=[b for b in ordered if _box(b)[1]<(first.get('height') or 800)*.55]
 candidates=[]
 if top:
  heights=[_box(b)[3] for b in top if 8<=_box(b)[3]<=80]
  high=max(heights or [0])*.78
  title_lines=[b for b in top if _box(b)[3]>=high and 5<=len(_clean(b['text']))<=240][:3]
  if title_lines:candidates.append(_clean(' '.join(b['text'] for b in title_lines)))
 title=hints.get('title') or (candidates[0] if candidates else '')
 # Candidate author lines occur after the detected title and before Abstract.
 author_candidates=[]
 for b in top[:14]:
  text=_clean(b['text'])
  if not text or text in candidates or HEADING.match(text) or DOI.search(text):continue
  if re.search(r'@|university|institute|department|journal|copyright|https?://',text,re.I):continue
  if 2<=len(text)<=260 and re.search(r'[A-Za-z\u4e00-\u9fff]',text):author_candidates.append(text)
 # Locate the title in page geometry, then collect the compact byline immediately
 # below it. This avoids treating journal headers or title continuations as authors.
 title_norm=re.sub(r'\W','',title).casefold();title_end=None;acc=''
 for block in top:
  part=re.sub(r'\W','',_clean(block['text'])).casefold()
  if not acc and part and (part in title_norm or title_norm in part):acc=part;title_end=_box(block)[1]+_box(block)[3]
  elif acc and len(acc)<len(title_norm) and part in title_norm:
   acc+=part;title_end=_box(block)[1]+_box(block)[3]
  if title_norm and (title_norm in acc or acc in title_norm and len(acc)>=len(title_norm)*.85):break
 byline_blocks=[]
 if title_end is not None:
  for block in top:
   y=_box(block)[1];text=_clean(block['text'])
   if y<=title_end or y>title_end+30:continue
   if re.search(r'@|university|institute|department|journal|copyright|article info|abstract|doi|received|accepted|lancet|\bvol\b|\d{4}\s*;',text,re.I):continue
   if len(text)<=140 and not re.search(r'[.!?]$',text):byline_blocks.append(block)
 if byline_blocks:
  byline_blocks.sort(key=lambda b:(int(_box(b)[1]/5),_box(b)[0]));likely_byline=_clean(' '.join(b['text'] for b in byline_blocks))
  likely_byline=re.sub(r'\s+,',',',likely_byline);likely_byline=re.sub(r',\s*,+',', ',likely_byline)
  likely_byline=re.sub(r'[⁎*†‡]+','',likely_byline).strip(' ,')
 else:likely_byline=''
 # A byline detected directly below the title is generally more complete than the
 # single corresponding-author value often stored in PDF properties.
 if not likely_byline:likely_byline=next((x for x in author_candidates if (',' in x or re.search(r'\b(?:and|&)\b',x,re.I)) and not re.search(r'[.!?]$',x) and not re.search(r'journal|pharmacol|research',x,re.I)), '')
 authors=likely_byline or hints.get('authors') or (author_candidates[0] if author_candidates else '')
 first_text='\n'.join(_clean(b['text']) for b in ordered);doi_match=DOI.search(first_text);year_match=YEAR.search(first_text[:5000])
 fields={'title':title,'authors':[x.strip() for x in re.split(r'\s+(?:and|&)\s+|\s*;\s*',authors) if x.strip()] if authors else [],'year':year_match.group() if year_match else '','doi':doi_match.group().rstrip('.,;)').casefold() if doi_match else ''}
 sources={'title':'pdf_metadata' if hints.get('title') else 'first_page_layout' if fields['title'] else 'missing','authors':'first_page_layout' if likely_byline else 'pdf_metadata' if hints.get('authors') else 'first_page_layout' if fields['authors'] else 'missing'}
 sources.update(year='first_page_text' if fields['year'] else 'missing',doi='first_page_text' if fields['doi'] else 'missing')
 status='complete' if fields['title'] and fields['authors'] and fields['year'] else 'partial'
 return {**fields,'status':status,'sources':sources,'candidates':{'titles':candidates[:3],'authors':author_candidates[:5]}}

def to_markdown(document):
 metadata=document['metadata'];lines=[]
 if metadata['title']:lines.append('# '+metadata['title'])
 if metadata['authors']:lines.extend(['',', '.join(metadata['authors'])])
 detail=' · '.join(x for x in [metadata['year'],metadata['doi']] if x)
 if detail:lines.extend(['',detail])
 current=None
 for paragraph in document['paragraphs']:
  if paragraph['role']=='heading':
   lines.extend(['','## '+paragraph['normalized_text']]);current=paragraph['section_id'];continue
  lines.extend(['',paragraph['normalized_text']])
 return '\n'.join(lines).strip()+'\n'

def build_document(path,index,filename=None):
 hints=_pdf_hints(path);paragraphs=[];pages=[];sections=[];section_id='sec-000';sections.append({'id':section_id,'title':'Front matter','level':1,'page_start':1,'paragraph_ids':[]})
 two_column_pages=[];unmapped=0
 for page in index.get('pages',[]):
  ordered,two=_ordered_blocks(page)
  if two:two_column_pages.append(page['physical_page'])
  paragraph_ids=[]
  for group in _paragraph_groups(ordered):
   raw,normal=_join_lines(group)
   role='heading' if len(group)==1 and bool(HEADING.match(normal)) else 'paragraph'
   pid=f"{index.get('sha256','')[:16]}-p{page['physical_page']}-para{len(paragraphs)+1}"
   if role=='heading':
    section_id=f'sec-{len(sections):03d}';sections.append({'id':section_id,'title':normal,'level':1,'page_start':page['physical_page'],'paragraph_ids':[]})
   refs=[]
   for block in group:
    box=block.get('box')
    if not box:unmapped+=1
    refs.append({'block_id':block['id'],'page_index':page['page_index'],'physical_page':page['physical_page'],'box':box})
   paragraph={'id':pid,'section_id':section_id,'page_index':page['page_index'],'physical_page':page['physical_page'],'role':role,'raw_text':raw,'normalized_text':normal,'block_ids':[b['id'] for b in group],'pdf_refs':refs}
   paragraphs.append(paragraph);paragraph_ids.append(pid);sections[-1]['paragraph_ids'].append(pid)
  pages.append({'page_index':page['page_index'],'physical_page':page['physical_page'],'width':page.get('width'),'height':page.get('height'),'state':page.get('state'),'raw_text':page.get('text',''),'normalized_text':'\n\n'.join(p['normalized_text'] for p in paragraphs if p['page_index']==page['page_index']),'reading_order_block_ids':[b['id'] for b in ordered],'paragraph_ids':paragraph_ids,'layout':'two_column' if two else 'single_column'})
 total=index.get('total_pages',0);read=index.get('read_pages',0);warnings=list(index.get('warnings',[]))
 if two_column_pages:warnings.append(f'检测到 {len(two_column_pages)} 个双栏页面，已按左栏到右栏重排阅读顺序。')
 if unmapped:warnings.append(f'{unmapped} 个原文行块没有可用坐标；文本保留但无法用于精确高亮。')
 status='failed' if not read else 'warning' if read<total or unmapped else 'good'
 document={'schema_version':SCHEMA_VERSION,'document_id':index.get('source_id'),'original_file':{'source_id':index.get('source_id'),'filename':filename or Path(path).name,'sha256':index.get('sha256')},'metadata':_metadata(index,hints),'pages':pages,'sections':[s for s in sections if s['paragraph_ids']],'paragraphs':paragraphs,'raw_text':'\n\f\n'.join(p.get('text','') for p in index.get('pages',[])),'normalized_text':'\n\n'.join(p['normalized_text'] for p in paragraphs),'quality':{'status':status,'read_pages':read,'total_pages':total,'two_column_pages':two_column_pages,'unmapped_blocks':unmapped,'warnings':warnings},'parser':{'name':'PDFium structured adapter','version':PARSER_VERSION,'coordinate_source':index.get('parser_version')}}
 document['markdown']=to_markdown(document);return document

def public_preview(document,markdown_limit=16000):
 metadata=document.get('metadata',{});quality=document.get('quality',{})
 return {'schema_version':document.get('schema_version'),'document_id':document.get('document_id'),'metadata':metadata,'sections':[{'id':s['id'],'title':s['title'],'page_start':s['page_start']} for s in document.get('sections',[])],'pages':len(document.get('pages',[])),'paragraphs':len(document.get('paragraphs',[])),'quality':quality,'parser':document.get('parser',{}),'first_page_text':next((p['normalized_text'] for p in document.get('pages',[]) if p['physical_page']==1),''),'markdown':document.get('markdown','')[:markdown_limit],'markdown_truncated':len(document.get('markdown',''))>markdown_limit}
