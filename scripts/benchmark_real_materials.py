"""Read actual PDFs in isolated temporary storage; never instantiate an API client."""
import argparse,json,resource,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.pdf_index import parse_pdf,fingerprint,VERSION
from app.evidence import EvidenceService
from app.tasks import TaskStore
from app.sources import AssetStore

def peak_mb():return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)

def measure(task_path,mode):
 from app import pdf_index
 pdf_index.MAX_CHARACTERS=200000 if mode=='legacy' else 300000
 task=json.loads(Path(task_path).read_text());started=time.monotonic();initial=peak_mb()
 with tempfile.TemporaryDirectory(prefix='backedup-real-memory-') as folder:
  root=Path(folder);tasks=TaskStore(root/'tasks');assets=AssetStore(root/'assets');evidence=EvidenceService(tasks,assets,root/'evidence');tasks.save(task)
  sizes=[];indexes={};stopped=False
  for n,source in enumerate(task['sources']):
   index=parse_pdf(Path(source['path']),source['id']);characters=sum(len(p['chars']) for p in index['pages'])
   sizes.append(dict(pages=index['total_pages'],characters=characters,text_characters=sum(len(p['text']) for p in index['pages'])))
   if mode=='legacy':
    indexes[source['id']]=index
    if sum(s['characters'] for s in sizes)>400000:stopped=True;break
   else:
    cached=evidence.cache/(index['sha256']+'-'+VERSION+'.json');cached.write_text(json.dumps(index,ensure_ascii=False));del index
   print(f'{mode}: local PDF {n+1}/{len(task["sources"])}',file=sys.stderr,flush=True)
  verified=0;selected_sources=0
  if mode!='legacy':
   package=evidence.prepare(task['id']);selected_sources=len(package['sources'])
   # Walk each actual citation's sources and validate a real block against coordinates.
   for loc in task['locations']:
    for sid in dict.fromkeys(m['match']['source_id'] for m in loc['members'] if m['match']['status']=='matched'):
     index=package['sources'][sid]
     block=next((b for p in index['pages'] for b in p['blocks'] if b['text'].strip()),None)
     if block:
      evidence.verify_evidence(package,sid,dict(source_id=sid,pdf_sha256=index['sha256'],block_id=block['id'],quote=block['text'],start=0,end=len(block['text']),role='支持'));verified+=1
     del index
    package['sources'].clear_cache()
  return dict(mode=mode,initial_rss_mb=round(initial,2),peak_rss_mb=round(peak_mb(),2),seconds=round(time.monotonic()-started,2),pdfs=len(sizes),pages=sum(s['pages'] for s in sizes),characters=sum(s['characters'] for s in sizes),max_pdf_characters=max(s['characters'] for s in sizes),max_pdf_pages=max(s['pages'] for s in sizes),stopped_at_old_limit=stopped,prepared_sources=selected_sources,coordinate_checks=verified,disk_mb=round(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())/1024**2,2),per_pdf=sizes)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--task',required=True);parser.add_argument('--worker',choices=['legacy','lazy']);parser.add_argument('--output',default=str(ROOT/'docs/benchmark-real-42.json'));args=parser.parse_args()
 if args.worker:print(json.dumps(measure(args.task,args.worker)))
 else:
  results=[]
  for mode in ['legacy','lazy']:
   output=subprocess.check_output([sys.executable,__file__,'--task',args.task,'--worker',mode],text=True);results.append(json.loads(output))
  record=dict(kind='actual PDFs; local parsing and coordinate checks only; no semantic/model validation',results=results)
  Path(args.output).write_text(json.dumps(record,ensure_ascii=False,indent=2));print(json.dumps(record,ensure_ascii=False))
