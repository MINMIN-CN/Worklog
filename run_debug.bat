@echo off
rem 控制台模式启动，能看到日志和报错，排查问题用。
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m worklog
) else (
    uv run python -m worklog
)
if errorlevel 1 (
    echo.
    echo 启动失败，请把上面的错误信息发给开发者。
    pause
)
