@echo off
setlocal

set "TASK_NAME=TCPTransGUI Server"
schtasks /Delete /F /TN "%TASK_NAME%"
if errorlevel 1 (
    echo 删除开机自启动任务失败，或任务不存在：%TASK_NAME%
    exit /b 1
)

echo 已删除 Windows 服务端开机自启动任务：%TASK_NAME%
