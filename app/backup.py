"""Verified local backups; restore never overwrites an existing directory."""
import hashlib,json,os,shutil,stat,tempfile,zipfile
from pathlib import Path,PurePosixPath
from .storage import DATA_VERSION,rewrite_paths

MAX_RESTORE_BYTES=1024*1024*1024
DIRECTORIES={'assets','tasks','evidence','checks','settings','checkpoints'}

def read_local_json(path):
 try:return json.loads(path.read_text(encoding='utf-8'))
 except UnicodeDecodeError:return json.loads(path.read_text()) # Existing Windows data may use the system code page.

def files(root):
 result=[]
 for directory in DIRECTORIES:
  if (root/directory).is_symlink():raise ValueError('备份目录包含符号链接，未读取其目标')
  for path in (root/directory).rglob('*'):
   if path.is_symlink():raise ValueError('备份目录包含符号链接，未读取其目标')
   if path.is_file() and 'cache' not in path.relative_to(root).parts and not path.name.endswith(('-diagnostic.json','-prompt.md')):result.append(path)
 if (root/'storage.json').is_file():result.append(root/'storage.json')
 return sorted(result)

def without_keys(value):
 if isinstance(value,dict):return {k:without_keys(v) for k,v in value.items() if k!='api_key'}
 if isinstance(value,list):return [without_keys(v) for v in value]
 return value

def check_attachments(value,root):
 if isinstance(value,dict):
  if value.get('path') and str(value['path']).lower().endswith('.pdf'):
   path=Path(value['path']).resolve()
   if not path.is_relative_to(root/'assets') or not path.is_file():raise ValueError('备份需要完整本地PDF；存在外部或缺失附件，请先导入本地PDF或导出独立报告包')
  for item in value.values():check_attachments(item,root)
 elif isinstance(value,list):
  for item in value:check_attachments(item,root)

def create_backup(root,destination):
 root=Path(root).resolve();destination=Path(destination).resolve()
 if destination.exists():raise ValueError('备份目标已存在，请使用新文件名')
 version=read_local_json(root/'storage.json')['data_version']
 for path in (root/'checks').glob('*.json'):
  if read_local_json(path).get('status') in {'queued','running'}:raise ValueError('请先完成或取消检查，再备份')
 before=files(root);states={p:(p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in before}
 destination.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(dir=destination.parent,suffix='.tmp');os.close(fd);temporary=Path(name)
 try:
  manifest={'backup_version':1,'data_version':version,'original_root':str(root),'files':[]}
  with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
   for path in before:
    relative=path.relative_to(root).as_posix()
    if path.suffix=='.json':
     value=without_keys(read_local_json(path))
     check_attachments(value,root)
     if relative=='settings/model.json':value={k:v for k,v in value.items() if k in {'provider','model','base_url'}};value['session_only']=True
     payload=json.dumps(value,ensure_ascii=False).encode();archive.writestr(relative,payload);digest=hashlib.sha256(payload).hexdigest();size=len(payload)
    else:
     digest=hashlib.sha256();size=0
     with path.open('rb') as source,archive.open(relative,'w') as output:
      for chunk in iter(lambda:source.read(1024*1024),b''):output.write(chunk);digest.update(chunk);size+=len(chunk)
     digest=digest.hexdigest()
    manifest['files'].append({'path':relative,'sha256':digest,'bytes':size})
   archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
  if files(root)!=before or any(states[p]!=(p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in before):raise ValueError('备份期间数据发生变化，未发布不一致的备份')
  # Publish without replacing even if another process creates the destination.
  if os.name=='nt':temporary.rename(destination) # Windows rename refuses an existing target.
  else:os.link(temporary,destination)
 finally:temporary.unlink(missing_ok=True)
 return manifest

def restore_backup(archive_path,target,expected_version=DATA_VERSION):
 target=Path(target).resolve()
 if target.exists():raise ValueError('恢复目录已存在，未覆盖任何数据')
 staging=None
 try:
  with zipfile.ZipFile(archive_path) as archive:
   names=archive.namelist()
   if len(names)!=len(set(names)):raise ValueError('备份包含重复文件')
   if archive.getinfo('manifest.json').file_size>4*1024*1024 or sum(i.file_size for i in archive.infolist())>MAX_RESTORE_BYTES:raise ValueError('备份超过恢复容量上限')
   manifest=json.loads(archive.read('manifest.json'))
   if manifest.get('backup_version')!=1 or manifest.get('data_version')!=expected_version:raise ValueError('备份数据格式不兼容')
   entries=manifest['files']
   if set(names)!={'manifest.json',*(row['path'] for row in entries)}:raise ValueError('备份文件清单不一致')
   if sum(i.file_size for i in archive.infolist())>MAX_RESTORE_BYTES:raise ValueError('备份超过恢复容量上限')
   for info in archive.infolist():
    path=PurePosixPath(info.filename)
    if path.is_absolute() or '..' in path.parts or '\\' in info.filename or stat.S_ISLNK(info.external_attr>>16):raise ValueError('备份路径不安全')
    if info.filename!='manifest.json' and path.parts[0] not in DIRECTORIES|{'storage.json'}:raise ValueError('备份包含未知目录')
   target.parent.mkdir(parents=True,exist_ok=True);staging=Path(tempfile.mkdtemp(prefix='.restore-',dir=target.parent))
   for row in entries:
    path=staging/row['path'];path.parent.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256();size=0
    with archive.open(row['path']) as source,path.open('wb') as output:
     for chunk in iter(lambda:source.read(1024*1024),b''):output.write(chunk);digest.update(chunk);size+=len(chunk)
    if size!=row['bytes'] or digest.hexdigest()!=row['sha256']:raise ValueError('备份完整性校验失败，原数据保留')
    if path.suffix=='.json':
     value=rewrite_paths(without_keys(read_local_json(path)),Path(manifest['original_root']).resolve(),target)
     path.write_text(json.dumps(value,ensure_ascii=False))
   if target.exists():raise ValueError('恢复目录已存在，未覆盖任何数据')
   staging.rename(target);staging=None
  return manifest
 finally:
  if staging and staging.exists():shutil.rmtree(staging)
