"""PDF/BibTeX ingestion and read-only localhost Zotero adapter."""
from .text_io import read_text_compat, write_text_utf8
import base64,hashlib,json,re,uuid,urllib.request,urllib.parse
from pathlib import Path
from pypdf import PdfReader
import bibtexparser
from .pdf_index import parse_pdf

MAX_PDF=15*1024*1024
MAX_UPLOAD=40*1024*1024
ZOTERO='http://127.0.0.1:23119'

def identifier():return uuid.uuid4().hex

def clean_doi(value):
 m=re.search(r'10\.\d{4,9}/[^\s<>"\]]+',value or '',re.I)
 return m.group().rstrip('.,;)').casefold() if m else ''

def pdf_source(path,name=None,index=None):
 source=dict(id=identifier(),filename=name or path.name,path=str(path),title='',authors='',year='',online_year='',publication_year='',year_basis='',doi='',metadata_verified=False,metadata_source='pdf_hints',attachment_status='available',warnings=[])
 try:
  with open(path,'rb') as stream:
   doc=PdfReader(stream)
   if doc.is_encrypted:raise ValueError('PDF需要密码，当前不能读取')
   if len(doc.pages)==0:raise ValueError('PDF没有页面')
   source['pages']=len(doc.pages)
   index=index or parse_pdf(path,source['id']);document=index.get('document',{});metadata=document.get('metadata',{});quality=document.get('quality',{})
   source['title']=metadata.get('title','');source['authors']='; '.join(metadata.get('authors',[]));source['doi']=metadata.get('doi','');source['year']=metadata.get('year','')
   source['preview']=next((p.get('normalized_text','') for p in document.get('pages',[]) if p.get('physical_page')==1),'')[:1800]
   source.update(document_schema=document.get('schema_version'),document_parser=document.get('parser',{}).get('version'),parse_quality=quality.get('status','failed'),parse_pages=quality.get('read_pages',0),detected_sections=len(document.get('sections',[])))
   if not source['preview'].strip():source['warnings'].append('首页无可提取文字；未执行OCR，身份需补充。')
   source['warnings'].extend(quality.get('warnings',[]));source['warnings'].append('统一文档识别结果仅为线索，请核对标题、作者、年份后确认。')
 except Exception as e:source['attachment_status']='unreadable';source['warnings'].append(str(e)[:200])
 return source

