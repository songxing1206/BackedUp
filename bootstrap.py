"""Create an isolated runtime on first launch; never access model credentials."""
import os, subprocess, sys, venv
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    if sys.version_info < (3,10):
        raise RuntimeError('需要 Python 3.10 或更新版本。')
    python=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists():
        print('首次启动：创建本地 Python 环境……',flush=True)
        venv.EnvBuilder(with_pip=True).create(ROOT/'.venv')
    check=subprocess.run([str(python),'-c','import pypdf,bibtexparser,pypdfium2,PIL,platformdirs'],capture_output=True)
    if check.returncode:
        print('首次启动需要联网下载运行依赖；此过程不调用模型API。',flush=True)
        subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'requirements.txt')],check=True)
    return subprocess.call([str(python),str(ROOT/'launcher.py'),*sys.argv[1:]],cwd=ROOT)

if __name__=='__main__':
    try: sys.exit(main())
    except (OSError,RuntimeError,subprocess.CalledProcessError) as e:
        print('启动失败：'+str(e),file=sys.stderr);sys.exit(1)
