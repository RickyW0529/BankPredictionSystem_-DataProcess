#!/usr/bin/env bash

# 自动切换到脚本所在目录
cd "$(dirname "$0")"

echo "=========================================="
echo "  停止银行预测数据处理系统"
echo "=========================================="
echo ""

# 查找 Streamlit 进程
PIDS=$(pgrep -f "streamlit run app.py" 2>/dev/null || true)

if [ -z "$PIDS" ]; then
    echo "未检测到运行中的 Streamlit 进程。"
    exit 0
fi

echo "检测到以下 Streamlit 进程:"
echo "$PIDS" | while read -r pid; do
    ps -p "$pid" -o pid,comm,args 2>/dev/null | tail -n 1
done

echo ""
echo "正在终止进程..."
echo "$PIDS" | xargs -r kill -TERM 2>/dev/null || true

sleep 2

# 检查是否还有残留
REMAINING=$(pgrep -f "streamlit run app.py" 2>/dev/null || true)
if [ -n "$REMAINING" ]; then
    echo "强制终止残留进程..."
    echo "$REMAINING" | xargs -r kill -KILL 2>/dev/null || true
fi

echo "已停止。"
