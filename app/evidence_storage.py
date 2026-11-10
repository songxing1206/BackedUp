"""Streaming schema-1 storage with a disposable, single-source read cache."""
from .text_io import read_text_compat, write_text_utf8
import hashlib,json

def stamp(path):
 s=path.stat();return [s.st_size,s.st_mtime_ns]

def source_summary(sources,sid):
 return dict.get(sources,sid,{}) if isinstance(sources,IndexedSources) else sources.get(sid,{})

class IndexedSources(dict):
 def __init__(self,path,entries):
  super().__init__({sid:e['summary'] for sid,e in entries.items()})
  self.path=path;self.entries=entries;self.cached=None;self.signature=stamp(path)
 def __getitem__(self,sid):
  if stamp(self.path)!=self.signature:raise ValueError('证据包已变化，请重新加载')
  if self.cached and self.cached[0]==sid:return self.cached[1]
  self.cached=None
  entry=self.entries[sid]
  with self.path.open('rb') as f:
   f.seek(entry['offset']);raw=f.read(entry['length'])
  if hashlib.sha256(raw).hexdigest()!=entry['digest']:raise ValueError('证据包内容校验失败')
  value=json.loads(raw);self.cached=(sid,value);return value
 def get(self,sid,default=None):return self[sid] if sid in self else default
 def clear_cache(self):self.cached=None

def load_package(path):
 sidecar=path.with_suffix('.offsets.json')
 try:
  meta=json.loads(read_text_compat(sidecar))
  if meta['stamp']==stamp(path):return {**meta['header'],'sources':IndexedSources(path,meta['entries'])}
 except (OSError,ValueError,KeyError,TypeError):pass
 return json.loads(read_text_compat(path))

def write_package(path,header,sources):
 entries={};temp=path.with_suffix('.tmp')
 try:
  with temp.open('wb') as f:
   f.write(json.dumps(header,ensure_ascii=False,separators=(',',':')).encode()[:-1]+b',"sources":{')
   for sid,index in sources:
    if entries:f.write(b',')
    f.write(json.dumps(sid).encode()+b':')
    offset=f.tell();raw=json.dumps(index,ensure_ascii=False,separators=(',',':')).encode();f.write(raw)
    entries[sid]=dict(offset=offset,length=len(raw),digest=hashlib.sha256(raw).hexdigest(),summary={k:v for k,v in index.items() if k not in {'pages','document'}})
    del raw,index
   f.write(b'}}')
  temp.replace(path)
  sidecar=path.with_suffix('.offsets.json');pending=sidecar.with_suffix('.tmp')
  write_text_utf8(pending, json.dumps(dict(stamp=stamp(path),header=header,entries=entries),ensure_ascii=False));pending.replace(sidecar)
 except BaseException:
  temp.unlink(missing_ok=True);raise
 return {**header,'sources':IndexedSources(path,entries)}
