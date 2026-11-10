"""Real loopback launch test in a disposable copy without user data or keys."""
import json,shutil,socket,subprocess,sys,tempfile,time,urllib.request,os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.runtime import instance_id

opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

def find_service(root):
 for port in range(8787,8798):
  try:
   with opener.open(f'http://127.0.0.1:{port}/api/health',timeout=.2) as response:value=json.loads(response.read(2048))
   if value.get('instance')==instance_id(root/'userdata/data-v1'):return port
  except (OSError,ValueError):pass
 return None

def main():
 with tempfile.TemporaryDirectory(prefix='backed-up-smoke-') as directory:
  root=Path(directory)
  shutil.copytree(ROOT/'app',root/'app',ignore=shutil.ignore_patterns('__pycache__'))
  shutil.copytree(ROOT/'web',root/'web')
  for name in ['server.py','launcher.py']:shutil.copy2(ROOT/name,root/name)
  environment={**os.environ,'BACKEDUP_DATA_HOME':str(root/'userdata'),'BACKEDUP_CACHE_HOME':str(root/'cache')}
  # The preferred port must be occupied, either by the real app or our fixture.
  blocker=socket.socket()
  try:blocker.bind(('127.0.0.1',8787));blocker.listen()
  except OSError:blocker.close();blocker=None
  process=None
  try:
   with (root/'smoke.log').open('w+') as log:
    process=subprocess.Popen([sys.executable,'launcher.py','--no-browser'],cwd=root,stdout=log,stderr=log,env=environment)
    deadline=time.monotonic()+20;port=None
    while time.monotonic()<deadline:
     port=find_service(root)
     if port:break
     if process.poll() is not None:raise RuntimeError('启动器提前退出')
     time.sleep(.1)
    if port is None or port==8787:raise RuntimeError('端口冲突恢复未通过')
    reuse=subprocess.run([sys.executable,'launcher.py','--no-browser'],cwd=root,capture_output=True,text=True,timeout=20,env=environment)
    if reuse.returncode or f':{port}/' not in reuse.stdout:raise RuntimeError('重复启动复用未通过')
    with opener.open(f'http://localhost:{port}/',timeout=2) as response:
     if response.status!=200:raise RuntimeError('网页未就绪')
    # Windows TerminateProcess does not run the launcher's finally block, so
    # stop the child through the same endpoint as the product's Exit button.
    with opener.open(f'http://127.0.0.1:{port}/api/config',timeout=2) as response:
     token=json.loads(response.read())['token']
    request=urllib.request.Request(f'http://127.0.0.1:{port}/api/shutdown',data=b'{}',method='POST',headers={'Content-Type':'application/json','X-BackedUp-Token':token})
    with opener.open(request,timeout=2) as response:
     if response.status!=200:raise RuntimeError('服务退出接口失败')
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and find_service(root) is not None:time.sleep(.1)
    if find_service(root) is not None:raise RuntimeError('退出后服务仍运行')
    process.wait(timeout=10)
    print(f'真实启动冒烟通过：端口冲突→{port}；重复启动复用；网页200；退出释放端口。未使用用户数据或模型。')
  finally:
   if process and process.poll() is None:process.terminate();process.wait(timeout=10)
   if blocker:blocker.close()

if __name__=='__main__':main()
