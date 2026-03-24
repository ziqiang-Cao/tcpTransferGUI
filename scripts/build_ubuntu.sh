#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/project_root.sh"
PROJECT_ROOT="$(tcptransgui_resolve_project_root "${BASH_SOURCE[0]}")"
cd "$PROJECT_ROOT"

ARCH="${TCPTRANSGUI_ARCH:-$(dpkg --print-architecture)}"
CLIENT_PORTABLE_DIR="$PROJECT_ROOT/release/ubuntu/client"
SERVER_PORTABLE_DIR="$PROJECT_ROOT/release/ubuntu/server"

python3 scripts/check_build_env.py
if [ "${TCPTRANSGUI_SKIP_PIP:-0}" != "1" ]; then
    python3 -m pip install --upgrade pip
    python3 -m pip install -r requirements.txt pyinstaller
fi
QT_QPA_PLATFORM=offscreen python3 scripts/generate_branding_assets.py
python3 scripts/clean_artifacts.py

pyinstaller --noconfirm packaging/client.spec
pyinstaller --noconfirm packaging/server.spec

mkdir -p "$CLIENT_PORTABLE_DIR" "$SERVER_PORTABLE_DIR/packaging/ubuntu"

install -m 755 dist/tcpTransClient "$CLIENT_PORTABLE_DIR/tcpTransClient"
install -m 755 dist/tcpTransServer "$SERVER_PORTABLE_DIR/tcpTransServer"
install -m 755 scripts/install_ubuntu_server.sh "$SERVER_PORTABLE_DIR/install_ubuntu_server.sh"
install -m 644 assets/branding/app_icon.png "$CLIENT_PORTABLE_DIR/app_icon.png"
install -m 644 assets/branding/app_icon.png "$SERVER_PORTABLE_DIR/app_icon.png"
install -m 644 README.md "$CLIENT_PORTABLE_DIR/README.md"
install -m 644 README.md "$SERVER_PORTABLE_DIR/README.md"
install -m 644 packaging/ubuntu/tcptransgui-server.service "$SERVER_PORTABLE_DIR/packaging/ubuntu/tcptransgui-server.service"
install -m 644 packaging/ubuntu/tcptransgui-server.env "$SERVER_PORTABLE_DIR/packaging/ubuntu/tcptransgui-server.env"
install -m 644 packaging/ubuntu/tcptransgui-server.desktop "$SERVER_PORTABLE_DIR/packaging/ubuntu/tcptransgui-server.desktop"

tar -czf "release/tcptransgui-client-ubuntu-${ARCH}-portable.tar.gz" -C "$CLIENT_PORTABLE_DIR" .
tar -czf "release/tcptransgui-server-ubuntu-${ARCH}-portable.tar.gz" -C "$SERVER_PORTABLE_DIR" .
cp "release/tcptransgui-client-ubuntu-${ARCH}-portable.tar.gz" release/tcptransgui-client-ubuntu-portable.tar.gz
cp "release/tcptransgui-server-ubuntu-${ARCH}-portable.tar.gz" release/tcptransgui-server-ubuntu-portable.tar.gz

python3 scripts/clean_artifacts.py --keep-release

echo "Build architecture: $ARCH"
echo "Ubuntu client release ready in: $CLIENT_PORTABLE_DIR"
echo "Ubuntu server release ready in: $SERVER_PORTABLE_DIR"
