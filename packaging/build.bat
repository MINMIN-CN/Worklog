@echo off
rem 一键构建 Windows 安装包：图标 -> PyInstaller -> Inno Setup
rem 产物：dist\installer\WorkLog-Setup-0.5.0.exe
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo 请先运行 install.bat 安装依赖。
    pause
    exit /b 1
)

echo [1/4] 生成图标...
".venv\Scripts\python.exe" packaging\make_icon.py || goto :err

echo [2/4] 清理旧产物...
if exist "dist\WorkLog" rmdir /s /q "dist\WorkLog"
if exist "dist\installer" rmdir /s /q "dist\installer"

echo [3/4] PyInstaller 打包（需要几分钟）...
".venv\Scripts\python.exe" -m PyInstaller packaging\worklog.spec --noconfirm --clean || goto :err

echo [4/4] Inno Setup 生成安装包...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo 未找到 Inno Setup，请先安装：winget install JRSoftware.InnoSetup
    goto :err
)

set "LANGDEF="
if exist "packaging\ChineseSimplified.isl" set "LANGDEF=/DUseChinese=1"

"%ISCC%" %LANGDEF% packaging\installer.iss || goto :err

echo.
echo 构建完成！安装包：
dir /b "dist\installer"
echo 位置：%~dp0dist\installer
pause
exit /b 0

:err
echo.
echo 构建失败，请查看上面的错误信息。
pause
exit /b 1
