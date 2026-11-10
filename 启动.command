#!/bin/zsh
cd "${0:A:h}"
if command -v python3 >/dev/null 2>&1; then
  python3 bootstrap.py
else
  echo '请先安装 Python 3.10 或更新版本：https://www.python.org/downloads/'
  exit 1
fi
if [[ $? -ne 0 ]]; then
  echo '启动失败，请查看上方原因。按回车关闭。'
  read
fi
