"""Explicit local backup/restore commands. No models, no automatic overwrites."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.storage import data_dir
from app.backup import create_backup,restore_backup

if __name__=='__main__':
 parser=argparse.ArgumentParser();commands=parser.add_subparsers(dest='command',required=True)
 backup=commands.add_parser('backup');backup.add_argument('--destination',required=True)
 restore=commands.add_parser('restore');restore.add_argument('--backup',required=True);restore.add_argument('--target',required=True)
 args=parser.parse_args()
 try:
  result=create_backup(data_dir(),args.destination) if args.command=='backup' else restore_backup(args.backup,args.target)
  print(f'完成：数据格式{result["data_version"]}，{len(result["files"])}个文件；API Key不包含在备份中。')
 except (OSError,ValueError,KeyError) as error:print('未完成：'+str(error),file=sys.stderr);sys.exit(1)
