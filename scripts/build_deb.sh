#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/project_root.sh"
PROJECT_ROOT="$(tcptransgui_resolve_project_root "${BASH_SOURCE[0]}")"
cd "$PROJECT_ROOT"

VERSION="${TCPTRANSGUI_VERSION:-1.1.0}"
ARCH="${TCPTRANSGUI_ARCH:-$(dpkg --print-architecture)}"
WORK_ROOT="$PROJECT_ROOT/release/deb/work"
OUTPUT_DIR="$PROJECT_ROOT/release/deb"

bash "$PROJECT_ROOT/scripts/build_ubuntu.sh"

build_client_package() {
    local pkg_name="tcptransgui-client"
    local pkg_dir="$WORK_ROOT/${pkg_name}_${VERSION}_${ARCH}"
    local output_file="$OUTPUT_DIR/${pkg_name}_${VERSION}_${ARCH}.deb"

    rm -rf "$pkg_dir"
    mkdir -p \
        "$pkg_dir/DEBIAN" \
        "$pkg_dir/opt/tcptransgui/client" \
        "$pkg_dir/usr/bin" \
        "$pkg_dir/usr/share/applications" \
        "$pkg_dir/usr/share/pixmaps" \
        "$pkg_dir/usr/share/doc/${pkg_name}"

    install -m 755 "$PROJECT_ROOT/release/ubuntu/client/tcpTransClient" "$pkg_dir/opt/tcptransgui/client/tcpTransClient"
    install -m 644 "$PROJECT_ROOT/packaging/ubuntu/tcptransgui-client.desktop" "$pkg_dir/usr/share/applications/tcptransgui-client.desktop"
    install -m 644 "$PROJECT_ROOT/assets/branding/app_icon.png" "$pkg_dir/usr/share/pixmaps/tcptransgui-client.png"
    install -m 644 "$PROJECT_ROOT/README.md" "$pkg_dir/usr/share/doc/${pkg_name}/README.md"

    cat > "$pkg_dir/DEBIAN/control" <<EOF
Package: ${pkg_name}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: TCPTransGUI Packager <packager@localhost>
Depends: desktop-file-utils
Description: TCPTransGUI desktop client
 Desktop client for secure TCP file transfer with resumable multi-thread upload
 and download, persistent transfer task recovery and TLS connection protection.
EOF

    cat > "$pkg_dir/usr/bin/tcptransgui-client" <<'EOF'
#!/bin/sh
exec /opt/tcptransgui/client/tcpTransClient "$@"
EOF
    chmod 755 "$pkg_dir/usr/bin/tcptransgui-client"

    install -m 755 "$PROJECT_ROOT/packaging/debian/client.postinst" "$pkg_dir/DEBIAN/postinst"
    install -m 755 "$PROJECT_ROOT/packaging/debian/client.postrm" "$pkg_dir/DEBIAN/postrm"

    dpkg-deb --build --root-owner-group "$pkg_dir" "$output_file"
}

build_server_package() {
    local pkg_name="tcptransgui-server"
    local pkg_dir="$WORK_ROOT/${pkg_name}_${VERSION}_${ARCH}"
    local output_file="$OUTPUT_DIR/${pkg_name}_${VERSION}_${ARCH}.deb"

    rm -rf "$pkg_dir"
    mkdir -p \
        "$pkg_dir/DEBIAN" \
        "$pkg_dir/opt/tcptransgui/server" \
        "$pkg_dir/etc/default" \
        "$pkg_dir/lib/systemd/system" \
        "$pkg_dir/usr/bin" \
        "$pkg_dir/usr/share/applications" \
        "$pkg_dir/usr/share/pixmaps" \
        "$pkg_dir/usr/share/doc/${pkg_name}"

    install -m 755 "$PROJECT_ROOT/release/ubuntu/server/tcpTransServer" "$pkg_dir/opt/tcptransgui/server/tcpTransServer"
    install -m 644 "$PROJECT_ROOT/packaging/ubuntu/tcptransgui-server.env" "$pkg_dir/etc/default/tcptransgui-server"
    install -m 644 "$PROJECT_ROOT/packaging/ubuntu/tcptransgui-server.service" "$pkg_dir/lib/systemd/system/tcptransgui-server.service"
    install -m 644 "$PROJECT_ROOT/packaging/ubuntu/tcptransgui-server.desktop" "$pkg_dir/usr/share/applications/tcptransgui-server.desktop"
    install -m 644 "$PROJECT_ROOT/assets/branding/app_icon.png" "$pkg_dir/usr/share/pixmaps/tcptransgui-server.png"
    install -m 644 "$PROJECT_ROOT/README.md" "$pkg_dir/usr/share/doc/${pkg_name}/README.md"

    cat > "$pkg_dir/DEBIAN/control" <<EOF
Package: ${pkg_name}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: TCPTransGUI Packager <packager@localhost>
Depends: adduser, systemd
Description: TCPTransGUI headless server
 GUI-capable TCP file transfer server with local user management, TLS transport,
 resumable transfers, expiring temporary users and systemd auto-start support.
EOF

    cat > "$pkg_dir/usr/bin/tcptransgui-server" <<'EOF'
#!/bin/sh
exec /opt/tcptransgui/server/tcpTransServer "$@"
EOF
    chmod 755 "$pkg_dir/usr/bin/tcptransgui-server"

    install -m 755 "$PROJECT_ROOT/packaging/debian/server.postinst" "$pkg_dir/DEBIAN/postinst"
    install -m 755 "$PROJECT_ROOT/packaging/debian/server.prerm" "$pkg_dir/DEBIAN/prerm"
    install -m 755 "$PROJECT_ROOT/packaging/debian/server.postrm" "$pkg_dir/DEBIAN/postrm"

    dpkg-deb --build --root-owner-group "$pkg_dir" "$output_file"
}

mkdir -p "$OUTPUT_DIR"
rm -rf "$WORK_ROOT"

build_client_package
build_server_package

rm -rf "$WORK_ROOT"
python3 "$PROJECT_ROOT/scripts/clean_artifacts.py" --keep-release

echo "Debian client package ready in: $OUTPUT_DIR/tcptransgui-client_${VERSION}_${ARCH}.deb"
echo "Debian server package ready in: $OUTPUT_DIR/tcptransgui-server_${VERSION}_${ARCH}.deb"
