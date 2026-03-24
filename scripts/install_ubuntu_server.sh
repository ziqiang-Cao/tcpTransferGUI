#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="tcptransgui-server.service"
ENV_FILE="/etc/default/tcptransgui-server"
OVERRIDE_DIR="/etc/systemd/system/${SERVICE_NAME}.d"
OVERRIDE_FILE="${OVERRIDE_DIR}/override.conf"

if [[ "${EUID}" -ne 0 ]]; then
    echo "请使用 sudo 运行此脚本。"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -x "${SCRIPT_DIR}/tcpTransServer" ]]; then
    SERVER_BIN="${SCRIPT_DIR}/tcpTransServer"
    CLIENT_BIN=""
    ASSET_DIR="${SCRIPT_DIR}/packaging/ubuntu"
    BRANDING_DIR="${SCRIPT_DIR}"
elif [[ -x "${SCRIPT_DIR}/server/tcpTransServer" ]]; then
    SERVER_BIN="${SCRIPT_DIR}/server/tcpTransServer"
    CLIENT_BIN="${SCRIPT_DIR}/client/tcpTransClient"
    ASSET_DIR="${SCRIPT_DIR}/packaging/ubuntu"
    BRANDING_DIR="${SCRIPT_DIR}/assets/branding"
else
    SERVER_BIN="${PROJECT_ROOT}/release/ubuntu/server/tcpTransServer"
    CLIENT_BIN="${PROJECT_ROOT}/release/ubuntu/client/tcpTransClient"
    ASSET_DIR="${PROJECT_ROOT}/packaging/ubuntu"
    BRANDING_DIR="${PROJECT_ROOT}/assets/branding"
fi

if [[ ! -x "${SERVER_BIN}" ]]; then
    echo "未找到已构建的 Ubuntu 服务端可执行文件：${SERVER_BIN}"
    echo "请先运行 bash scripts/build_ubuntu.sh"
    exit 1
fi

detect_service_user() {
    local candidate=""
    if [[ -n "${TCPTRANSGUI_SERVICE_USER:-}" ]] && id "${TCPTRANSGUI_SERVICE_USER}" >/dev/null 2>&1; then
        echo "${TCPTRANSGUI_SERVICE_USER}"
        return 0
    fi
    if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]] && id "${SUDO_USER}" >/dev/null 2>&1; then
        echo "${SUDO_USER}"
        return 0
    fi
    if candidate="$(logname 2>/dev/null)" && [[ -n "${candidate}" && "${candidate}" != "root" ]] && id "${candidate}" >/dev/null 2>&1; then
        echo "${candidate}"
        return 0
    fi
    candidate="$(awk -F: '$3 >= 1000 && $1 != "nobody" && $7 !~ /(nologin|false)$/ { print $1; exit }' /etc/passwd)"
    if [[ -n "${candidate}" ]] && id "${candidate}" >/dev/null 2>&1; then
        echo "${candidate}"
        return 0
    fi
    echo "root"
}

