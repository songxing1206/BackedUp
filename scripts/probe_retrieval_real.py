"""Offline candidate probe against stored exact evidence; no model or paid calls."""
import json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.evidence_storage import load_package
from app.retrieval import Retriever,pack_sources

def probe(task_path,evidence_path,output):
 task=json.loads(Path(task_path).read_text());package=load_package(Path(evidence_path));start=time.monotonic();results=[]
 reviews={r['location_id']:r for r in task.get('evidence_review',{}).get('locations',[])}
 with tempfile.TemporaryDirectory(prefix='retrieval-probe-') as folder:
  retriever=Retriever(folder);paths={};info={}
  for sid in package['sources']:
   index=package['sources'][sid];paths[sid]=retriever.build(index);info[sid]={'id':sid,'sha256':index['sha256'],'partial_scope':True}
   del index
  package['sources'].clear_cache()
  for loc in task['locations']:
   sids=list(dict.fromkeys(m['match']['source_id'] for m in loc['members'] if m['match']['status']=='matched'));seen=set();sizes=[]
   for round_number in range(2):
    sources=[{**info[sid],'blocks':[b for b in retriever.select(paths[sid],loc.get('claim_text',loc['sentence']),round_number) if b['id'] not in seen]} for sid in sids]
    selected=pack_sources(sources,12000);seen.update(b['id'] for s in selected for b in s['blocks']);sizes.append(len(json.dumps(selected,ensure_ascii=False).encode()))
   reference={e['block_id'] for c in reviews.get(loc['id'],{}).get('claims',[]) for j in c['source_judgments'] for e in j.get('evidence',[]) if e.get('validation') in {'verified','text_verified'} and e.get('block_id')}
   results.append({'location':loc['id'],'sources':len(sids),'candidate_bytes':sizes,'reference_blocks':len(reference),'retrieved_reference_blocks':len(reference&seen)})
  record={'kind':'offline lexical retrieval probe; stored previous evidence is NOT semantic gold','seconds':round(time.monotonic()-start,2),'locations':results,'index_mb':round(sum(p.stat().st_size for p in Path(folder).rglob('*') if p.is_file())/1024**2,2),'reference_block_hits':sum(r['retrieved_reference_blocks'] for r in results),'reference_blocks':sum(r['reference_blocks'] for r in results),'candidate_bytes_total':sum(sum(r['candidate_bytes']) for r in results)}
 Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in record.items() if k!='locations'}))
if __name__=='__main__':probe(*sys.argv[1:])
