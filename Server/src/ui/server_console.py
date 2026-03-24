import errno
import shutil
import socket
import subprocess
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from common.defaults import (
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    LEGACY_PRIVILEGED_DEFAULT_PORT,
)
from common.app_meta import format_window_title


SYSTEMD_SERVICE_NAME = "tcptransgui-server.service"
SYSTEMD_ENV_FILE = Path("/etc/default/tcptransgui-server")
DEFAULT_DEPLOY_BADGE_TEXT = "Ubuntu 可作为开机自启服务运行"


def format_bytes(value):
    size = float(value)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class CreateUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(format_window_title("新增用户"))
        self.setModal(True)
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("创建账号")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #173042;")
        layout.addWidget(title)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("请输入密码")
        self.role_combo = QComboBox()
        self.role_combo.addItems(["user", "admin"])
        self.temp_checkbox = QCheckBox("创建临时用户")
        self.temp_checkbox.setChecked(False)
        self.expire_days_spin = QSpinBox()
        self.expire_days_spin.setRange(1, 3650)
        self.expire_days_spin.setValue(1)
        self.expire_days_spin.setSuffix(" 天")
        self.expire_days_spin.setEnabled(False)
        self.expiry_hint = QLabel("默认 1 天，可自定义有效天数；到期后自动删除账号和全部文件。")
        self.expiry_hint.setWordWrap(True)
        self.expiry_hint.setStyleSheet("color: #8b4a1f;")
        self.temp_checkbox.toggled.connect(self.expire_days_spin.setEnabled)

        form.addWidget(QLabel("用户名"), 0, 0)
        form.addWidget(self.username_input, 0, 1)
        form.addWidget(QLabel("密码"), 1, 0)
        form.addWidget(self.password_input, 1, 1)
        form.addWidget(QLabel("角色"), 2, 0)
        form.addWidget(self.role_combo, 2, 1)
        form.addWidget(QLabel("有效期"), 3, 0)
        form.addWidget(self.expire_days_spin, 3, 1)
        layout.addLayout(form)
        layout.addWidget(self.temp_checkbox)
        layout.addWidget(self.expiry_hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def payload(self):
        return {
            "username": self.username_input.text().strip(),
            "password": self.password_input.text(),
            "role": self.role_combo.currentText(),
            "expires_in_days": self.expire_days_spin.value() if self.temp_checkbox.isChecked() else None,
        }


class EditUserDialog(QDialog):
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = dict(user)
        self.setWindowTitle(format_window_title("编辑用户"))
        self.setModal(True)
        self.setFixedWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("修改账号信息")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #173042;")
        layout.addWidget(title)

        hint = QLabel(
            "可修改用户名；密码留空表示保持不变。"
            + (" 当前选择的是主管理员账号。" if self.user.get("is_primary_admin") else "")
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #5a7283;")
        layout.addWidget(hint)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        role_value = QLabel("admin" if self.user.get("role") == "admin" else "user")
        role_value.setStyleSheet("font-weight: 700; color: #173042;")
        self.username_input = QLineEdit(self.user.get("username", ""))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("留空则不修改密码")

        form.addWidget(QLabel("角色"), 0, 0)
        form.addWidget(role_value, 0, 1)
        form.addWidget(QLabel("用户名"), 1, 0)
        form.addWidget(self.username_input, 1, 1)
        form.addWidget(QLabel("新密码"), 2, 0)
        form.addWidget(self.password_input, 2, 1)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def payload(self):
        return {
            "username": self.username_input.text().strip(),
            "password": self.password_input.text(),
        }


class StatCard(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        self.value_label = QLabel("--")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setObjectName("statValue")
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(value)


class ServerDashboard(QMainWindow):
    def __init__(self, server, settings_store):
        super().__init__()
        self.server = server
        self.settings_store = settings_store
        self.settings = self.settings_store.load()
        self._users = []
        self._initial_positioned = False
        self._tray_mode_enabled = False
        self._allow_tray_exit = False
        self._external_runtime = self._empty_external_runtime()
        self._systemd_service_available = False
        self.setWindowTitle(format_window_title("TCP 传输服务端"))
        self.resize(1180, 760)
        self._build_ui()
        self._bind_server()
        self._runtime_probe_timer = QTimer(self)
        self._runtime_probe_timer.setInterval(2500)
        self._runtime_probe_timer.timeout.connect(self.refresh_runtime_state)
        self._runtime_probe_timer.start()
        self.refresh_users(server.list_users())
        self.refresh_runtime_state()
        self.refresh_sessions([])
        if self.auto_start_checkbox.isChecked():
            self.start_server()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("dashboardRoot")
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(18)

        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(18)

        hero_text_panel = QFrame()
        hero_text_panel.setObjectName("heroTextPanel")
        hero_left = QVBoxLayout()
        hero_left.setContentsMargins(18, 16, 18, 16)
        hero_left.setSpacing(8)
        title = QLabel("服务端控制台")
        title.setObjectName("heroTitle")
        subtitle = QLabel("本地用户管理、会话监控与传输统计集中在一个界面中。")
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)
        hero_left.addWidget(title)
        hero_left.addWidget(subtitle)
        hero_left.addStretch(1)
        hero_text_panel.setLayout(hero_left)

        hero_status_panel = QFrame()
        hero_status_panel.setObjectName("heroStatusPanel")
        hero_right = QVBoxLayout()
        hero_right.setContentsMargins(16, 16, 16, 16)
        hero_right.setSpacing(12)
        self.mode_badge = QLabel("未启动 · 支持 GUI 与 systemd 部署")
        self.mode_badge.setObjectName("heroBadge")
        self.deploy_badge = QLabel("Ubuntu 可作为开机自启服务运行")
        self.deploy_badge.setObjectName("heroBadgeAlt")
        hero_right.addWidget(self.mode_badge, alignment=Qt.AlignRight)
        hero_right.addWidget(self.deploy_badge, alignment=Qt.AlignRight)
        hero_right.addStretch(1)
        hero_status_panel.setLayout(hero_right)

        hero_layout.addWidget(hero_text_panel, 3)
        hero_layout.addWidget(hero_status_panel, 2)
        root.addWidget(hero_card)

        control_group = QGroupBox("服务设置")
        control_group.setObjectName("controlGroup")
        control_layout = QVBoxLayout(control_group)
        control_layout.setContentsMargins(16, 18, 16, 14)
        control_layout.setSpacing(12)

        top_control_row = QHBoxLayout()
        top_control_row.setSpacing(10)

        host_field = QFrame()
        host_field.setObjectName("fieldCard")
        host_field_layout = QVBoxLayout(host_field)
        host_field_layout.setContentsMargins(14, 10, 14, 12)
        host_field_layout.setSpacing(6)
        host_label = QLabel("监听地址")
        host_label.setObjectName("fieldLabel")
        self.host_input = QLineEdit(self.settings.get("host", DEFAULT_SERVER_HOST))
        self.host_input.setPlaceholderText(f"例如 {DEFAULT_SERVER_HOST}")
        host_field_layout.addWidget(host_label)
        host_field_layout.addWidget(self.host_input)

        port_field = QFrame()
        port_field.setObjectName("fieldCard")
        port_field_layout = QVBoxLayout(port_field)
        port_field_layout.setContentsMargins(14, 10, 14, 12)
        port_field_layout.setSpacing(6)
        port_label = QLabel("端口")
        port_label.setObjectName("fieldLabel")
        port_row = QHBoxLayout()
        port_row.setSpacing(8)
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(int(self.settings.get("port", DEFAULT_SERVER_PORT)))
        self.port_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.port_input.setAlignment(Qt.AlignCenter)
        self.port_input.setMinimumWidth(96)
        self.port_down_button = QPushButton("-")
        self.port_up_button = QPushButton("+")
        self.port_down_button.setObjectName("stepButton")
        self.port_up_button.setObjectName("stepButton")
        self.port_down_button.setFixedSize(32, 32)
        self.port_up_button.setFixedSize(32, 32)
        port_row.addWidget(self.port_input, 1)
        port_row.addWidget(self.port_down_button)
        port_row.addWidget(self.port_up_button)
        port_field_layout.addWidget(port_label)
        port_field_layout.addLayout(port_row)

        self.start_button = QPushButton("启动服务")
        self.stop_button = QPushButton("停止服务")
        self.start_button.setProperty("variant", "primary")
        self.stop_button.setProperty("variant", "danger")
        self.stop_button.setEnabled(False)

        top_control_row.addWidget(host_field, 1)
        top_control_row.addWidget(port_field)
        top_control_row.addWidget(self.start_button)
        top_control_row.addWidget(self.stop_button)

        bottom_control_row = QHBoxLayout()
        bottom_control_row.setSpacing(10)
        self.auto_start_checkbox = QCheckBox("打开控制台后自动启动服务")
        self.auto_start_checkbox.setChecked(bool(self.settings.get("auto_start_service", False)))
        self.auto_start_hint = QLabel("适合配合桌面快捷方式或系统开机自启使用。")
        self.auto_start_hint.setObjectName("hintLabel")
        bottom_control_row.addWidget(self.auto_start_checkbox)
        bottom_control_row.addStretch(1)
        bottom_control_row.addWidget(self.auto_start_hint)

        service_control_row = QHBoxLayout()
        service_control_row.setSpacing(10)
        self.systemd_enable_checkbox = QCheckBox("启用 tcptransgui-server.service 开机自启")
        self.systemd_enable_checkbox.setEnabled(False)
        self.systemd_enable_hint = QLabel("安装了 systemd 服务后，可在这里直接启用或禁用。")
        self.systemd_enable_hint.setObjectName("hintLabel")
        service_control_row.addWidget(self.systemd_enable_checkbox)
        service_control_row.addStretch(1)
        service_control_row.addWidget(self.systemd_enable_hint)

        control_layout.addLayout(top_control_row)
        control_layout.addLayout(bottom_control_row)
        control_layout.addLayout(service_control_row)
        root.addWidget(control_group)

        stats_layout = QGridLayout()
        self.status_card = StatCard("运行状态")
        self.sessions_card = StatCard("在线会话")
        self.upload_card = StatCard("累计上传")
        self.download_card = StatCard("累计下载")
        stats_layout.addWidget(self.status_card, 0, 0)
        stats_layout.addWidget(self.sessions_card, 0, 1)
        stats_layout.addWidget(self.upload_card, 0, 2)
        stats_layout.addWidget(self.download_card, 0, 3)
        root.addLayout(stats_layout)

        content_layout = QHBoxLayout()

        user_group = QGroupBox("用户管理")
        user_layout = QVBoxLayout(user_group)
        button_bar = QHBoxLayout()
        self.add_user_button = QPushButton("新增用户")
        self.edit_user_button = QPushButton("编辑用户")
        self.reset_password_button = QPushButton("重置密码")
        self.delete_user_button = QPushButton("删除用户")
        self.add_user_button.setProperty("variant", "accent")
        self.edit_user_button.setProperty("variant", "primary")
        self.reset_password_button.setProperty("variant", "secondary")
        self.delete_user_button.setProperty("variant", "danger")
        button_bar.addWidget(self.add_user_button)
        button_bar.addWidget(self.edit_user_button)
        button_bar.addWidget(self.reset_password_button)
        button_bar.addWidget(self.delete_user_button)
        user_layout.addLayout(button_bar)
        self.delete_storage_checkbox = QCheckBox("删除用户时同时清理用户目录")
        user_layout.addWidget(self.delete_storage_checkbox)

        self.user_table = QTableWidget(0, 5)
        self.user_table.setHorizontalHeaderLabels(["用户名", "角色", "类型", "到期时间", "目录"])
        self.user_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.user_table.verticalHeader().setVisible(False)
        self.user_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.user_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.user_table.setAlternatingRowColors(True)
        user_layout.addWidget(self.user_table)
        content_layout.addWidget(user_group, 3)

        side_panel = QVBoxLayout()

        session_group = QGroupBox("当前会话")
        session_layout = QVBoxLayout(session_group)
        self.session_table = QTableWidget(0, 4)
        self.session_table.setHorizontalHeaderLabels(["用户", "角色", "地址", "登录时间"])
        self.session_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.session_table.verticalHeader().setVisible(False)
        self.session_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.session_table.setAlternatingRowColors(True)
        session_layout.addWidget(self.session_table)
        side_panel.addWidget(session_group, 2)

        log_group = QGroupBox("服务日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        side_panel.addWidget(log_group, 3)

        content_layout.addLayout(side_panel, 4)
        root.addLayout(content_layout)

        self.setCentralWidget(central)

        self.setStyleSheet(
            """
            QMainWindow, QWidget#dashboardRoot {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #f5efe5,
                    stop: 0.52 #eef6f4,
                    stop: 1 #e1edf3
                );
                color: #173042;
                font-size: 13px;
            }
            QLabel {
                background: transparent;
            }
            QFrame#heroCard {
                border: none;
                border-radius: 26px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #14354d,
                    stop: 0.55 #195d69,
                    stop: 1 #2d857a
                );
            }
            QFrame#heroTextPanel, QFrame#heroStatusPanel {
                border: none;
                border-radius: 20px;
                background: rgba(255, 255, 255, 0.10);
            }
            QLabel#heroTitle {
                color: #fffdf8;
                font-size: 32px;
                font-weight: 800;
                letter-spacing: 0.4px;
            }
            QLabel#heroSubtitle {
                color: rgba(245, 251, 252, 0.92);
                font-size: 14px;
                line-height: 1.45;
            }
            QLabel#heroBadge, QLabel#heroBadgeAlt {
                padding: 10px 14px;
                border-radius: 14px;
                font-weight: 700;
            }
            QLabel#heroBadge {
                background: rgba(255, 247, 222, 0.95);
                color: #8b4a1f;
            }
            QLabel#heroBadgeAlt {
                background: rgba(12, 34, 46, 0.28);
                color: #f0f8fa;
            }
            QGroupBox {
                border: 1px solid rgba(23, 48, 66, 0.10);
                border-radius: 18px;
                margin-top: 12px;
                font-weight: 700;
                background: rgba(255, 255, 255, 0.93);
            }
            QGroupBox#controlGroup {
                border-radius: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
            QFrame#fieldCard {
                background: rgba(247, 251, 252, 0.96);
                border: 1px solid rgba(28, 127, 120, 0.16);
                border-radius: 18px;
            }
            QGroupBox#statCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgba(255, 255, 255, 0.98),
                    stop: 1 rgba(241, 248, 249, 0.98)
                );
            }
            QLabel#statValue {
                font-size: 28px;
                font-weight: 800;
                color: #173042;
            }
            QLineEdit, QSpinBox, QTableWidget, QPlainTextEdit {
                border: 1px solid #d7e1e6;
                border-radius: 14px;
                padding: 8px 10px;
                background: rgba(250, 252, 253, 0.98);
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #1c7f78;
                background: white;
            }
            QLabel#fieldLabel {
                color: #315164;
                font-weight: 700;
                font-size: 12px;
            }
            QLabel#hintLabel {
                color: #66808f;
            }
            QTableWidget {
                alternate-background-color: rgba(237, 244, 245, 0.75);
            }
            QTableWidget::item:selected {
                background: rgba(37, 144, 139, 0.14);
                color: #173042;
            }
            QHeaderView::section {
                background: #ebf3f4;
                color: #315164;
                border: none;
                border-bottom: 1px solid #d7e1e6;
                padding: 10px 8px;
                font-weight: 700;
            }
            QPlainTextEdit {
                background: #112b3b;
                color: #e5f1f5;
                border: 1px solid rgba(17, 43, 59, 0.25);
            }
            QSpinBox {
                padding-right: 10px;
                font-weight: 700;
                min-height: 34px;
            }
            QPushButton#stepButton {
                border: none;
                border-radius: 10px;
                padding: 0;
                font-size: 20px;
                font-weight: 800;
                color: #1c7f78;
                background: rgba(28, 127, 120, 0.12);
            }
            QPushButton#stepButton:hover {
                background: rgba(28, 127, 120, 0.22);
            }
            QPushButton#stepButton:pressed {
                background: rgba(28, 127, 120, 0.28);
            }
            QPushButton {
                border: none;
                border-radius: 12px;
                padding: 9px 16px;
                font-weight: 600;
            }
            QPushButton[variant="primary"] {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #1c7f78,
                    stop: 1 #2f9d8f
                );
                color: white;
            }
            QPushButton[variant="primary"]:hover:!disabled {
                background: #227c73;
            }
            QPushButton[variant="accent"] {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #d87733,
                    stop: 1 #bf5327
                );
                color: white;
            }
            QPushButton[variant="accent"]:hover:!disabled {
                background: #b94a22;
            }
            QPushButton[variant="secondary"] {
                background: rgba(20, 53, 77, 0.10);
                color: #173042;
            }
            QPushButton[variant="secondary"]:hover:!disabled {
                background: rgba(20, 53, 77, 0.16);
            }
            QPushButton[variant="danger"] {
                background: rgba(191, 95, 73, 0.12);
                color: #8d3e2a;
            }
            QPushButton[variant="danger"]:hover:!disabled {
                background: rgba(191, 95, 73, 0.20);
            }
            QPushButton:disabled {
                background: #d2dbe0;
                color: #78909c;
            }
            QCheckBox {
                color: #365466;
                spacing: 8px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 6px;
                border: 1px solid #c5d4dc;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #1c7f78;
                border: 1px solid #1c7f78;
            }
            """
        )

        self.start_button.clicked.connect(self.start_server)
        self.stop_button.clicked.connect(self.stop_server)
        self.add_user_button.clicked.connect(self.add_user)
        self.edit_user_button.clicked.connect(self.edit_user)
        self.reset_password_button.clicked.connect(self.reset_password)
        self.delete_user_button.clicked.connect(self.delete_user)
        self.host_input.editingFinished.connect(self.persist_settings)
        self.host_input.editingFinished.connect(self.refresh_runtime_state)
        self.port_input.valueChanged.connect(self.persist_settings)
        self.port_input.valueChanged.connect(self.refresh_runtime_state)
        self.auto_start_checkbox.toggled.connect(self.persist_settings)
        self.systemd_enable_checkbox.toggled.connect(self.on_systemd_enable_toggled)
        self.port_down_button.clicked.connect(lambda: self.adjust_port(-1))
        self.port_up_button.clicked.connect(lambda: self.adjust_port(1))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_positioned:
            self._center_on_screen()
            self._initial_positioned = True

    def _center_on_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def set_tray_mode_enabled(self, enabled):
        self._tray_mode_enabled = bool(enabled)

    def request_tray_exit(self):
        self._allow_tray_exit = True
        self.close()

    def closeEvent(self, event):
        if self._tray_mode_enabled and not self._allow_tray_exit:
            event.ignore()
            self.hide()
            return
        if self.server.is_running():
            self.server.stop()
        self._allow_tray_exit = False
        super().closeEvent(event)

    def _bind_server(self):
        self.server.log_message.connect(self.append_log)
        self.server.users_changed.connect(self.refresh_users)
        self.server.stats_changed.connect(self.refresh_stats)
        self.server.sessions_changed.connect(self.refresh_sessions)

    def append_log(self, message):
        self.log_view.appendPlainText(message)

    def adjust_port(self, delta):
        new_value = min(65535, max(1, self.port_input.value() + delta))
        self.port_input.setValue(new_value)

    def persist_settings(self):
        self.settings_store.save(
            host=self.host_input.text().strip() or DEFAULT_SERVER_HOST,
            port=int(self.port_input.value()),
            auto_start_service=self.auto_start_checkbox.isChecked(),
        )

    @staticmethod
    def _empty_external_runtime():
        return {
            "running": False,
            "managed_by": "",
            "can_stop": False,
            "badge": "",
            "hint": DEFAULT_DEPLOY_BADGE_TEXT,
            "start_message": "",
            "stop_message": "",
        }

    def _selected_host(self):
        return self.host_input.text().strip() or DEFAULT_SERVER_HOST

    def _selected_port(self):
        return int(self.port_input.value())

    @staticmethod
    def _is_wildcard_host(host):
        return (host or "").strip() in {"", "0.0.0.0", "*", "::", "[::]"}

    def _host_matches(self, left, right):
        left_value = (left or DEFAULT_SERVER_HOST).strip()
        right_value = (right or DEFAULT_SERVER_HOST).strip()
        if left_value == right_value:
            return True
        if self._is_wildcard_host(left_value) or self._is_wildcard_host(right_value):
            return True
        return {left_value, right_value} <= {"127.0.0.1", "localhost"}

    def _is_selected_port_in_use(self, host, port):
        bind_host = (host or DEFAULT_SERVER_HOST).strip() or DEFAULT_SERVER_HOST
        if bind_host == "*":
            bind_host = DEFAULT_SERVER_HOST
        if bind_host == "localhost":
            bind_host = "127.0.0.1"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
                candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                candidate.bind((bind_host, port))
        except socket.gaierror:
            return False
        except OSError as exc:
            return exc.errno == errno.EADDRINUSE
        return False

    def _load_systemd_runtime_config(self):
        config = {
            "host": DEFAULT_SERVER_HOST,
            "port": DEFAULT_SERVER_PORT,
        }
        if not SYSTEMD_ENV_FILE.exists():
            return config
        try:
            for raw_line in SYSTEMD_ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "TCPTRANSGUI_HOST" and value:
                    config["host"] = value
                elif key == "TCPTRANSGUI_PORT":
                    try:
                        config["port"] = int(value)
                    except (TypeError, ValueError):
                        pass
        except OSError:
            pass
        return config

    def _systemd_service_active(self):
        if shutil.which("systemctl") is None:
            return False
        try:
            result = subprocess.run(
                ["systemctl", "is-active", SYSTEMD_SERVICE_NAME],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0 and result.stdout.strip() == "active"

    def _systemd_unit_exists(self):
        return any(
            path.exists()
            for path in (
                Path("/etc/systemd/system") / SYSTEMD_SERVICE_NAME,
                Path("/lib/systemd/system") / SYSTEMD_SERVICE_NAME,
            )
        )

    def _systemd_service_enabled(self):
        if shutil.which("systemctl") is None or not self._systemd_unit_exists():
            return False
        try:
            result = subprocess.run(
                ["systemctl", "is-enabled", SYSTEMD_SERVICE_NAME],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0 and result.stdout.strip() == "enabled"

    def _refresh_systemd_service_controls(self):
        available = shutil.which("systemctl") is not None and self._systemd_unit_exists()
        self._systemd_service_available = available
        checked = self._systemd_service_enabled() if available else False
        self.systemd_enable_checkbox.blockSignals(True)
        self.systemd_enable_checkbox.setEnabled(available)
        self.systemd_enable_checkbox.setChecked(checked)
        self.systemd_enable_checkbox.blockSignals(False)
        if not available:
            self.systemd_enable_hint.setText("当前未检测到已安装的 tcptransgui-server.service。")
        elif checked:
            self.systemd_enable_hint.setText("已启用开机自启；取消勾选时会同时停止后台服务，避免继续占用端口。")
        else:
            self.systemd_enable_hint.setText("当前未启用开机自启；勾选后将由 systemd 在开机时自动拉起后台服务。")

    def _run_privileged_command(self, command):
        errors = []
        attempts = [command]
        if shutil.which("pkexec") is not None:
            attempts.append(["pkexec", *command])

        for current_command in attempts:
            try:
                result = subprocess.run(
                    current_command,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except Exception as exc:
                errors.append(str(exc))
                continue
            if result.returncode == 0:
                return True, ""
            output = (result.stderr or result.stdout).strip()
            if output:
                errors.append(output)

        message = "\n".join(item for item in errors if item).strip()
        if not message:
            message = f"命令执行失败：{' '.join(command)}"
        return False, message

    def _detect_external_runtime(self):
        if self.server.is_running():
            return self._empty_external_runtime()

        host = self._selected_host()
        port = self._selected_port()
        if not self._is_selected_port_in_use(host, port):
            return self._empty_external_runtime()

        service_active = self._systemd_service_active()
        service_config = self._load_systemd_runtime_config()
        managed_by_systemd = (
            service_active
            and int(service_config.get("port", DEFAULT_SERVER_PORT)) == port
            and self._host_matches(host, service_config.get("host", DEFAULT_SERVER_HOST))
        )

        if managed_by_systemd:
            return {
                "running": True,
                "managed_by": "systemd",
                "can_stop": True,
                "badge": f"运行中 · 已由 systemd 后台实例监听 {host}:{port}",
                "hint": "后台实例已在运行；如需改由当前界面接管，请先点击“停止服务”。",
                "start_message": (
                    f"端口 {port} 当前已由已安装的 systemd 后台服务监听。"
                    "\n无需重复启动；若要切换为当前界面托管，请先点击“停止服务”。"
                ),
                "stop_message": "",
            }

        return {
            "running": True,
            "managed_by": "external",
            "can_stop": False,
            "badge": f"端口占用 · {host}:{port} 已被其他进程监听",
            "hint": "请先释放该端口，或切换到其他未占用端口后再启动服务。",
            "start_message": (
                f"端口 {port} 已被其他进程占用。"
                f"\n请先停止占用进程，或改用其他端口，例如 {DEFAULT_SERVER_PORT}。"
            ),
            "stop_message": (
                f"端口 {port} 当前由其他进程占用，无法从本界面直接停止。"
                "\n请先关闭对应进程，或释放端口后再重试。"
            ),
        }

    def refresh_runtime_state(self):
        self._refresh_systemd_service_controls()
        self.refresh_stats(self.server.current_stats())

    def refresh_stats(self, stats):
        external = self._detect_external_runtime()
        self._external_runtime = external

        if stats["running"]:
            self.status_card.set_value("运行中")
            self.mode_badge.setText(f"运行中 · {stats['host']}:{stats['port']}")
            self.deploy_badge.setText("当前由控制台界面托管，可切换到托盘后台常驻。")
            self.start_button.setText("启动服务")
            self.stop_button.setText("停止服务")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        elif external["running"]:
            self.status_card.set_value("外部运行")
            self.mode_badge.setText(external["badge"])
            self.deploy_badge.setText(external["hint"])
            self.start_button.setText("启动服务")
            self.stop_button.setText("停止服务" if external["can_stop"] else "服务已被占用")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(external["can_stop"])
        else:
            self.status_card.set_value("已停止")
            self.mode_badge.setText("未启动 · 支持 GUI 与 systemd 部署")
            self.deploy_badge.setText(DEFAULT_DEPLOY_BADGE_TEXT)
            self.start_button.setText("启动服务")
            self.stop_button.setText("停止服务")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

        self.sessions_card.set_value(str(stats["session_count"]))
        self.upload_card.set_value(format_bytes(stats["upload_bytes"]))
        self.download_card.set_value(format_bytes(stats["download_bytes"]))

    def refresh_users(self, users):
        self._users = [dict(user) for user in users]
        self.user_table.setRowCount(len(users))
        for row, user in enumerate(users):
            self.user_table.setItem(row, 0, QTableWidgetItem(user["username"]))
            self.user_table.setItem(row, 1, QTableWidgetItem(user["role"]))
            if user.get("is_primary_admin"):
                account_type = "主管理员"
            else:
                account_type = "临时" if user.get("is_temporary") else "常规"
            self.user_table.setItem(row, 2, QTableWidgetItem(account_type))
            self.user_table.setItem(row, 3, QTableWidgetItem(user.get("expires_at_text", "-")))
            self.user_table.setItem(row, 4, QTableWidgetItem(user["home_dir"]))

    def refresh_sessions(self, sessions):
        self.session_table.setRowCount(len(sessions))
        for row, session in enumerate(sessions):
            self.session_table.setItem(row, 0, QTableWidgetItem(session["username"]))
            self.session_table.setItem(row, 1, QTableWidgetItem(session["role"]))
            self.session_table.setItem(row, 2, QTableWidgetItem(session["address"]))
            self.session_table.setItem(row, 3, QTableWidgetItem(session["created_at"]))

    def selected_username(self):
        user = self.selected_user()
        return user["username"] if user else ""

    def selected_user(self):
        row = self.user_table.currentRow()
        if row < 0 or row >= len(self._users):
            return None
        return dict(self._users[row])

    def start_server(self):
        self.persist_settings()
        external = self._detect_external_runtime()
        if external["running"]:
            box = QMessageBox.information if external["managed_by"] == "systemd" else QMessageBox.warning
            box(
                self,
                format_window_title("服务已在运行" if external["managed_by"] == "systemd" else "端口占用"),
                external["start_message"],
            )
            self.refresh_runtime_state()
            return
        try:
            self.server.start(self._selected_host(), self._selected_port())
        except OSError as exc:
            detail = str(exc)
            if exc.errno == errno.EACCES:
                detail = (
                    f"{exc}\n\n当前端口 {self.port_input.value()} 需要更高权限。"
                    " Linux/macOS 下普通用户不能监听 1-1023 端口。"
                    f"\n建议改用 {DEFAULT_SERVER_PORT} 这样的高位端口；"
                    "若必须使用低位端口，请改为 root 或 systemd 服务方式启动。"
                )
                if self.port_input.value() == LEGACY_PRIVILEGED_DEFAULT_PORT:
                    self.port_input.setValue(DEFAULT_SERVER_PORT)
                    self.persist_settings()
            elif exc.errno == errno.EADDRINUSE:
                external = self._detect_external_runtime()
                if external["running"]:
                    detail = external["start_message"]
                else:
                    detail = (
                        f"{exc}\n\n端口 {self.port_input.value()} 已被占用。"
                        f"\n请更换为未占用端口，例如 {DEFAULT_SERVER_PORT}。"
                    )
            QMessageBox.critical(self, format_window_title("启动失败"), detail)
        except Exception as exc:
            QMessageBox.critical(self, format_window_title("启动失败"), str(exc))

    def _stop_systemd_service(self):
        ok, error_text = self._run_privileged_command(["systemctl", "stop", SYSTEMD_SERVICE_NAME])
        if ok:
            return True, ""
        if not error_text:
            error_text = (
                "未能停止 systemd 后台服务。"
                "\n你也可以在终端中执行：sudo systemctl stop tcptransgui-server"
            )
        return False, error_text

    def on_systemd_enable_toggled(self, checked):
        if not self._systemd_service_available:
            return
        command = (
            ["systemctl", "enable", SYSTEMD_SERVICE_NAME]
            if checked
            else ["systemctl", "disable", "--now", SYSTEMD_SERVICE_NAME]
        )
        ok, error_text = self._run_privileged_command(command)
        self.refresh_runtime_state()
        if ok:
            return
        self.systemd_enable_checkbox.blockSignals(True)
        self.systemd_enable_checkbox.setChecked(not checked)
        self.systemd_enable_checkbox.blockSignals(False)
        action = "启用" if checked else "禁用"
        QMessageBox.warning(
            self,
            format_window_title(f"{action}失败"),
            error_text
            or (
                f"未能{action} tcptransgui-server.service。"
                f"\n你也可以在终端中执行：sudo systemctl {'enable' if checked else 'disable --now'} tcptransgui-server"
            ),
        )

    def stop_server(self):
        if self.server.is_running():
            self.server.stop()
            self.refresh_runtime_state()
            return

        external = self._detect_external_runtime()
        if not external["running"]:
            return
        if external["managed_by"] == "systemd":
            ok, error_text = self._stop_systemd_service()
            self.refresh_runtime_state()
            if not ok:
                QMessageBox.warning(self, format_window_title("停止失败"), error_text)
            return
        QMessageBox.information(self, format_window_title("无法停止"), external["stop_message"])

    def add_user(self):
        dialog = CreateUserDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        payload = dialog.payload()
        if not payload["username"] or not payload["password"]:
            QMessageBox.information(self, format_window_title("提示"), "用户名和密码不能为空。")
            return
        try:
            self.server.create_user(
                payload["username"],
                payload["password"],
                payload["role"],
                expires_in_days=payload["expires_in_days"],
            )
        except Exception as exc:
            QMessageBox.warning(self, format_window_title("新增失败"), str(exc))

    def edit_user(self):
        user = self.selected_user()
        if not user:
            QMessageBox.information(self, format_window_title("提示"), "请先选择一个用户。")
            return
        dialog = EditUserDialog(user, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        payload = dialog.payload()
        if not payload["username"]:
            QMessageBox.information(self, format_window_title("提示"), "用户名不能为空。")
            return
        try:
            updated_user = self.server.update_user(
                user["username"],
                new_username=payload["username"],
                password=payload["password"] or None,
            )
        except Exception as exc:
            QMessageBox.warning(self, format_window_title("修改失败"), str(exc))
            return

        changed = []
        if updated_user["username"] != user["username"]:
            changed.append(f"用户名已更新为 {updated_user['username']}")
        if payload["password"]:
            changed.append("密码已更新")
        if changed:
            QMessageBox.information(self, format_window_title("修改成功"), "，".join(changed) + "。")

    def reset_password(self):
        username = self.selected_username()
        if not username:
            QMessageBox.information(self, format_window_title("提示"), "请先选择一个用户。")
            return
        password, ok = QInputDialog.getText(
            self,
            format_window_title("重置密码"),
            f"为 {username} 设置新密码",
            QLineEdit.Password,
        )
        if not ok or not password:
            return
        try:
            self.server.reset_password(username, password)
        except Exception as exc:
            QMessageBox.warning(self, format_window_title("重置失败"), str(exc))

    def delete_user(self):
        username = self.selected_username()
        if not username:
            QMessageBox.information(self, format_window_title("提示"), "请先选择一个用户。")
            return
        remove_files = self.delete_storage_checkbox.isChecked()
        tip = "并同时清理该用户目录中的文件" if remove_files else "但保留该用户目录中的文件"
        confirmed = QMessageBox.question(
            self,
            format_window_title("删除用户"),
            f"确认删除用户 {username} 吗？本次将删除账号，{tip}。",
        )
        if confirmed != QMessageBox.Yes:
            return
        try:
            self.server.delete_user(username, remove_files=remove_files)
        except Exception as exc:
            QMessageBox.warning(self, format_window_title("删除失败"), str(exc))
