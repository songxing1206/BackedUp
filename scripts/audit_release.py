"""Audit explicit source candidates and actual macOS ZIP; never print secrets."""
import argparse,hashlib,json,re,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.runtime import APP_VERSION

FORBIDDEN={'output','private','assets','tasks','.venv','.build-tools','__pycache__','model.json','.env','.git','.execution'}
PATTERNS=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(rb'AIza[0-9A-Za-z_-]{35}'),re.compile(rb'\bsk-(?:proj-|ant-)?[0-9A-Za-z_-]{24,}')]
DOCS={'retrieval-efficiency.md','memory-real-42.md','pending-release.md','release-scope.md','user-guide.md','support.md','windows-adaptation.md'}

def secret_hits(name,payload):
 return [{'file':name,'pattern':i+1,'line':payload[:m.start()].count(b'\n')+1} for i,pattern in enumerate(PATTERNS) for m in pattern.finditer(payload)]

def source_files():
 selected=[ROOT/name for name in ['README.md','CHANGELOG.md','THIRD_PARTY_NOTICES.md','requirements.txt','.gitignore','bootstrap.py','launcher.py','desktop.py','server.py','启动.command','诊断.command','启动.bat','诊断.bat']]
 for folder in ['app','web','scripts','tests','licenses','.github']:
  selected.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and not any(part in FORBIDDEN for part in p.relative_to(ROOT).parts))
 selected.extend(ROOT/'docs'/name for name in DOCS)
 return sorted(set(p for p in selected if p.exists() and p.name not in {'audit_local_migration.py','package_faults.py'}))

def audit(build_source=False):
 files=source_files();report={'version':APP_VERSION,'source_file_count':len(files),'source_findings':[],'package_findings':[]}
 for path in files:
  name=path.relative_to(ROOT).as_posix()
  if path.is_symlink() or path.suffix.lower() in {'.pdf','.jsonl','.log'}:report['source_findings'].append({'file':name,'reason':'unexpected source file'})
  report['source_findings'].extend(secret_hits(name,path.read_bytes()))
 package=ROOT/'release'/f'BackedUp-{APP_VERSION}-macOS-arm64.zip';manifest=json.loads((ROOT/'release/manifest.json').read_text())
 if manifest['version']!=APP_VERSION:report['package_findings'].append({'reason':'manifest version mismatch'})
 with zipfile.ZipFile(package) as archive:
  names=archive.namelist()
  required=['THIRD_PARTY_NOTICES.md','app/vendor/citefact/LICENSE']
  for rel in required:
   if not any(n.endswith('/'+rel) for n in names):report['package_findings'].append({'reason':'missing license document','file':rel})
  for document in (ROOT/'licenses').rglob('*'):
   if document.is_file() and not any(n.endswith('/licenses/'+document.relative_to(ROOT/'licenses').as_posix()) for n in names):report['package_findings'].append({'reason':'missing dependency notice','file':document.name})
  for info in archive.infolist():
   parts=Path(info.filename).parts
   if any(p in FORBIDDEN for p in parts) or Path(info.filename).suffix.lower() in {'.pdf','.jsonl','.log'}:report['package_findings'].append({'file':info.filename,'reason':'forbidden file'})
   if not info.is_dir():report['package_findings'].extend(secret_hits(info.filename,archive.read(info)))
  for row in manifest['files']:
   name='BackedUp.app/'+row['file']
   if name not in names or hashlib.sha256(archive.read(name)).hexdigest()!=row['sha256']:report['package_findings'].append({'file':name,'reason':'manifest hash mismatch'})
 report['package']={'file':package.name,'bytes':package.stat().st_size,'sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'manifest_files':len(manifest['files'])}
 if report['source_findings'] or report['package_findings']:raise ValueError(json.dumps(report,ensure_ascii=False))
 if build_source:
  target=ROOT/'release'/f'BackedUp-{APP_VERSION}-source.zip'
  with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
   for path in files:archive.write(path,'BackedUp-source/'+path.relative_to(ROOT).as_posix())
  with zipfile.ZipFile(target) as archive:
   if archive.testzip() is not None:raise ValueError('源码ZIP完整性失败')
   for path in files:
    if archive.read('BackedUp-source/'+path.relative_to(ROOT).as_posix())!=path.read_bytes():raise ValueError('源码ZIP与审查文件不一致')
  report['source_archive']={'file':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
 report['scope']='Allowlist and standard credential-pattern scan; not proof against every secret format. Working directory is not an audited Git repository.'
 (ROOT/'release/candidate-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--build-source',action='store_true');args=parser.parse_args()
 print(json.dumps(audit(args.build_source),ensure_ascii=False))
