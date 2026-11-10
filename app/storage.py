"""Stable per-user storage, isolated by incompatible data format, not release."""
from .text_io import read_text_compat, write_text_utf8
import json,os,shutil,tempfile
from pathlib import Path
from platformdirs import user_data_path,user_cache_path

DATA_VERSION=1

def data_home():
 return Path(os.environ['BACKEDUP_DATA_HOME']).expanduser().resolve() if os.environ.get('BACKEDUP_DATA_HOME') else user_data_path('BackedUp',appauthor=False)

def data_dir():return data_home()/f'data-v{DATA_VERSION}'

def cache_dir():
 base=Path(os.environ['BACKEDUP_CACHE_HOME']).expanduser().resolve() if os.environ.get('BACKEDUP_CACHE_HOME') else user_cache_path('BackedUp',appauthor=False)
 return base/f'data-v{DATA_VERSION}'

def rewrite_paths(value,old,new):
 if isinstance(value,list):return [rewrite_paths(v,old,new) for v in value]
 if isinstance(value,dict):
  result={k:rewrite_paths(v,old,new) for k,v in value.items()}
  if isinstance(result.get('path'),str):
   try:result['path']=str(new/Path(result['path']).resolve().relative_to(old))
   except ValueError:pass
  return result
 return value

def initialize(legacy=None):
 target=data_dir();home=data_home();home.mkdir(parents=True,exist_ok=True,mode=0o700)
 if os.name!='nt':home.chmod(0o700)
 if target.exists():
  manifest=target/'storage.json'
  if manifest.exists() and json.loads(read_text_compat(manifest)).get('data_version')!=DATA_VERSION:raise ValueError('数据格式不兼容，未修改旧数据。')
  return target
 staging=Path(tempfile.mkdtemp(prefix='.import-',dir=home))
 try:
  imported=False
  if legacy and Path(legacy).is_dir():
   legacy=Path(legacy).resolve()
   for name in ['assets','tasks','evidence','checks']:
    source=legacy/name
    if not source.is_dir():continue
    shutil.copytree(source,staging/name,ignore=shutil.ignore_patterns('cache','*-prompt.md','*-diagnostic.json'))
    for file in (staging/name).rglob('*.json'):
     value=rewrite_paths(json.loads(read_text_compat(file)),legacy,target)
     write_text_utf8(file, json.dumps(value,ensure_ascii=False))
    imported=True
   settings=legacy/'private/model.json'
   if settings.is_file():
    preferences=json.loads(read_text_compat(settings));preferences={k:preferences[k] for k in ['provider','model','base_url'] if k in preferences}
    (staging/'settings').mkdir(exist_ok=True)
    write_text_utf8(staging/'settings/model.json', json.dumps({**preferences,'api_key':'','session_only':True}))
  write_text_utf8(staging/'storage.json', json.dumps({'data_version':DATA_VERSION,'legacy_imported':imported}))
  staging.rename(target)
 finally:
  if staging.exists():shutil.rmtree(staging)
 return target

def history_namespaces():
 return sorted(p.name for p in data_home().glob('data-v*') if p.is_dir() and p.name[6:].isdigit())

def namespace_dir(name):
 if name not in history_namespaces():raise ValueError('历史数据目录不存在')
 return data_home()/name
