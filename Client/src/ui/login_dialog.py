from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QBoxLayout,
    QDialog,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from common.defaults import DEFAULT_LOCAL_SERVER
from common.app_meta import format_window_title


class LoginDialog(QDialog):
    def __init__(self, default_server, default_username):
        super().__init__()
        self.setWindowTitle(format_window_title("连接服务器"))
        self.default_server = default_server
        self.default_username = ""
        self._initial_positioned = False
        self._build_ui()
        self._configure_window_size()
        self.setSizeGripEnabled(True)

    def _configure_window_size(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            min_width = min(500, max(380, available.width() - 160))
            min_height = min(520, max(440, available.height() - 180))
            width = min(620, max(540, available.width() - 140))
            height = min(680, max(580, available.height() - 140))
        else:
            min_width, min_height = 380, 440
            width, height = 580, 620
        self.setMinimumSize(min_width, min_height)
        self.resize(width, height)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(self.scroll_area)

        page = QWidget()
        self.scroll_area.setWidget(page)

        root = QVBoxLayout(page)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(20, 20, 20, 20)
        hero_layout.setSpacing(8)

        eyebrow = QLabel("SECURE TCP TRANSFER")
        eyebrow.setObjectName("eyebrowLabel")
        title = QLabel("文件传输工作台")
        title.setObjectName("heroTitle")
        title.setWordWrap(True)
        subtitle = QLabel("连接到你的专属网盘，支持断点续传、多线程传输与暂停后恢复。")
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)
        hint = QLabel("输入 tcp://host:port、账号与密码即可开始。")
        hint.setObjectName("heroHint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        self.feature_row = QBoxLayout(QBoxLayout.LeftToRight)
        self.feature_row.setSpacing(6)
        tls_chip = QLabel("TLS 加密")
        tls_chip.setObjectName("heroChip")
        resume_chip = QLabel("断点续传")
        resume_chip.setObjectName("heroChipAlt")
        thread_chip = QLabel("多线程")
        thread_chip.setObjectName("heroChipAlt")
        self.feature_row.addWidget(tls_chip)
        self.feature_row.addWidget(resume_chip)
        self.feature_row.addWidget(thread_chip)
        self.feature_row.addStretch(1)

        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addLayout(self.feature_row)
        hero_layout.addWidget(hint)
        root.addWidget(hero_card)

        form_card = QFrame()
        form_card.setObjectName("formCard")
        form_wrap = QVBoxLayout(form_card)
        form_wrap.setContentsMargins(18, 16, 18, 16)
        form_wrap.setSpacing(12)

        form_title = QLabel("连接信息")
        form_title.setObjectName("sectionTitle")
        form_wrap.addWidget(form_title)

        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.form.setFormAlignment(Qt.AlignTop)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.form.setSpacing(10)
        self.form.setHorizontalSpacing(14)
        self.form.setVerticalSpacing(12)
        self.server_input = QLineEdit(self.default_server)
        self.server_input.setPlaceholderText(DEFAULT_LOCAL_SERVER)
        self.username_input = QLineEdit(self.default_username)
        self.username_input.setPlaceholderText("请输入用户名")
        self.password_input = QLineEdit("")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("请输入密码")
        self.server_input.setMinimumHeight(42)
        self.username_input.setMinimumHeight(42)
        self.password_input.setMinimumHeight(42)

        server_label = QLabel("服务器")
        username_label = QLabel("用户名")
        password_label = QLabel("密码")
        for label in (server_label, username_label, password_label):
            label.setObjectName("formLabel")
            label.setMinimumWidth(58)

        self.form.addRow(server_label, self.server_input)
        self.form.addRow(username_label, self.username_input)
        self.form.addRow(password_label, self.password_input)
        form_wrap.addLayout(self.form)
        root.addWidget(form_card)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setMinimumHeight(18)
        root.addWidget(self.error_label)

        self.button_row = QBoxLayout(QBoxLayout.LeftToRight)
        self.button_row.addStretch(1)
        self.cancel_button = QPushButton("退出")
        self.login_button = QPushButton("登录")
        self.cancel_button.setProperty("variant", "ghost")
        self.login_button.setProperty("variant", "primary")
        self.cancel_button.clicked.connect(self.reject)
        self.login_button.clicked.connect(self.accept)
        self.button_row.addWidget(self.cancel_button)
        self.button_row.addWidget(self.login_button)
        root.addLayout(self.button_row)

        self.setStyleSheet(
            """
            QDialog {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #f5efe4,
                    stop: 0.45 #edf5f3,
                    stop: 1 #dfeaf2
                );
                color: #173042;
                font-size: 13px;
            }
            QFrame#heroCard {
                border: none;
                border-radius: 22px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #12344d,
                    stop: 0.5 #1a5366,
                    stop: 0.82 #2f7b74,
                    stop: 1 #db7d34
                );
            }
            QLabel#eyebrowLabel {
                color: rgba(255, 233, 194, 0.92);
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.4px;
            }
            QLabel#heroTitle {
                color: white;
                font-size: 24px;
                font-weight: 800;
            }
            QLabel#heroSubtitle {
                color: rgba(255, 255, 255, 0.9);
                font-size: 13px;
            }
            QLabel#heroChip, QLabel#heroChipAlt {
                padding: 5px 10px;
                border-radius: 11px;
                font-weight: 700;
            }
            QLabel#heroChip {
                color: #8b4a1f;
                background: rgba(255, 241, 210, 0.94);
            }
            QLabel#heroChipAlt {
                color: #edf7f8;
                background: rgba(12, 34, 46, 0.22);
            }
            QLabel#heroHint {
                color: #12344d;
                background: rgba(255, 243, 214, 0.95);
                border-radius: 14px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QFrame#formCard {
                background: rgba(255, 255, 255, 0.94);
                border: 1px solid rgba(23, 48, 66, 0.10);
                border-radius: 20px;
            }
            QLabel#sectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #173042;
            }
            QLabel#formLabel {
                color: #476275;
                font-weight: 600;
            }
            QLineEdit {
                border: 1px solid #d4e0e7;
                border-radius: 12px;
                padding: 10px 12px;
                background: rgba(250, 252, 253, 0.96);
                selection-background-color: #1e7f74;
            }
            QLineEdit:focus {
                border: 1px solid #1e7f74;
                background: white;
            }
            QPushButton {
                border: none;
                border-radius: 12px;
                padding: 10px 18px;
                color: white;
                font-weight: 600;
            }
            QPushButton[variant="primary"] {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #d77432,
                    stop: 1 #c4552b
                );
            }
            QPushButton[variant="primary"]:hover {
                background: #bc4d25;
            }
            QPushButton[variant="ghost"] {
                background: rgba(18, 52, 77, 0.10);
                color: #173042;
            }
            QPushButton[variant="ghost"]:hover {
                background: rgba(18, 52, 77, 0.16);
            }
            QLabel#errorLabel {
                color: #b63f2a;
                font-weight: 600;
            }
            """
        )

        self.server_input.setFocus()
        self.server_input.selectAll()
        self.password_input.returnPressed.connect(self.accept)
        self._apply_responsive_layout()

    def credentials(self):
        return {
            "server": self.server_input.text().strip(),
            "username": self.username_input.text().strip(),
            "password": self.password_input.text(),
        }

    def show_error(self, message):
        self.error_label.setText(message)

    def _apply_responsive_layout(self):
        viewport_width = self.scroll_area.viewport().width() if hasattr(self, "scroll_area") else self.width()
        self.feature_row.setDirection(QBoxLayout.LeftToRight if viewport_width >= 520 else QBoxLayout.TopToBottom)
        self.button_row.setDirection(QBoxLayout.LeftToRight)
        self.form.setRowWrapPolicy(
            QFormLayout.DontWrapRows if viewport_width >= 520 else QFormLayout.WrapAllRows
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "scroll_area"):
            self._apply_responsive_layout()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "scroll_area"):
            self._apply_responsive_layout()
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