class AssetStore:
 def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.documents=self.root/'documents';self.documents.mkdir(exist_ok=True)
 def document_path(self,sid):
  if not re.fullmatch(r'[a-f0-9]{32}',sid):raise ValueError('无效来源ID')
  return self.documents/(sid+'.json')
 def document(self,sid):
  try:return json.loads(read_text_compat(self.document_path(sid)))
  except FileNotFoundError:
   source=self.get(sid)
   if not source.get('path') or not Path(source['path']).is_file():raise ValueError('PDF不可读取，无法生成统一文档') from None
   index=parse_pdf(source['path'],sid);document=index.get('document',{});write_text_utf8(self.document_path(sid),json.dumps(document,ensure_ascii=False));return document
 def meta_path(self,sid):
  if not re.fullmatch(r'[a-f0-9]{32}',sid):raise ValueError('无效来源ID')
  return self.root/(sid+'.json')
 def get(self,sid):
  try:
   source=json.loads(read_text_compat(self.meta_path(sid)))
   return self.reuse_identity(source)
  except FileNotFoundError:raise ValueError('来源不存在') from None
 def reuse_identity(self,source):
  if source.get('metadata_verified') or source.get('attachment_status')!='available':return source
  path=Path(source.get('path') or '')
  if not path.is_file():return source
  with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
  candidates=[]
  for metadata in self.root.glob('*.json'):
   try:other=json.loads(read_text_compat(metadata))
   except (ValueError,OSError):continue
   if other.get('sha256')!=sha or not other.get('metadata_verified') or not all(other.get(k) for k in ['title','authors','year']):continue
   other_path=Path(other.get('path') or '')
   if not other_path.is_file():continue
   with other_path.open('rb') as stream:
    if hashlib.file_digest(stream,'sha256').hexdigest()!=sha:continue
   candidates.append(other)
  signatures={tuple(str(c.get(k,'')).strip().casefold() for k in ['title','authors','year']) for c in candidates}
  if len(signatures)!=1:return source
  chosen=candidates[0]
  for k in ['title','authors','year','online_year','publication_year','year_basis','year_verification','doi','metadata_source','identity_quote','metadata_pdf_sha256']:
   if k in chosen:source[k]=chosen[k]
  source.update(metadata_verified=True,sha256=sha,metadata_reused_from=chosen['id'])
  source.pop('metadata_attempt',None);self.save(source);return source
 def save(self,source):
  path=self.meta_path(source['id']);temp=path.with_suffix('.tmp');write_text_utf8(temp, json.dumps(source,ensure_ascii=False));temp.replace(path)
 def upload(self,name,data):
  if not isinstance(name,str) or not name.lower().endswith('.pdf'):raise ValueError('来源仅接受PDF文件')
  try:blob=base64.b64decode(data,validate=True)
  except Exception:raise ValueError('上传文件编码无效') from None
  if len(blob)>MAX_PDF:raise ValueError('单个PDF上限15MB；未保存超限文件')
  if not blob.startswith(b'%PDF-'):raise ValueError('文件不是有效PDF')
  sha=hashlib.sha256(blob).hexdigest()
  for metadata in self.root.glob('*.json'):
   old=json.loads(read_text_compat(metadata))
   if old.get('sha256')==sha and old.get('metadata_source')!='demo' and old.get('path') and Path(old['path']).exists():return self.get(old['id'])
  sid=identifier();path=self.root/(sid+'.pdf');path.write_bytes(blob)
  index=parse_pdf(path,sid);source=pdf_source(path,Path(name).name,index);source['id']=sid;source['sha256']=hashlib.sha256(blob).hexdigest()
  write_text_utf8(self.document_path(sid),json.dumps(index.get('document',{}),ensure_ascii=False));self.save(source);return source
 def confirm(self,sid,fields):
  source=self.get(sid)
  for k in ['title','authors','year','online_year','publication_year','year_basis','doi']:source[k]=str(fields.get(k,source.get(k,''))).strip()[:2000]
  if not all(source.get(k) for k in ['title','authors','year']):raise ValueError('请填写标题、第一作者姓氏及年份')
  if not re.fullmatch(r'(?:19|20)\d{2}[a-z]?',source['year'],re.I):raise ValueError('年份格式应为2023或2023a')
  for key in ['online_year','publication_year']:
   if source.get(key) and not re.fullmatch(r'(?:19|20)\d{2}[a-z]?',source[key],re.I):raise ValueError('在线发表和正式出版年份格式应为2023或2023a')
  if source.get('year_basis'):source['year_verification']=dict(status='confirmed',applicable_year=source['year'],basis=source['year_basis'])
  else:source.pop('year_verification',None)
  source['metadata_verified']=True;source['metadata_source']='user_confirmed';self.save(source);return source
 def bibliography(self,text,asset_ids):
  if len(text)>1000000:raise ValueError('书目超过1MB')
  db=bibtexparser.loads(text);assets=[self.get(sid) for sid in asset_ids];result=[]
  if not db.entries:raise ValueError('未读取到BibTeX条目')
  for entry in db.entries:
   title=re.sub(r'[{}]','',entry.get('title',''));doi=clean_doi(entry.get('doi',''))
   matches=[s for s in assets if doi and s.get('doi')==doi]
   if not matches and title:
    norm=lambda x:re.sub(r'[^\w]','',x).casefold()
    matches=[s for s in assets if s.get('title') and norm(s['title'])==norm(title)]
   bound=matches[0] if len(matches)==1 else None
   online_match=re.search(r'\b(?:19|20)\d{2}\b',entry.get('date',''));online_year=online_match.group() if online_match and online_match.group()!=entry.get('year','') else ''
   source=dict(id=identifier(),bib_key=entry['ID'],title=title,authors=entry.get('author',''),year=entry.get('year',''),online_year=online_year,publication_year=entry.get('year',''),year_basis='',doi=doi,metadata_verified=bool(title and entry.get('author') and entry.get('year')),metadata_source='bibtex',attachment_status=bound['attachment_status'] if bound else 'missing',filename=bound['filename'] if bound else '',path=bound.get('path') if bound else None,warnings=[])
   if not bound:source['warnings'].append('书目已读取；未可靠绑定PDF，请手动绑定。')
   self.save(source);result.append(source)
  return result

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

