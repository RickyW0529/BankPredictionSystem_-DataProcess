@echo off
chcp 65001 >nul

:: 自动切换到脚本所在目录
cd /d "%~dp0"

echo ==========================================
echo   停止银行预测数据处理系统
echo ==========================================
echo.

:: 查找占用 8501 端口的进程（Streamlit 默认端口）
echo 正在查找 Streamlit 进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8501') do (
    set PID=%%a
    goto :found
)

:: 备选：查找 streamlit 命令行
tasklist /FI "IMAGENAME eq python.exe" /V | findstr /I "streamlit" >nul
if errorlevel 1 (
    echo 未检测到运行中的 Streamlit 进程。
    pause
    exit /b 0
)

:: 通过 wmic 查找 streamlit 进程
for /f "tokens=2 delims=," %%a in ('wmic process where "CommandLine like '%%streamlit run app.py%%'" get ProcessId /format:csv ^| findstr "[0-9]"') do (
    set PID=%%a
    goto :found
)

echo 未检测到运行中的 Streamlit 进程。
pause
exit /b 0

:found
echo 发现进程 PID: %PID%
taskkill /PID %PID% /F /T >nul 2>&1
if errorlevel 1 (
    echo 终止失败，请手动结束进程。
) else (
    echo 已停止。
)
pause
