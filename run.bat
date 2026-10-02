@echo off
rem 双击启动（无控制台窗口）。第一次使用请先运行 install.bat。
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo 还没有安装依赖，请先双击 install.bat。
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m worklog
