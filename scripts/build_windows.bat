@echo off
setlocal enabledelayedexpansion

set PROJECT_ROOT=%~dp0..
cd /d %PROJECT_ROOT%

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python scripts\generate_branding_assets.py
python scripts\clean_artifacts.py

pyinstaller --noconfirm packaging\client.spec
pyinstaller --noconfirm packaging\server.spec

mkdir release\windows\client
mkdir release\windows\server
copy dist\tcpTransClient.exe release\windows\client\tcpTransClient.exe >nul
copy dist\tcpTransServer.exe release\windows\server\tcpTransServer.exe >nul
copy README.md release\windows\client\README.md >nul
copy README.md release\windows\server\README.md >nul
copy packaging\windows\install_server_autostart.bat release\windows\server\install_server_autostart.bat >nul
copy packaging\windows\remove_server_autostart.bat release\windows\server\remove_server_autostart.bat >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'release\\windows\\client\\*' -DestinationPath 'release\\tcptransgui-client-windows-portable.zip' -Force" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'release\\windows\\server\\*' -DestinationPath 'release\\tcptransgui-server-windows-portable.zip' -Force" >nul
python scripts\clean_artifacts.py --keep-release

echo Windows release ready in: %PROJECT_ROOT%\release\windows
