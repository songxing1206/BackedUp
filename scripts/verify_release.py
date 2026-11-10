"""Offline release gate: Python fixtures, frontend syntax and UI mock tests."""
import shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
 node=shutil.which('node')
 if not node:
  print('缺少 Node.js，无法完成前端发布检查。',file=sys.stderr);return 1
 commands=[[sys.executable,'-m','unittest','discover','-s','tests','-q']]
 commands.extend([node,'--check',str(p.relative_to(ROOT))] for p in sorted((ROOT/'web').glob('*.js')))
 commands.extend([node,str(p.relative_to(ROOT))] for p in sorted((ROOT/'tests').glob('*.cjs')))
 for command in commands:
  print('检查：'+' '.join(command[1:]),flush=True)
  if subprocess.run(command,cwd=ROOT).returncode:return 1
 print('离线发布检查全部通过；未调用真实模型，不代表模型语义验收完成。')
 return 0

if __name__=='__main__':sys.exit(main())
