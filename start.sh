#!/usr/bin/env bash
set -e

echo "=========================================="
echo "  银行预测数据处理系统"
echo "=========================================="
echo ""

# 1. 检测 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 python3，请先安装 Python 3.10 或更高版本。"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[1/5] 检测到 Python $PYTHON_VERSION"

# 2. 创建虚拟环境
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[2/5] 创建虚拟环境 ($VENV_DIR)..."
    python3 -m venv "$VENV_DIR"
else
    echo "[2/5] 虚拟环境已存在"
fi

# 3. 检查关键目录
mkdir -p output .ifind_cache .tushare_cache .akshare_cache
echo "[3/5] 关键目录检查完成"

# 4. 激活虚拟环境并安装依赖
echo "[4/5] 安装/更新依赖..."
source "$VENV_DIR/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

# 5. 启动 Streamlit
echo "[5/5] 启动 Streamlit..."
echo ""
python -m streamlit run app.py
