#!/bin/zsh
set -e

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "没有找到 Python 3。请先从 https://www.python.org/downloads/ 安装 Python。"
  read -k 1 "?按任意键关闭…"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "第一次启动：正在创建运行环境…"
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -c "import streamlit, pypdf, openpyxl, docx" >/dev/null 2>&1; then
  echo "第一次启动：正在安装所需组件，请保持网络连接…"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
fi

echo "工具即将打开。关闭本窗口即可停止工具。"
python -m streamlit run app.py