parse_env_value() {
    local key="$1"
    local file="$2"
    [[ -f "${file}" ]] || return 1
    awk -F= -v search_key="${key}" '
        $1 == search_key {
            sub(/^[[:space:]]+/, "", $2)
            sub(/[[:space:]]+$/, "", $2)
            gsub(/^"/, "", $2)
            gsub(/"$/, "", $2)
            print $2
            exit
        }
    ' "${file}"
}

SERVICE_USER="$(detect_service_user)"
SERVICE_GROUP="$(id -gn "${SERVICE_USER}" 2>/dev/null || echo "${SERVICE_USER}")"
SERVICE_HOME="$(getent passwd "${SERVICE_USER}" | cut -d: -f6)"
if [[ -z "${SERVICE_HOME}" ]]; then
    SERVICE_HOME="$(eval echo "~${SERVICE_USER}")"
fi
SERVICE_DATA_ROOT="${SERVICE_HOME}/.local/share/TCPTransGUI"
DEFAULT_DATA_DIR="${SERVICE_HOME}/.local/share/TCPTransGUI/server_data"

HOST_VALUE="$(parse_env_value TCPTRANSGUI_HOST "${ENV_FILE}" || true)"
PORT_VALUE="$(parse_env_value TCPTRANSGUI_PORT "${ENV_FILE}" || true)"
DATA_DIR_VALUE="$(parse_env_value TCPTRANSGUI_DATA_DIR "${ENV_FILE}" || true)"
HOST_VALUE="${HOST_VALUE:-0.0.0.0}"
PORT_VALUE="${PORT_VALUE:-9999}"
if [[ -z "${DATA_DIR_VALUE}" || "${DATA_DIR_VALUE}" == "/var/lib/tcptransgui/server_data" ]]; then
    DATA_DIR_VALUE="${DEFAULT_DATA_DIR}"
fi

install -d /opt/tcptransgui/client /opt/tcptransgui/server /usr/share/applications "${OVERRIDE_DIR}"
if [[ "${DATA_DIR_VALUE}" == "${SERVICE_DATA_ROOT}"* ]]; then
    install -d "${SERVICE_DATA_ROOT}" "${DATA_DIR_VALUE}"
else
    install -d "${DATA_DIR_VALUE}"
fi

install -m 755 "${SERVER_BIN}" /opt/tcptransgui/server/tcpTransServer
if [[ -x "${CLIENT_BIN}" ]]; then
    install -m 755 "${CLIENT_BIN}" /opt/tcptransgui/client/tcpTransClient
fi

install -m 644 "${ASSET_DIR}/tcptransgui-server.service" /etc/systemd/system/tcptransgui-server.service
cat > "${ENV_FILE}" <<EOF
TCPTRANSGUI_HOST=${HOST_VALUE}
TCPTRANSGUI_PORT=${PORT_VALUE}
TCPTRANSGUI_DATA_DIR=${DATA_DIR_VALUE}
EOF
cat > "${OVERRIDE_FILE}" <<EOF
[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
EOF

install -m 644 "${ASSET_DIR}/tcptransgui-server.desktop" /usr/share/applications/tcptransgui-server.desktop
if [[ -x "${CLIENT_BIN}" && -f "${ASSET_DIR}/tcptransgui-client.desktop" ]]; then
    install -m 644 "${ASSET_DIR}/tcptransgui-client.desktop" /usr/share/applications/tcptransgui-client.desktop
fi
if [[ -f "${BRANDING_DIR}/app_icon.png" ]]; then
    install -d /usr/share/pixmaps
    install -m 644 "${BRANDING_DIR}/app_icon.png" /usr/share/pixmaps/tcptransgui-server.png
    if [[ -x "${CLIENT_BIN}" ]]; then
        install -m 644 "${BRANDING_DIR}/app_icon.png" /usr/share/pixmaps/tcptransgui-client.png
    fi
fi

if [[ "${DATA_DIR_VALUE}" == "${SERVICE_DATA_ROOT}"* ]]; then
    chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${SERVICE_DATA_ROOT}"
else
    chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${DATA_DIR_VALUE}"
fi

systemctl daemon-reload
systemctl stop "${SERVICE_NAME}" >/dev/null 2>&1 || true
systemctl disable "${SERVICE_NAME}" >/dev/null 2>&1 || true

echo "安装完成。"
echo "服务名称: tcptransgui-server"
echo "查看状态: systemctl status tcptransgui-server"
echo "环境配置: ${ENV_FILE}"
echo "systemd 覆盖配置: ${OVERRIDE_FILE}"
echo "服务运行用户: ${SERVICE_USER}:${SERVICE_GROUP}"
echo "数据目录: ${DATA_DIR_VALUE}"
echo "默认不会自动启用 systemd 服务，可在服务端主界面中直接控制 enable / disable。"
