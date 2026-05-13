@echo off
chcp 65001 >nul
echo ==========================================
echo   银行预测数据处理系统
echo ==========================================
echo.

:: 1. 检测 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10 或更高版本。
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%a in ('python -c "import sys; print(f\'{sys.version_info.major}.{sys.version_info.minor}\')"') do set PYVER=%%a
echo [1/4] 检测到 Python %PYVER%

:: 2. 创建虚拟环境
set VENV_DIR=.venv
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [2/4] 创建虚拟环境 (%VENV_DIR%)...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败。
        pause
        exit /b 1
    )
) else (
    echo [2/4] 虚拟环境已存在
)

:: 3. 激活虚拟环境并安装依赖
echo [3/4] 安装/更新依赖...
call "%VENV_DIR%\Scripts\activate.bat"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接。
    pause
    exit /b 1
)

:: 4. 启动 Streamlit
echo [4/4] 启动 Streamlit...
echo.
python -m streamlit run app.py

pause
