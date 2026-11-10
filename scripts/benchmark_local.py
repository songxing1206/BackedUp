"""Synthetic backend benchmarks in isolated processes, no real model calls."""
import argparse,base64,gc,json,os,resource,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from pdf_fixture import make_pdf
from app.sources import AssetStore
from app.tasks import TaskStore
from app.evidence import EvidenceService
from app.automatic_review import ReviewQueue

CASES={'small':(1,2,1),'batch':(10,5,1),'long_pdf':(1,50,1),'many_citations':(1,5,30),'repeat':(1,5,30)}
NAMES=['Smith','Jones','Brown','Taylor','Clark','Wilson','Miller','Davis','Garcia','Moore']

def rss():return int(subprocess.check_output(['/bin/ps','-o','rss=','-p',str(os.getpid())]).strip())/1024

def worker(case,fixture):
 tracing=bool(os.environ.get('BACKEDUP_TRACE_MEMORY'))
 if tracing:
  import tracemalloc
  tracemalloc.start()
 with tempfile.TemporaryDirectory(prefix='backed-up-benchmark-') as d:
  root=Path(d);assets=AssetStore(root/'assets');tasks=TaskStore(root/'tasks');evidence=EvidenceService(tasks,assets,root/'evidence');sources=[]
  for path in sorted(Path(fixture).glob('*.pdf')):
   source=assets.upload(path.name,base64.b64encode(path.read_bytes()).decode());source=assets.confirm(source['id'],{'title':'Fixture study','authors':path.stem,'year':'2023'});sources.append(source)
  calls=[]
  class Fake:
   def call(_,prompt,cancel):
    data=json.loads(prompt.split('\nDATA\n')[1]);calls.append(data['phase'])
    if data['phase']=='merge':return data['candidates'][0]
    source=data['sources'][0];block=source['blocks'][1]
    return {'claims':[{'id':'P1','text':data['sentence'],'source_judgments':[{'source_id':source['id'],'status':'支持','reason':'fixture only','evidence':[{'source_id':source['id'],'pdf_sha256':source['sha256'],'block_id':block['id'],'quote':block['text'],'role':'支持'}]}]}],'combined':{'status':'支持','reason':'fixture only'}}
  queue=ReviewQueue(tasks,assets,evidence,root/'checks',lambda:{'provider':'fake','model':'fixture'},lambda _:Fake());samples=[];started=time.monotonic();baseline=rss();iterations=CASES[case][2]
  try:
   for number in range(iterations if case=='repeat' else 1):
    paragraphs=30 if case=='many_citations' else len(sources)
    text='\n\n'.join(f'Finding {i+1} reports recall ({sources[i%len(sources)]["authors"]}, 2023).' for i in range(paragraphs))
    job=queue.start(text,[s['id'] for s in sources]);queue.wait(job['id'],120)
    result=queue.get(job['id'])
    if result['status']!='completed':raise RuntimeError(str(result['errors']))
    gc.collect();samples.append(round(rss(),2))
   deadline=time.monotonic()+2
   while queue.events and time.monotonic()<deadline:time.sleep(.01)
   assert not queue.events and not queue.snapshots
   if tracing:
    print(tracemalloc.get_traced_memory(),file=sys.stderr)
    for entry in tracemalloc.take_snapshot().statistics('lineno')[:10]:print(entry,file=sys.stderr)
  finally:queue.close()
  peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024*1024 if sys.platform=='darwin' else 1024)
  return {'case':case,'pdf_count':len(sources),'pages_per_pdf':CASES[case][1],'tasks':iterations if case=='repeat' else 1,'citations_per_task':30 if case=='many_citations' else len(sources),'seconds':round(time.monotonic()-started,3),'peak_process_mb':round(peak,2),'baseline_rss_mb':round(baseline,2),'rss_after_tasks_mb':samples,'disk_mb':round(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())/1048576,2),'mock_calls':len(calls),'events_remaining':len(queue.events),'snapshots_remaining':len(queue.snapshots)}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--worker');parser.add_argument('--fixture');args=parser.parse_args()
 if args.worker:print(json.dumps(worker(args.worker,args.fixture)));return
 results=[]
 with tempfile.TemporaryDirectory(prefix='backed-up-fixtures-') as d:
  for case,(count,pages,_) in CASES.items():
   directory=Path(d)/case;directory.mkdir()
   for name in NAMES[:count]:
    rows=[(40,790-i*32,('Recall evidence '+name+' improves learning in adults. ')*2) for i in range(20)]
    make_pdf(directory/(name+'.pdf'),pages=[rows for _ in range(pages)])
   response=subprocess.run([sys.executable,__file__,'--worker',case,'--fixture',str(directory)],capture_output=True,text=True,timeout=180)
   if response.returncode:raise RuntimeError(response.stderr[-3000:])
   if os.environ.get('BACKEDUP_TRACE_MEMORY'):print(response.stderr,file=sys.stderr)
   results.append(json.loads(response.stdout.strip().splitlines()[-1]));print(json.dumps(results[-1]),flush=True)
 output=ROOT/'docs/benchmark-local.json';output.write_text(json.dumps({'kind':'synthetic backend only; excludes browser and real inference','platform':sys.platform,'results':results},indent=2))

if __name__=='__main__':main()
