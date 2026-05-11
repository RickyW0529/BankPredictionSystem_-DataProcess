#!/usr/bin/env bash
set -e

echo "=========================================="
echo "银行预测数据处理系统"
echo "=========================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 python3，请先安装 Python 3.9 或更高版本。"
    exit 1
fi

echo "[1/2] 检查依赖..."
python3 -m pip install -q -r requirements.txt

echo "[2/2] 启动前端..."
python3 -m streamlit run app.py