LOCAL_OPENER=urllib.request.build_opener(NoRedirect)

def zotero_get(route):
 if not route.startswith('/api/'):raise ValueError('不允许访问其他服务')
 req=urllib.request.Request(ZOTERO+route,headers={'Zotero-API-Version':'3'})
 try:
  with LOCAL_OPENER.open(req,timeout=4) as r:return json.load(r)
 except Exception:raise ValueError('无法连接Zotero本地API。请启动Zotero，并启用允许其他应用访问。') from None

def paginated(route):
 result=[]
 for start in range(0,20000,100):
  batch=zotero_get(route+('&' if '?' in route else '?')+f'limit=100&start={start}')
  if not isinstance(batch,list):raise ValueError('Zotero返回的列表格式不正确')
  result.extend(batch)
  if len(batch)<100:return result
 raise ValueError('Zotero列表超过20,000项，请选择更小的分类；未截断导入。')

def collections():
 rows=paginated('/api/users/0/collections');bykey={x['key']:x['data'] for x in rows}
 def label(key,seen=None):
  seen=set() if seen is None else seen
  if key in seen:return bykey[key]['name']
  seen.add(key);d=bykey[key];parent=d.get('parentCollection')
  return (label(parent,seen)+' / ' if parent in bykey else '')+d['name']
 return [dict(key=x['key'],name=label(x['key'])) for x in rows]

def import_collection(key,assets):
 if not re.fullmatch(r'[A-Z0-9]{8}',key):raise ValueError('无效Zotero分类ID')
 result=[]
 for item in paginated(f'/api/users/0/collections/{key}/items/top'):
  d=item['data']
  if d.get('itemType') in ['attachment','note']:continue
  authors=' and '.join((c.get('lastName','')+', '+c.get('firstName','')).strip(', ') if c.get('lastName') else c.get('name','') for c in d.get('creators',[]) if c.get('creatorType')=='author')
  year=re.search(r'\b(?:19|20)\d{2}\b',d.get('date',''))
  source=dict(id=identifier(),title=d.get('title',''),authors=authors,year=year.group() if year else '',doi=clean_doi(d.get('DOI','')),zotero_key=item['key'],metadata_verified=bool(authors and year and d.get('title')),metadata_source='zotero',attachment_status='missing',filename='',path=None,warnings=[])
  try:children=paginated(f'/api/users/0/items/{item["key"]}/children')
  except ValueError:
   children=[];source["warnings"].append("附件读取失败，已保留文献元数据，继续处理其他来源。")
  for child in children:
   cd=child.get('data',{})
   if cd.get('contentType')!='application/pdf':continue
   href=child.get('links',{}).get('enclosure',{}).get('href','');local=cd.get('path','')
   if href.startswith('file://'):local=urllib.parse.unquote(urllib.parse.urlparse(href).path)
   if local.startswith('/') and Path(local).is_file():
    source.update(path=local,filename=Path(local).name,attachment_status='available');break
   # Zotero can serve attachments through its local file endpoint.
   try:
    req=urllib.request.Request(ZOTERO+f'/api/users/0/items/{child["key"]}/file')
    with LOCAL_OPENER.open(req,timeout=4) as response:
     if urllib.parse.urlparse(response.url).hostname not in ['127.0.0.1','localhost']:raise ValueError('附件重定向到外部服务，未读取')
     blob=response.read(MAX_PDF+1)
    if len(blob)>MAX_PDF:raise ValueError('附件超过15MB')
    if blob.startswith(b'%PDF-'):
     path=assets.root/(source['id']+'.pdf');path.write_bytes(blob);source.update(path=str(path),filename=cd.get('filename') or cd.get('title','附件.pdf'),attachment_status='available');break
   except Exception:continue
  if source['attachment_status']=='missing':source['warnings'].append('文献元数据已读取，未取得可访问本地PDF。')
  assets.save(source);result.append(source)
 return result
