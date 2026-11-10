"""Build an unsigned arm64 app using explicit resource allowlists."""
import hashlib,json,os,platform,plistlib,shutil,subprocess,sys,zipfile,importlib.metadata
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.runtime import APP_VERSION

def main():
 if sys.platform!='darwin' or platform.machine()!='arm64':raise SystemExit('本脚本当前构建 macOS Apple Silicon 测试包')
 tools=ROOT/'.build-tools';environment={**os.environ,'PYTHONPATH':str(tools),'PYINSTALLER_CONFIG_DIR':str(ROOT/'build/pyinstaller-cache')}
 for name in ['platformdirs','cryptography','cffi','pycparser','charset-normalizer','pyparsing','bibtexparser','pypdf','Pillow']:
  try:distribution=importlib.metadata.distribution(name)
  except importlib.metadata.PackageNotFoundError:continue
  for entry in distribution.files or []:
   if any(word in entry.name.upper() for word in ['LICENSE','COPYING','NOTICE']):
    path=distribution.locate_file(entry)
    if path.is_file():shutil.copy2(path,ROOT/'licenses'/(name+'-'+str(entry).replace('/','_')))
 for path in tools.glob('pyinstaller-*.dist-info/licenses/*'):
  if path.is_file():shutil.copy2(path,ROOT/'licenses'/('PyInstaller-'+path.name))
 python_license=Path(sys.base_prefix)/'lib/python3.12/LICENSE.txt'
 if python_license.is_file():shutil.copy2(python_license,ROOT/'licenses/Python-LICENSE.txt')
 command=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--name','BackedUp','--target-architecture','arm64','--osx-bundle-identifier','org.backedup.local','--exclude-module','numpy','--exclude-module','jinja2','--exclude-module','tkinter','--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build/pyinstaller'),'--specpath',str(ROOT/'build'),
  '--add-data',str(ROOT/'web')+':web','--add-data',str(ROOT/'app/vendor/citefact/prompts')+':app/vendor/citefact/prompts','--add-data',str(ROOT/'app/vendor/citefact/LICENSE')+':app/vendor/citefact','--add-data',str(ROOT/'licenses')+':licenses','--add-data',str(ROOT/'THIRD_PARTY_NOTICES.md')+':.',str(ROOT/'desktop.py')]
 # Some managed Python distributions require an additional trust resource beside ssl.py.
 # Preserve the runtime trust policy; never bypass TLS verification to make the bundle start.
 import ssl
 trust_resource=Path(ssl.__file__).parent/'codex-rejected-cas.pem'
 if trust_resource.is_file():command[-1:-1]=['--add-data',str(trust_resource)+':.']
 subprocess.run(command,cwd=ROOT,env=environment,check=True)
 app=ROOT/'dist/BackedUp.app'
 plist=app/'Contents/Info.plist';info=plistlib.loads(plist.read_bytes())
 info.update(CFBundleShortVersionString=APP_VERSION.split('-')[0],CFBundleVersion=APP_VERSION.split('-')[0],BackedUpReleaseVersion=APP_VERSION)
 plist.write_bytes(plistlib.dumps(info))
 subprocess.run(['codesign','--force','--deep','--sign','-',str(app)],check=True)
 prohibited={'output','private','tasks','assets','.venv','.build-tools','__pycache__','model.json'}
 entries=[]
 for path in sorted(app.rglob('*')):
  relative=path.relative_to(app)
  if any(part in prohibited for part in relative.parts) or path.suffix in {'.pdf','.jsonl','.log'}:raise RuntimeError('发布包存在禁止文件：'+str(relative))
  if path.is_file() and not path.is_symlink():
   with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
   entries.append({'file':str(relative),'bytes':path.stat().st_size,'sha256':digest})
 release=ROOT/'release';release.mkdir(exist_ok=True)
 output=release/f'BackedUp-{APP_VERSION}-macOS-arm64.zip'
 # ditto preserves app symlinks and executable modes, unlike generic zip writers.
 subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(output)],check=True)
 with zipfile.ZipFile(output,'a',zipfile.ZIP_DEFLATED) as archive:
  for name in ['user-guide.md','release-scope.md','support.md']:archive.write(ROOT/'docs'/name,name)
  archive.write(ROOT/'CHANGELOG.md','CHANGELOG.md')
 manifest={'version':APP_VERSION,'architecture':'arm64','developer_signed':False,'notarized':False,'file_count':len(entries),'files':entries}
 (release/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 (release/'安装说明.txt').write_text('macOS Apple Silicon 测试版。解压后将 BackedUp.app 拖到应用程序文件夹并打开。无需安装 Python。此包未签名、未公证，系统可能阻止打开；仅用于受邀测试，不是正式公开发行版。通过网页“退出服务”关闭后台。数据保存在 ~/Library/Application Support/BackedUp/data-v1，不随替换应用删除。升级前备份该目录。Key默认仅本次运行。选择云API会发送检查所需文字并由用户承担费用。Intel/Windows/干净电脑/真实模型验收未完成。')
 print(output)

if __name__=='__main__':main()
