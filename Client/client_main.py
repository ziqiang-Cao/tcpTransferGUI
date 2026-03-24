import sys
import traceback
from pathlib import Path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

BOOTSTRAP_ROOT = Path(__file__).resolve().parents[1]
if str(BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

from common.runtime import data_root, resource_path
from common.tray import AppTrayController
from common.defaults import DEFAULT_LOCAL_SERVER
from common.app_meta import format_window_title

from Client.src.core.client import FileTransferClient
from Client.src.core.state_store import ClientStateStore
from Client.src.ui.dialogs import show_error
from Client.src.ui.login_dialog import LoginDialog
from Client.src.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    icon_path = resource_path("assets", "branding", "app_icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app_data_root = data_root("client_data")
    state_store = ClientStateStore(app_data_root)
    settings = state_store.load_settings()
    client = FileTransferClient(state_store=state_store)
    dialog = LoginDialog(
        settings.get("last_server", DEFAULT_LOCAL_SERVER),
        "",
    )

    while True:
        if dialog.exec_() != LoginDialog.Accepted:
            return 0
        try:
            credentials = dialog.credentials()
            client.login(
                credentials["server"],
                credentials["username"],
                credentials["password"],
            )
            state_store.save_settings(
                last_server=client.server_text,
                thread_count=settings.get("thread_count", 4),
            )
            break
        except Exception as exc:
            dialog.show_error(str(exc))

    try:
        window = MainWindow(client, state_store)
        window.show()
        tray_controller = AppTrayController(app, window, format_window_title("TCP 文件传输客户端"), app.windowIcon())
        app._tray_controller = tray_controller
        if not tray_controller.available:
            app.setQuitOnLastWindowClosed(True)
    except Exception as exc:
        show_error(
            None,
            format_window_title("客户端启动失败"),
            f"登录成功，但主界面初始化失败：\n{exc}\n\n详细堆栈已输出到终端。",
        )
        traceback.print_exc()
        return 1
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
