import sys
from pathlib import Path

from PyQt5.QtCore import QObject, QProcess, Qt, QTimer
from PyQt5.QtWidgets import QAction, QApplication, QMenu, QSystemTrayIcon


class AppTrayController(QObject):
    def __init__(self, app, window, title, icon, start_hidden=False):
        super().__init__(window)
        self.app = app
        self.window = window
        self.title = title
        self.start_hidden = start_hidden
        self._restart_requested = False
        self._tray = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        tray = QSystemTrayIcon(icon, window)
        tray.setToolTip(title)

        menu = QMenu()
        home_action = QAction("主页面", menu)
        restart_action = QAction("重启", menu)
        exit_action = QAction("退出", menu)
        home_action.triggered.connect(self.show_from_tray)
        restart_action.triggered.connect(self.restart_application)
        exit_action.triggered.connect(self.exit_application)
        menu.addAction(home_action)
        menu.addSeparator()
        menu.addAction(restart_action)
        menu.addAction(exit_action)

        tray.setContextMenu(menu)
        tray.activated.connect(self.on_tray_activated)
        tray.show()
        self._tray = tray

        if hasattr(self.window, "set_tray_mode_enabled"):
            self.window.set_tray_mode_enabled(True)

        if self.start_hidden:
            QTimer.singleShot(0, self.hide_to_tray)

    @property
    def available(self):
        return self._tray is not None

    def on_tray_activated(self, reason):
        if reason in {QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick}:
            if self.window.isVisible() and not self.window.isMinimized():
                self.hide_to_tray()
            else:
                self.show_from_tray()

    def hide_to_tray(self):
        self.window.hide()

    def show_from_tray(self):
        self.window.show()
        self.window.setWindowState(self.window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.window.raise_()
        self.window.activateWindow()

    def exit_application(self):
        self._restart_requested = False
        self._close_window()

    def restart_application(self):
        self._restart_requested = True
        self._close_window()

    def _close_window(self):
        if hasattr(self.window, "request_tray_exit"):
            self.window.request_tray_exit()
        else:
            self.window.close()
        QApplication.processEvents()
        QTimer.singleShot(0, self.finalize_after_close)

    def finalize_after_close(self):
        if self._restart_requested:
            self._start_detached_copy()
        self.app.quit()

    def _start_detached_copy(self):
        program = sys.executable
        if getattr(sys, "frozen", False):
            arguments = sys.argv[1:]
        else:
            arguments = sys.argv
        QProcess.startDetached(program, arguments, str(Path.cwd()))
