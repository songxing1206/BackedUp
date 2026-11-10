"""Start or reuse this checkout's local service; never call a model."""
import argparse,json,signal,socket,subprocess,sys,time,urllib.request,webbrowser
from pathlib import Path
from app.runtime import APP_VERSION,instance_id
from app.storage import data_dir,initialize
from app.platform_support import startup_lock

ROOT=Path(__file__).resolve().parent
PORTS=range(8787,8798)

def probe(port):
 try:
  # Loopback must not be routed through a user's API/network proxy.
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  with opener.open(f'http://127.0.0.1:{port}/api/health',timeout=.4) as response:
   value=json.loads(response.read(2048))
  return value if isinstance(value,dict) else None
 except (OSError,ValueError):return None

def existing_service():
 for port in PORTS:
  value=probe(port)
  if value and value.get('app')=='backed-up' and value.get('instance')==instance_id(data_dir()) and value.get('status')=='ready':return port,value
 return None

def free_port():
 for port in PORTS:
  with socket.socket() as sock:
   try:
    sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE if sys.platform=='win32' else socket.SO_REUSEADDR,1)
    sock.bind(('127.0.0.1',port));sock.listen(1)
   except OSError:continue
   return port
 raise RuntimeError('8787–8797 端口均被占用，请关闭已有服务后重试。')

def dependencies():
 missing=[]
 for name in ['pypdf','bibtexparser','pypdfium2','PIL','platformdirs']:
  try:__import__(name)
  except (ImportError,OSError):missing.append(name)
 return missing

def diagnostics():
 missing=dependencies();service=existing_service()
 return {'version':APP_VERSION,'python':sys.version.split()[0],
         'dependencies':'ok' if not missing else {'missing':missing},
         'service':{'status':'ready','port':service[0],'version':service[1].get('version')} if service else {'status':'stopped'}}

def open_page(port,enabled):
 url=f'http://localhost:{port}/'
 print(f'网页地址：{url}',flush=True)
 if enabled:webbrowser.open(url)

def launch(open_browser=True):
 missing=dependencies()
 if missing:raise RuntimeError('缺少运行依赖：'+', '.join(missing)+'。请按 README 安装 requirements.txt。')
 # Serialize two simultaneous clicks until readiness, then release the lock.
 directory=data_dir().parent;directory.mkdir(parents=True,exist_ok=True)
 process=None
 try:
  with startup_lock(directory/(data_dir().name+'-launcher.lock')):
   service=existing_service()
   if service:
    if service[1].get('version')!=APP_VERSION:raise RuntimeError('已有不同版本服务运行，请先在旧网页点击退出服务，再打开新版；不会强行结束任务。')
    open_page(service[0],open_browser);return 0
   initialize(ROOT/'output')
   port=free_port()
   command=[sys.executable,'--serve','--port',str(port)] if getattr(sys,'frozen',False) else [sys.executable,str(ROOT/'server.py'),'--port',str(port)]
   process=subprocess.Popen(command,cwd=ROOT)
   deadline=time.monotonic()+15
   while time.monotonic()<deadline:
    if process.poll() is not None:raise RuntimeError('后台启动失败，请查看上方错误并运行“诊断.command”。')
    ready=probe(port)
    if ready and ready.get('instance')==instance_id(data_dir()) and ready.get('status')=='ready':break
    time.sleep(.1)
   else:raise RuntimeError('后台未在15秒内就绪，请运行“诊断.command”。')
   open_page(port,open_browser)
  print('保持此终端开启；按 Control+C 退出服务。',flush=True)
  return process.wait()
 finally:
  if process and process.poll() is None:
   process.terminate()
   try:process.wait(timeout=5)
   except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');parser.add_argument('--diagnose',action='store_true');args=parser.parse_args()
 def stop(*_):raise KeyboardInterrupt
 signal.signal(signal.SIGTERM,stop)
 if hasattr(signal,'SIGHUP'):signal.signal(signal.SIGHUP,stop)
 try:
  if args.diagnose:print(json.dumps(diagnostics(),ensure_ascii=False,indent=2))
  else:sys.exit(launch(not args.no_browser))
 except KeyboardInterrupt:print('\n服务已退出。')
 except (OSError,RuntimeError,ValueError) as error:print('启动失败：'+str(error),file=sys.stderr);sys.exit(1)
