#!/usr/bin/env bash
set -e

# 自动切换到脚本所在目录
cd "$(dirname "$0")"

echo "=========================================="
echo "  银行预测数据处理系统 (麒麟版)"
echo "=========================================="
echo ""

# 1. 检测 Python（麒麟系统常见路径）
PYTHON_CMD=""
for cmd in python3 python3.10 python3.11 python3.12 /usr/bin/python3 /usr/local/bin/python3; do
    if command -v "$cmd" &> /dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "[错误] 未检测到 python3，请先安装 Python 3.10 或更高版本。"
    echo "  麒麟系统安装命令: sudo apt install python3 python3-venv python3-pip -y"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[1/5] 检测到 Python $PYTHON_VERSION (命令: $PYTHON_CMD)"

# 2. 创建虚拟环境
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[2/5] 创建虚拟环境 ($VENV_DIR)..."
    $PYTHON_CMD -m venv "$VENV_DIR"
else
    echo "[2/5] 虚拟环境已存在"
fi

# 3. 检查关键目录
mkdir -p output .ifind_cache .tushare_cache .akshare_cache
echo "[3/5] 关键目录检查完成"

# 4. 激活虚拟环境并安装依赖（显示实时进度，优先国内镜像）
echo "[4/5] 安装/更新依赖..."
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip || true

# 尝试默认源，失败则切换国内镜像
echo "  尝试 PyPI 官方源..."
if ! python -m pip install -r requirements.txt 2>/dev/null; then
    echo "  官方源失败，切换至清华镜像..."
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple || {
        echo "[错误] 依赖安装失败，请检查网络连接或手动配置 pip 镜像。"
        exit 1
    }
fi

# 5. 启动 Streamlit
echo "[5/5] 启动 Streamlit..."
echo ""
python -m streamlit run app.py
