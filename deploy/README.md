# 银行预测数据处理系统 - 本地部署包

## 系统要求

- Python 3.10 或更高版本
- 网络连接（用于下载依赖）

## 快速开始

### macOS / Linux

```bash
cd deploy
chmod +x start.sh stop.sh
./start.sh
```

### Windows

双击运行 `start.bat`

### 麒麟系统

```bash
cd deploy
chmod +x start_kylin.sh stop.sh
./start_kylin.sh
```

## 脚本说明

### 启动脚本流程

1. **检测 Python** - 检查系统是否已安装 Python 3.10+
2. **创建虚拟环境** - 在项目目录下自动创建 `.venv`（如不存在）
3. **检查关键目录** - 自动创建 `output/`、`.ifind_cache/`、`.tushare_cache/`、`.akshare_cache/`
4. **安装依赖** - 从 `requirements.txt` 安装/更新所有依赖（显示实时下载进度）
5. **启动 Streamlit** - 自动打开浏览器访问 `http://localhost:8501`

### 停止脚本

```bash
# macOS / Linux / 麒麟
./stop.sh

# Windows
双击 stop.bat
```

## 首次启动

首次运行会自动下载并安装所有依赖，根据网络状况可能需要 **2~5 分钟**。请耐心等待，终端会显示每个包的下载和安装进度。

## 常见问题

### Q: 提示 "未检测到 python3"
A: 请先安装 Python 3.10+，安装时勾选 "Add Python to PATH"。

### Q: 依赖安装失败
A: 检查网络连接。麒麟系统会自动切换至清华镜像源重试。

### Q: Streamlit 启动后浏览器没有自动打开
A: 手动访问 http://localhost:8501

### Q: 如何更新依赖
A: 直接重新运行启动脚本即可，会自动检测并更新。

## 目录结构

```
deploy/
├── app.py                      # Streamlit 前端入口
├── main.py                     # 命令行流水线入口
├── requirements.txt            # Python 依赖列表
├── bank_pipeline/              # 核心处理模块
├── tests/                      # 测试用例
├── start.sh                    # macOS / Linux 启动
├── start.bat                   # Windows 启动
├── start_kylin.sh              # 麒麟系统启动
├── stop.sh                     # macOS / Linux / 麒麟 停止
└── stop.bat                    # Windows 停止
```
