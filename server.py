"""Local citation review workbench; user-configured model providers only."""
import json,secrets,re,argparse,signal,sys
from app.runtime import health
from app.storage import DATA_VERSION,data_dir,cache_dir,initialize,history_namespaces,namespace_dir
from app.report_archive import report_bundle,saved_bundle
from app.model_settings import SettingsStore
from app.model_provider import ModelClient
from app.automatic_review import ReviewQueue
from app.pdf_index import render_page,fingerprint
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from app.sources import AssetStore,collections,import_collection,MAX_UPLOAD
from app.tasks import TaskStore
from app.evidence import EvidenceService
ROOT=Path(__file__).resolve().parent
assets=tasks=evidence=model_settings=None
TOKEN=secrets.token_urlsafe(32)
checks=experiments=None # Initialize workers only when serving, never during test/module import.

def configure():
 global assets,tasks,evidence,model_settings
 directory=initialize(ROOT/'output')
 cache=cache_dir();cache.mkdir(parents=True,exist_ok=True,mode=0o700)
 import os
 if os.name!='nt':cache.chmod(0o700)
 assets=AssetStore(directory/'assets');tasks=TaskStore(directory/'tasks')
 evidence=EvidenceService(tasks,assets,directory/'evidence',cache_dir()/'pdf')
 model_settings=SettingsStore(directory/'settings/model.json')

def public(value):
 if isinstance(value,dict):return {k:public(v) for k,v in value.items() if k!='path'}
 if isinstance(value,list):return [public(v) for v in value]
 return value

