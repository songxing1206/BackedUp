#!/bin/zsh
cd "${0:A:h}"
if [[ -x .venv/bin/python ]]; then
  runner=.venv/bin/python
elif [[ -x ../竞品体验/.venv/bin/python ]]; then
  runner=../竞品体验/.venv/bin/python
else
  echo '未找到运行环境，请按 README 安装 Python 与依赖。'
  read
  exit 1
fi
"$runner" launcher.py --diagnose
echo '诊断不读取论文或 API Key，不调用模型。按回车关闭。'
read
