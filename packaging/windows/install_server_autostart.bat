@echo off
setlocal

set "BASE_DIR=%~dp0"
set "SERVER_BIN=%BASE_DIR%server\tcpTransServer.exe"
if "%LOCALAPPDATA%"=="" (
    set "DATA_DIR=%USERPROFILE%\AppData\Local\TCPTransGUI\server_data"
) else (
    set "DATA_DIR=%LOCALAPPDATA%\TCPTransGUI\server_data"
)
set "TASK_NAME=TCPTransGUI Server"

if not exist "%SERVER_BIN%" (
    echo 未找到服务端程序：%SERVER_BIN%
    exit /b 1
)

if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"

set "SERVER_CMD=\"%SERVER_BIN%\" --headless --host 0.0.0.0 --port 9999 --data-dir \"%DATA_DIR%\""
schtasks /Create /F /TN "%TASK_NAME%" /SC ONLOGON /RL HIGHEST /RU "%USERNAME%" /TR "%SERVER_CMD%"
if errorlevel 1 (
    echo 开机自启动任务创建失败，请使用管理员权限运行。
    exit /b 1
)

echo 已创建 Windows 服务端开机自启动任务：%TASK_NAME%
