#!/usr/bin/env bash
set -e

# --- 修复 Mac 双击运行时的路径问题 ---
cd "$(dirname "$0")"

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

# 2. 创建/校验虚拟环境
VENV_DIR=".venv"
NEED_CREATE=false
if [ ! -d "$VENV_DIR" ]; then
    NEED_CREATE=true
    echo "[2/5] 虚拟环境不存在，准备创建..."
else
    # 检查虚拟环境中的 Python 版本是否与系统一致
    if [ -f "$VENV_DIR/bin/python" ]; then
        VENV_PY_VER=$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2>/dev/null || echo "unknown")
        if [ "$VENV_PY_VER" != "$PYTHON_VERSION" ]; then
            echo "[2/5] 虚拟环境 Python 版本 ($VENV_PY_VER) 与系统 ($PYTHON_VERSION) 不一致，重新创建..."
            rm -rf "$VENV_DIR"
            NEED_CREATE=true
        else
            echo "[2/5] 虚拟环境已存在且版本一致"
        fi
    else
        echo "[2/5] 虚拟环境损坏，重新创建..."
        rm -rf "$VENV_DIR"
        NEED_CREATE=true
    fi
fi

if [ "$NEED_CREATE" = true ]; then
    python3 -m venv "$VENV_DIR"
    echo "[2/5] 虚拟环境创建完成"
fi

# 3. 检查关键目录
mkdir -p output .ifind_cache .tushare_cache .akshare_cache
echo "[3/5] 关键目录检查完成"

# 4. 激活虚拟环境并安装依赖（显示实时进度）
echo "[4/5] 安装/更新依赖..."
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 5. 启动 Streamlit
echo "[5/5] 启动 Streamlit..."
echo ""
python -m streamlit run app.py