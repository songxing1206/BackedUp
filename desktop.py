"""Frozen app entry point. Source users continue to use launcher.py."""
import argparse,json,sys,signal
from launcher import launch,diagnostics

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--serve',action='store_true');parser.add_argument('--port',type=int,default=8787);parser.add_argument('--diagnose',action='store_true');parser.add_argument('--no-browser',action='store_true')
 parser.add_argument('--backup-to');parser.add_argument('--restore-from');parser.add_argument('--restore-to');args=parser.parse_args()
 if args.backup_to or args.restore_from or args.restore_to:
  if bool(args.backup_to)==bool(args.restore_from) or bool(args.restore_from)!=bool(args.restore_to):parser.error('请选择 --backup-to 或同时提供 --restore-from 与 --restore-to')
  from app.backup import create_backup,restore_backup
  from app.storage import data_dir
  result=create_backup(data_dir(),args.backup_to) if args.backup_to else restore_backup(args.restore_from,args.restore_to)
  print(f'完成：数据格式{result["data_version"]}，{len(result["files"])}个文件；不包含API Key。');return 0
 def stop(*_):raise KeyboardInterrupt
 signal.signal(signal.SIGTERM,stop)
 if hasattr(signal,'SIGHUP'):signal.signal(signal.SIGHUP,stop)
 try:
  if args.serve:
   from server import serve
   serve(args.port);return 0
  if args.diagnose:print(json.dumps(diagnostics(),ensure_ascii=False));return 0
  return launch(not args.no_browser)
 except KeyboardInterrupt:return 0
 except Exception as error:
  # No raw traceback in a GUI error: it could contain local paths or credentials.
  print('启动失败，请检查运行环境。错误类型：'+type(error).__name__,file=sys.stderr)
  if isinstance(error,FileNotFoundError):
   from pathlib import Path
   print('缺失资源：'+Path(error.filename or '').name,file=sys.stderr)
  if not args.no_browser and not args.serve:
   from app.platform_support import show_startup_error
   show_startup_error()
  return 1

if __name__=='__main__':sys.exit(main())
