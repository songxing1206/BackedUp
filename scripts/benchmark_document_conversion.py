"""Offline old/new PDF conversion comparison; never calls a model service."""
import argparse,json,re,sys,time,tempfile,logging
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
logging.getLogger('pypdf').setLevel(logging.ERROR)
from app.pdf_index import parse_pdf,range_regions
from app.retrieval import Retriever
from app.sources import clean_doi

def legacy_metadata(path):
 with Path(path).open('rb') as stream:
  reader=PdfReader(stream);meta=reader.metadata or {};text=reader.pages[0].extract_text() or ''
 years=re.findall(r'\b(?:19|20)\d{2}\b',text[:2500])
 return {'title':str(meta.get('/Title') or '').strip(),'authors':str(meta.get('/Author') or '').strip(),'year':years[0] if years else '','doi':clean_doi(text),'first_page_text':text}

def retrieval(index,query,root):
 retriever=Retriever(root);selected=retriever.select(retriever.build(index),query);mapped=0
 by_id={b['id']:(p,b) for p in index['pages'] for b in p['blocks']}
 for block in selected:
  page,raw=by_id[block['id']]
  try:range_regions(page,raw,0,len(raw['text'].strip()));mapped+=1
  except ValueError:pass
 return {'block_ids':[b['id'] for b in selected],'quotes':[b['text'] for b in selected[:5]],'coordinate_mapped':mapped,'selected':len(selected)}

def compare(path,query,cache):
 started=time.perf_counter();legacy=legacy_metadata(path);legacy_seconds=time.perf_counter()-started
 started=time.perf_counter();index=parse_pdf(path,'benchmark');structured_seconds=time.perf_counter()-started;document=index.get('document',{})
 legacy_index={k:v for k,v in index.items() if k!='document'}
 old_retrieval=retrieval(legacy_index,query,cache/'old');new_retrieval=retrieval(index,query,cache/'new')
 metadata=document.get('metadata',{});quality=document.get('quality',{})
 return {'file':str(path),'pages':index.get('total_pages'),'legacy':{'metadata':{k:legacy[k] for k in ['title','authors','year','doi']},'seconds':legacy_seconds,'first_page_preview':' '.join(legacy['first_page_text'].split())[:800],'retrieval':old_retrieval},'structured':{'metadata':{k:metadata.get(k) for k in ['title','authors','year','doi','status','sources']},'seconds':structured_seconds,'first_page_preview':next((p['normalized_text'] for p in document.get('pages',[]) if p['physical_page']==1),'')[:800],'sections':[s['title'] for s in document.get('sections',[])],'paragraphs':len(document.get('paragraphs',[])),'quality':quality,'retrieval':new_retrieval},'evidence_block_ids_preserved':set(new_retrieval['block_ids'])<={b['id'] for p in index['pages'] for b in p['blocks']},'highlight_mapping_preserved':new_retrieval['coordinate_mapped']==new_retrieval['selected'] if new_retrieval['selected'] else None}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('paths',nargs='+');parser.add_argument('--query',default='evidence support result');parser.add_argument('--output');args=parser.parse_args()
 files=[]
 for value in args.paths:
  path=Path(value);files.extend(sorted(path.glob('*.pdf')) if path.is_dir() else [path])
 with tempfile.TemporaryDirectory() as folder:report={'synthetic':False,'model_calls':0,'query':args.query,'documents':[compare(path,args.query,Path(folder)/str(n)) for n,path in enumerate(files) if path.is_file()]}
 text=json.dumps(report,ensure_ascii=False,indent=2)
 if args.output:Path(args.output).write_text(text,encoding='utf-8')
 sys.stdout.buffer.write(text.encode('utf-8')+b'\n')
if __name__=='__main__':main()
