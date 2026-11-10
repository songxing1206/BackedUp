"""Build a Windows x64 portable beta on Windows; never include user data."""
import hashlib,json,platform,shutil,subprocess,sys,importlib.metadata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.runtime import APP_VERSION

def main():
 if sys.platform!='win32' or platform.machine().lower() not in {'amd64','x86_64'}:raise SystemExit('请使用Windows x64与64位Python构建；不能在macOS交叉打包')
 for name in ['pypdf','bibtexparser','pypdfium2','Pillow','platformdirs','pyinstaller']:
  distribution=importlib.metadata.distribution(name)
  for entry in distribution.files or []:
   if any(word in entry.name.upper() for word in ['LICENSE','COPYING','NOTICE']):
    path=distribution.locate_file(entry)
    if path.is_file():shutil.copy2(path,ROOT/'licenses'/(name+'-'+str(entry).replace('/','_').replace('\\','_')))
 python_license=Path(sys.base_prefix)/'LICENSE.txt'
 if python_license.is_file():shutil.copy2(python_license,ROOT/'licenses/Python-LICENSE.txt')
 command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--console','--name','BackedUp','--python-option','X utf8','--exclude-module','numpy','--exclude-module','jinja2','--exclude-module','tkinter','--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build/windows'),'--specpath',str(ROOT/'build')]
 for source,target in [('web','web'),('app/vendor/citefact/prompts','app/vendor/citefact/prompts'),('app/vendor/citefact/LICENSE','app/vendor/citefact'),('licenses','licenses'),('THIRD_PARTY_NOTICES.md','.')]:command.extend(['--add-data',str(ROOT/source)+';'+target])
 subprocess.run([*command,str(ROOT/'desktop.py')],cwd=ROOT,check=True)
 folder=ROOT/'dist/BackedUp';entries=[]
 (folder/'使用说明.txt').write_text('Windows x64便携测试版，完整解压目录后双击BackedUp.exe，不要删除_internal。保持控制台开启，通过网页退出服务。数据保存在%LOCALAPPDATA%/BackedUp/data-v1。仅支持用户自填API，Key默认仅会话使用，模型费用由用户承担。备份：BackedUp.exe --backup-to 新备份.zip；恢复：--restore-from 备份.zip --restore-to 不存在的新目录。本包未代码签名，SmartScreen可能提示；干净机器及真实模型仍需验收。',encoding='utf-8')
 for path in sorted(folder.rglob('*')):
  relative=path.relative_to(folder)
  if any(p in {'output','assets','tasks','private','tests','.venv','.build-tools','model.json'} for p in relative.parts) or path.suffix.lower() in {'.pdf','.jsonl','.log'}:raise RuntimeError('禁止发布文件：'+str(relative))
  if path.is_file():
   with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
   entries.append({'file':relative.as_posix(),'bytes':path.stat().st_size,'sha256':digest})
 release=ROOT/'release';release.mkdir(exist_ok=True)
 (release/'windows-manifest.json').write_text(json.dumps({'version':APP_VERSION,'platform':'windows-x64','signed':False,'files':entries},indent=2),encoding='utf-8')
 output=shutil.make_archive(str(release/f'BackedUp-{APP_VERSION}-Windows-x64'),'zip',folder.parent,folder.name)
 print(output)

if __name__=='__main__':main()
