@echo off
rem 首次安装：创建虚拟环境并安装依赖。
chcp 65001 >nul
cd /d "%~dp0"
echo 正在安装依赖（第一次需要几分钟）...
uv sync
if errorlevel 1 (
    echo.
    echo 安装失败：请确认已安装 uv（https://docs.astral.sh/uv/）并且网络可用。
    pause
    exit /b 1
)
echo.
echo 安装完成。双击 run.bat 启动。
pause
