@echo off
setlocal enabledelayedexpansion

set PROJECT_ROOT=%~dp0..
set APP_VERSION=%TCPTRANSGUI_VERSION%
if "%APP_VERSION%"=="" set APP_VERSION=1.1.0

cd /d %PROJECT_ROOT%

if not exist release\windows\client\tcpTransClient.exe (
    call "%PROJECT_ROOT%\scripts\build_windows.bat"
)

if not exist release\windows\server\tcpTransServer.exe (
    call "%PROJECT_ROOT%\scripts\build_windows.bat"
)

set ISCC_EXE=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe

if "%ISCC_EXE%"=="" (
    echo 未找到 Inno Setup 6，请先安装后再执行本脚本。
    exit /b 1
)

if not exist release\windows\installer mkdir release\windows\installer

"%ISCC_EXE%" /DMyAppVersion=%APP_VERSION% packaging\windows\tcpTransGUI-client.iss
if errorlevel 1 exit /b 1

"%ISCC_EXE%" /DMyAppVersion=%APP_VERSION% packaging\windows\tcpTransGUI-server.iss
if errorlevel 1 exit /b 1

echo Windows client/server installers ready in: %PROJECT_ROOT%\release\windows\installer
