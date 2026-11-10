"""Small native adapters; no model calls or shell commands."""
import os,subprocess,sys,time
from contextlib import contextmanager

@contextmanager
def startup_lock(path,timeout=20):
 with path.open('a+b') as stream:
  if stream.seek(0,2)==0:stream.write(b'0');stream.flush()
  if sys.platform=='win32':
   import msvcrt
   def acquire():stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
   def release():stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
  else:
   import fcntl
   def acquire():fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
   def release():fcntl.flock(stream,fcntl.LOCK_UN)
  deadline=time.monotonic()+timeout
  while True:
   try:acquire();break
   except OSError:
    if time.monotonic()>=deadline:raise RuntimeError('已有启动流程未结束，请稍后重试。') from None
    time.sleep(.1)
  try:yield
  finally:release()

def open_directory(path):
 if sys.platform=='win32':os.startfile(str(path))
 elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
 else:subprocess.Popen(['xdg-open',str(path)])

def show_startup_error():
 message='若旧版网页仍在运行，请先点击退出服务再启动新版。否则请确认数据目录可写，并使用诊断入口检查。'
 if sys.platform=='win32':
  import ctypes
  ctypes.windll.user32.MessageBoxW(None,message,'Backed Up 启动失败',0x10)
 elif sys.platform=='darwin':subprocess.run(['osascript','-e',f'display alert "Backed Up 启动失败" message "{message}"'],check=False)
