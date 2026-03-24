import argparse
import os
import signal
import sys
from pathlib import Path

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

BOOTSTRAP_ROOT = Path(__file__).resolve().parents[1]
if str(BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

from common.runtime import data_root, resource_path
from common.security import create_server_ssl_context
from common.tray import AppTrayController
from common.defaults import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from common.app_meta import format_window_title

from Server.src.core.auth import UserStore
from Server.src.core.file_manager import FileStorage
from Server.src.core.settings_store import ServerSettingsStore
from Server.src.core.server import TransferServer
from Server.src.ui.server_console import ServerDashboard


def parse_args():
    parser = argparse.ArgumentParser(description="TCP 文件传输服务端")
    parser.add_argument("--headless", action="store_true", help="以无界面模式运行，适合 systemd")
    parser.add_argument("--host", default=DEFAULT_SERVER_HOST, help=f"监听地址，默认 {DEFAULT_SERVER_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT, help=f"监听端口，默认 {DEFAULT_SERVER_PORT}")
    parser.add_argument("--data-dir", default="", help="自定义数据目录，默认使用程序旁的 server_data")
    return parser.parse_args()


def build_server(app_data_root):
    user_store = UserStore(app_data_root / "users.json", app_data_root / "storage")
    file_storage = FileStorage(app_data_root / "storage")
    ssl_context = create_server_ssl_context(app_data_root)
    return TransferServer(user_store, file_storage, ssl_context=ssl_context)


def resolve_data_dir(custom_data_dir):
    if custom_data_dir:
        return Path(custom_data_dir).expanduser().resolve()
    return data_root("server_data")


def _x11_socket_exists(display_text):
    value = (display_text or "").strip()
    if not value:
        return False
    if ":" not in value:
        return True
    host_part, screen_part = value.split(":", 1)
    if host_part and host_part not in {"localhost", "unix"}:
        return True
    display_number = screen_part.split(".", 1)[0]
    if not display_number.isdigit():
        return False
    return Path(f"/tmp/.X11-unix/X{display_number}").exists()


def detect_gui_issue():
    wayland_display = os.environ.get("WAYLAND_DISPLAY", "").strip()
    if wayland_display:
        runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", ""))
        if runtime_dir and (runtime_dir / wayland_display).exists():
            return ""
        return f"WAYLAND_DISPLAY={wayland_display} 不可用"

    display = os.environ.get("DISPLAY", "").strip()
    if not display:
        return "未检测到 DISPLAY/WAYLAND_DISPLAY"
    if not _x11_socket_exists(display):
        return f"DISPLAY={display} 不可用"
    return ""


def run_headless(server, host, port):
    app = QCoreApplication(sys.argv)
    server.log_message.connect(print)
    server.start(host, port)

    def shutdown(*_args):
        server.stop()
        app.quit()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    return app.exec_()


def main():
    args = parse_args()
    app_data_root = resolve_data_dir(args.data_dir)
    app_data_root.mkdir(parents=True, exist_ok=True)
    server = build_server(app_data_root)
    settings_store = ServerSettingsStore(app_data_root / "settings.json")
    if args.headless:
        return run_headless(server, args.host, args.port)

    gui_issue = detect_gui_issue()
    if gui_issue:
        print(
            f"[tcpTransGUI] 图形界面不可用：{gui_issue}，已自动切换为无界面模式。"
            " 如需 GUI，请在桌面会话中运行并确保 DISPLAY 或 WAYLAND_DISPLAY 正确。",
            file=sys.stderr,
        )
        return run_headless(server, args.host, args.port)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    icon_path = resource_path("assets", "branding", "app_icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = ServerDashboard(server, settings_store)
    if args.host != DEFAULT_SERVER_HOST:
        window.host_input.setText(args.host)
    if args.port != DEFAULT_SERVER_PORT:
        window.port_input.setValue(args.port)
    window.show()
    tray_controller = AppTrayController(app, window, format_window_title("TCP 传输服务端"), app.windowIcon(), start_hidden=True)
    app._tray_controller = tray_controller
    if not tray_controller.available:
        app.setQuitOnLastWindowClosed(True)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