def task_view(record):
 """Attach the saved run failure summary so historical gray results explain themselves."""
 jid=record.get('last_check_id')
 if not jid or checks is None:return record
 try:job=checks.get(jid)
 except (ValueError,FileNotFoundError):return record
 record['check_errors']=list(job.get('errors',[]))
 record['check_status']=dict(status=job.get('status'),stage=job.get('stage'),completed=job.get('completed'),total=job.get('total'))
 return record

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,body,kind='application/json',status=200,filename=None):
  if kind=='application/json':body=json.dumps(public(body),ensure_ascii=False).encode()
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
  if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
  self.end_headers();self.wfile.write(body)
 def allowed(self):
  host=self.headers.get('Host')
  if host not in {f'localhost:{self.server.server_port}',f'127.0.0.1:{self.server.server_port}'}:return False
  origin='http://'+host
  return self.headers.get('Origin',origin)==origin
 def send_file(self,file,filename):
  file.seek(0,2);length=file.tell();file.seek(0)
  self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Length',str(length));self.send_header('Content-Disposition',f'attachment; filename="{filename}"');self.send_header('Cache-Control','no-store');self.end_headers()
  import shutil
  shutil.copyfileobj(file,self.wfile,length=65536)
 def do_GET(self):
  try:
   if not self.allowed():return self.send({'error':'仅允许本地页面访问'},status=403)
   if self.path=='/api/health':return self.send(health(data_dir()))
   if self.path=='/api/licenses':
    files=[ROOT/'THIRD_PARTY_NOTICES.md',ROOT/'app/vendor/citefact/LICENSE']+sorted(p for p in (ROOT/'licenses').rglob('*') if p.is_file())
    return self.send({'documents':[{'name':('CiteFact · MIT License' if p==files[1] else str(p.relative_to(ROOT))),'text':p.read_text(encoding='utf-8',errors='replace')} for p in files]})
   if self.path=='/api/config':return self.send({'token':TOKEN,'data_version':DATA_VERSION,'version':health(data_dir())['version']})
   if self.path=='/api/model/settings':return self.send(model_settings.public())
   if self.path=='/api/tasks':return self.send(tasks.history())
   if self.path=='/api/architecture':
    from app.experiments import ARCHITECTURE,BENCHMARK,LEGACY_COMPARISON,CONTEXT_CONFIGS
    return self.send({'pipeline':ARCHITECTURE,'benchmark':BENCHMARK,'legacy_comparison':[{'dimension':row[0],'legacy':row[1],'agent':row[2],'change':row[3]} for row in LEGACY_COMPARISON],'context_configs':CONTEXT_CONFIGS})
   if self.path=='/api/experiments':return self.send(experiments.list())
   if self.path=='/api/experiments/tasks':return self.send([dict(id=row['id'],title=row['title'],created_at=row['created_at'],locations=len(row.get('locations',[])),is_checking=row.get('is_checking',False)) for row in tasks.history()])
   m=re.fullmatch(r'/api/experiments/([a-f0-9]{32})/trace',self.path)
   if m:return self.send(experiments.trace(m[1]))
   m=re.fullmatch(r'/api/experiments/([a-f0-9]{32})/export\.(json|html)',self.path)
   if m:
    if m[2]=='json':return self.send(experiments.export_json(m[1]),'application/json; charset=utf-8',filename='backed-up-experiment.json')
    return self.send(experiments.export_html(m[1]),'text/html; charset=utf-8',filename='backed-up-experiment.html')
   m=re.fullmatch(r'/api/experiments/([a-f0-9]{32})',self.path)
   if m:return self.send(experiments.get(m[1]))
   if self.path=='/api/history':
    rows=[]
    for name in history_namespaces():
     root=namespace_dir(name)
     if (root/'tasks').is_dir():
      for row in TaskStore(root/'tasks').history():rows.append({**row,'namespace':name,'current':root==data_dir()})
    return self.send(sorted(rows,key=lambda r:r['created_at'],reverse=True))
   m=re.fullmatch(r'/api/history/(data-v\d+)/([a-f0-9]{32})/report',self.path)
   if m:
    root=namespace_dir(m[1]);record=TaskStore(root/'tasks').get(m[2])
    with saved_bundle(record,root,cache_dir()/'archives') as bundle:
     import zipfile
     return self.send(zipfile.ZipFile(bundle).read('report.html'),'text/html; charset=utf-8')
   m=re.fullmatch(r'/api/history/(data-v\d+)/([a-f0-9]{32})/(sources/[a-f0-9]{32}\.pdf|evidence/[a-f0-9]{32}-\d+\.png)',self.path)
   if m:
    root=namespace_dir(m[1]);record=TaskStore(root/'tasks').get(m[2])
    with saved_bundle(record,root,cache_dir()/'archives') as bundle:
     import zipfile
     return self.send(zipfile.ZipFile(bundle).read(m[3]),'application/pdf' if m[3].endswith('.pdf') else 'image/png')
   m=re.fullmatch(r'/api/tasks/([a-f0-9]{32})/report-bundle',self.path)
   if m:
    with saved_bundle(tasks.get(m[1]),tasks.root.parent,cache_dir()/'archives') as bundle:return self.send_file(bundle,'backed-up-report.zip')
   m=re.fullmatch(r'/api/tasks/([a-f0-9]{32})/report-bundle/check',self.path)
   if m:
    with saved_bundle(tasks.get(m[1]),tasks.root.parent,cache_dir()/'archives'):return self.send({'ok':True})
   m=re.fullmatch(r'/api/checks/([a-f0-9]{32})',self.path)
   if m:return self.send({k:v for k,v in checks.get(m[1]).items() if k!='text'})
   m=re.fullmatch(r'/api/tasks/([a-f0-9]{32})/sources/([a-f0-9]{32})/pages/(\d+)',self.path)
   if m:
    t=tasks.get(m[1]);source=next((s for s in t['sources'] if s['id']==m[2]),None)
    if not source or not source.get('path'):raise ValueError('来源不属于任务或 PDF 不可读取')
    package=evidence.load(t['id']);evidence.current(t,package)
    if m[2] not in package['sources']:raise ValueError('来源未解析')
    return self.send(render_page(source['path'],int(m[3]),1.5),'image/png')
   if self.path=='/api/zotero/collections':return self.send(collections())
   m=re.fullmatch(r'/api/tasks/([a-f0-9]{32})(/export)?',self.path)
   if m:
    record=tasks.get(m[1])
    return self.send(record if m[2] else task_view(record),filename='backed-up-report.json' if m[2] else None)
   m=re.fullmatch(r'/api/assets/([a-f0-9]{32})/pdf',self.path)
   if m:
    source=assets.get(m[1]);path=source.get('path')
    if not path or source['attachment_status']!='available':raise ValueError('没有可访问的PDF')
    return self.send(Path(path).read_bytes(),'application/pdf')
   m=re.fullmatch(r'/api/assets/([a-f0-9]{32})/document',self.path)
   if m:
    from app.document_schema import public_preview
    return self.send(public_preview(assets.document(m[1])))
   m=re.fullmatch(r'/api/tasks/([a-f0-9]{32})/evidence/(package|prompt)',self.path)
   if m:
    if m[2]=='package':return self.send(evidence.export_json(m[1]),filename='evidence-package.json')
    return self.send(evidence.export_markdown(m[1]).encode(),'text/markdown; charset=utf-8',filename='codex-evidence-prompt.md')
   m=re.fullmatch(r'/api/tasks/([a-f0-9]{32})/evidence/([a-f0-9]{32})/page',self.path)
   if m:return self.send(evidence.preview(m[1],m[2]),'image/png')
   file={'/':'index.html','/guide':'guide.html','/guide.html':'guide.html','/experiments':'experiments.html','/experiments.html':'experiments.html','/experiments.js':'experiments.js','/app.js':'app.js','/task-quality.js':'task-quality.js','/style.css':'style.css','/workspace-classic.css':'workspace-classic.css','/evidence.js':'evidence.js','/model-settings.js':'model-settings.js','/automatic-review.js':'automatic-review.js','/pdf-reader.js':'pdf-reader.js','/overview.js':'overview.js','/local-data.js':'local-data.js'}.get(self.path)
   if self.path=='/storage.js':file='storage.js'
   if self.path=='/uploads.js':file='uploads.js'
   if not file:return self.send({'error':'页面不存在'},status=404)
   return self.send((ROOT/'web'/file).read_bytes(),'text/css; charset=utf-8' if file.endswith('.css') else 'text/html; charset=utf-8' if file.endswith('.html') else 'text/javascript; charset=utf-8')
  except (ValueError,OSError) as e:self.send({'error':str(e)},status=400)
 def do_POST(self):
  try:
   if not self.allowed() or self.headers.get('X-BackedUp-Token')!=TOKEN:return self.send({'error':'请求未授权，请刷新本地页面'},status=403)
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=MAX_UPLOAD:raise ValueError('请求为空或超过40MB')
   data=json.loads(self.rfile.read(length))
   m=re.fullmatch(r'/api/history/(data-v\d+)/([a-f0-9]{32})/delete',self.path)
   if m:
    from app.history_delete import delete_record
    root=namespace_dir(m[1])
    return self.send(delete_record(root,m[2],checks if root==data_dir() else None))
   if self.path=='/api/data/open':
    from app.platform_support import open_directory
    open_directory(data_dir());return self.send({'ok':True})
   if self.path=='/api/shutdown':
    import threading
    threading.Thread(target=self.server.shutdown,daemon=True).start();return self.send({'ok':True})
   if self.path=='/api/model/settings':return self.send(model_settings.save(data))
   if self.path=='/api/model/test':
    snapshot=model_settings.snapshot()
    if any(data.get(k)!=snapshot.get(k) for k in ['provider','model','base_url']):raise ValueError('模型配置已变化，请重新打开模型连接后测试；本次未调用 API')
    return self.send(ModelClient(snapshot).test())
   if self.path=='/api/checks/preflight':
    from app.source_preflight import source_preflight
    return self.send(source_preflight(data['text'],[assets.get(sid) for sid in data['source_ids']],data.get('location_limit')))
   if self.path=='/api/checks':
    options={k:data[k] for k in ['location_ids','review_mode','context_mode','location_limit','max_requests','token_budget','retry_failed_requests','execution_mode'] if k in data}
    return self.send({k:v for k,v in checks.start(data['text'],data['source_ids'],data.get('task_id'),**options).items() if k!='text'})
   if self.path=='/api/experiments':return self.send(experiments.create(data))
   if self.path=='/api/experiments/import':return self.send(experiments.import_document(data))
   m=re.fullmatch(r'/api/experiments/([a-f0-9]{32})/gold',self.path)
   if m:return self.send(experiments.attach_gold(m[1],data.get('gold')))
   m=re.fullmatch(r'/api/checks/([a-f0-9]{32})/(cancel|retry)',self.path)
   if m:return self.send({k:v for k,v in (checks.cancel(m[1]) if m[2]=='cancel' else checks.retry(m[1],**{k:data[k] for k in ['max_requests','token_budget'] if k in data})).items() if k!='text'})
   m=re.fullmatch(r'/api/tasks/([a-f0-9]{32})/evidence/(prepare|import)',self.path)
   if m:
    if m[2]=='prepare':return self.send(evidence.export_json(m[1],evidence.prepare(m[1])))
    return self.send(evidence.import_result(m[1],data))
   if self.path=='/api/assets':return self.send(assets.upload(data['name'],data['data']))
   if self.path=='/api/bibliography':return self.send(assets.bibliography(data['text'],data.get('asset_ids',[])))
   if self.path=='/api/zotero/import':return self.send(import_collection(data['key'],assets))
   if self.path=='/api/tasks':return self.send(tasks.create(data['text'],[assets.get(s) for s in data['source_ids']]))
   m=re.fullmatch(r'/api/assets/([a-f0-9]{32})/(confirm|bind)',self.path)
   if m:
    if m[2]=='confirm':return self.send(assets.confirm(m[1],data))
    source=assets.get(m[1]);attachment=assets.get(data['attachment_id'])
    if attachment['attachment_status']!='available':raise ValueError('选择的PDF不可读取')
    source.update(path=attachment['path'],filename=attachment['filename'],attachment_status='available');assets.save(source);return self.send(source)
   m=re.fullmatch(r'/api/tasks/([a-f0-9]{32})/source-identity',self.path)
   if m:
    current=tasks.get(m[1]);source=next((s for s in current['sources'] if s['id']==data['source_id']),None)
    if not source:raise ValueError('来源不属于当前任务')
    author=str(data.get('authors','')).strip();year=str(data.get('year','')).strip()
    if not author or not re.fullmatch(r'(?:19|20)\d{2}[a-z]?',year,re.I):raise ValueError('请填写作者和有效年份，例如 2022')
    from app.matching import surname,year_parts
    candidates=[(l,m) for l in current['locations'] for m in l['members'] if surname(m['author'])==surname(author) and year_parts(m['year'])==year_parts(year)]
    if not candidates:raise ValueError('未找到作者、年份相符的正文引用，请核对后重试')
    source.update(authors=author,year=year,metadata_verified=True,metadata_source='user_confirmed')
    assets.save(source)
    updated=tasks.update_source(current['id'],source['id'],source)
    selected=next(s for s in updated['sources'] if s['id']==source['id']);selected.update(metadata_verified=True,metadata_source='user_confirmed')
    from app.matching import match_member
    for l in updated['locations']:
     for member in l['members']:
      if not member['match'].get('assigned_by_user'):member['match']=match_member(member,updated['sources'])
    targets=[l['id'] for l in updated['locations'] if any(member['match'].get('source_id')==source['id'] and member['match']['status']=='matched' for member in l['members'])]
    from app.evidence import invalidate_review
    invalidate_review(updated,set(targets));tasks.summarize(updated);tasks.save(updated)
    return self.send({'task':updated,'location_ids':targets,'matched':bool(targets)})
   m=re.fullmatch(r'/api/tasks/([a-f0-9]{32})/assign',self.path)
   if m:return self.send(tasks.assign(m[1],data['member_id'],data['source_id']))
   return self.send({'error':'接口不存在'},status=404)
  except (ValueError,KeyError,TypeError,OSError) as e:self.send({'error':str(e)},status=400)

def serve(port=8787):
 global checks,experiments
 ThreadingHTTPServer.allow_reuse_address=sys.platform!='win32'
 server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
 configure()
 checks=ReviewQueue(tasks,assets,evidence,data_dir()/'checks',model_settings.snapshot,cache_root=cache_dir()/'reviews')
 from app.experiments import ExperimentStore
 experiments=ExperimentStore(data_dir()/'experiments',tasks,assets,checks,model_settings)
 def stop(*_):raise KeyboardInterrupt
 signal.signal(signal.SIGTERM,stop)
 print(f'Backed Up: http://localhost:{server.server_port}',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:checks.close();server.server_close()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8787);args=parser.parse_args();serve(args.port)
