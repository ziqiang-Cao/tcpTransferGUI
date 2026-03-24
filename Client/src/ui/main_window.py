import time
import uuid
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QMimeData, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QDrag
from PyQt5.QtWidgets import (
    QAbstractSpinBox,
    QAbstractItemView,
    QApplication,
    QBoxLayout,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Client.src.core.transfer import TransferTask
from Client.src.ui.dialogs import (
    ask_confirm,
    choose_open_file,
    choose_save_file,
    prompt_text,
    show_info,
    show_warning,
)
from Client.src.ui.transfer_item import TransferItem
from common.app_meta import format_window_title


ACTIVE_STATUSES = {"准备上传", "准备下载", "上传中", "下载中"}
RESTORABLE_STATUSES = {"已暂停", "失败", "等待恢复", "本地文件不存在"}


def format_size(value):
    size = float(value)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class RemoteFileTableWidget(QTableWidget):
    move_requested = pyqtSignal(str, str)

    MIME_TYPE = "application/x-tcptransgui-remote-path"

    def __init__(self, rows=0, columns=0, parent=None):
        super().__init__(rows, columns, parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

    def startDrag(self, supported_actions):
        row = self.currentRow()
        if row < 0:
            return
        item = self.item(row, 0)
        if item is None:
            return
        payload = item.data(Qt.UserRole)
        if not payload or not payload.get("path"):
            return
        mime_data = QMimeData()
        mime_data.setData(self.MIME_TYPE, payload["path"].encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(self.MIME_TYPE):
            super().dragMoveEvent(event)
            return
        row = self.rowAt(event.pos().y())
        if row < 0:
            event.ignore()
            return
        item = self.item(row, 0)
        payload = item.data(Qt.UserRole) if item else None
        if payload and payload.get("is_dir"):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(self.MIME_TYPE):
            super().dropEvent(event)
            return
        source_path = bytes(event.mimeData().data(self.MIME_TYPE)).decode("utf-8")
        row = self.rowAt(event.pos().y())
        if row < 0:
            event.ignore()
            return
        item = self.item(row, 0)
        payload = item.data(Qt.UserRole) if item else None
        if not payload or not payload.get("is_dir"):
            event.ignore()
            return
        self.move_requested.emit(source_path, payload["path"])
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self, client, state_store):
        super().__init__()
        self.client = client
        self.state_store = state_store
        self.task_entries = []
        self.remote_entries = []
        self.current_remote_dir = ""
        self._last_persist_time = 0.0
        self._icon_provider = QFileIconProvider()
        self._initial_size_fitted = False
        self._initial_positioned = False
        self._tray_mode_enabled = False
        self._allow_tray_exit = False
        self.setWindowTitle(format_window_title("TCP 文件传输客户端"))
        self._build_ui()
        self._configure_window_size()
        self.restore_saved_tasks()
        self.refresh_files()

    def _configure_window_size(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            screen_width = available.width()
            screen_height = available.height()
        else:
            screen_width = 1440
            screen_height = 900

        max_usable_width = max(760, screen_width - 40)
        min_width = min(980, max_usable_width)
        default_width = min(1160, max(1020, screen_width - 120))
        default_width = min(default_width, max_usable_width)
        if default_width < min_width:
            default_width = min_width
        min_height = min(560, max(480, screen_height - 180))
        default_height = min(760, max(620, screen_height - 140))
        self.setMinimumSize(min_width, min_height)
        super().resize(default_width, default_height)

    def _build_ui(self):
        settings = self.state_store.load_settings()

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.hero_layout = QBoxLayout(QBoxLayout.LeftToRight, hero_card)
        self.hero_layout.setContentsMargins(22, 18, 22, 18)
        self.hero_layout.setSpacing(16)

        hero_text_panel = QFrame()
        hero_text_panel.setObjectName("heroTextPanel")
        hero_text_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        hero_text = QVBoxLayout()
        hero_text.setContentsMargins(16, 12, 16, 12)
        hero_text.setSpacing(6)
        eyebrow = QLabel("SECURE FILE DESK")
        eyebrow.setObjectName("heroEyebrow")
        title = QLabel("文件传输工作台")
        title.setObjectName("heroTitle")
        subtitle = QLabel("稳定传输、大文件断点续传、暂停后恢复任务列表。")
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)
        self.hero_features_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.hero_features_layout.setSpacing(6)
        self.resume_badge = QLabel("断点续传")
        self.resume_badge.setObjectName("heroMiniBadge")
        self.thread_badge = QLabel("多线程传输")
        self.thread_badge.setObjectName("heroMiniBadgeAlt")
        self.hero_features_layout.addWidget(self.resume_badge)
        self.hero_features_layout.addWidget(self.thread_badge)
        self.hero_features_layout.addStretch(1)
        hero_text.addWidget(eyebrow)
        hero_text.addWidget(title)
        hero_text.addWidget(subtitle)
        hero_text.addLayout(self.hero_features_layout)
        hero_text_panel.setLayout(hero_text)

        hero_status_panel = QFrame()
        hero_status_panel.setObjectName("heroStatusPanel")
        hero_status_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        hero_side = QVBoxLayout()
        hero_side.setContentsMargins(14, 12, 14, 12)
        hero_side.setSpacing(8)
        self.connection_badge = QLabel(f"{self.client.username} @ {self.client.server_text}")
        self.connection_badge.setObjectName("connectionBadge")
        self.connection_badge.setWordWrap(True)
        self.transport_badge = QLabel("TLS 加密链路已启用")
        self.transport_badge.setObjectName("summaryBadgeWarm")
        self.transport_badge.setWordWrap(True)
        self.server_summary_label = QLabel("服务器文件 0 项")
        self.server_summary_label.setObjectName("summaryBadge")
        self.server_summary_label.setWordWrap(True)
        self.task_summary_label = QLabel("传输任务 0 项")
        self.task_summary_label.setObjectName("summaryBadgeAlt")
        self.task_summary_label.setWordWrap(True)
        hero_side.addWidget(self.connection_badge, alignment=Qt.AlignRight)
        hero_side.addWidget(self.transport_badge, alignment=Qt.AlignRight)
        hero_side.addWidget(self.server_summary_label, alignment=Qt.AlignRight)
        hero_side.addWidget(self.task_summary_label, alignment=Qt.AlignRight)
        hero_status_panel.setLayout(hero_side)

        self.hero_layout.addWidget(hero_text_panel, 3)
        self.hero_layout.addWidget(hero_status_panel, 2)
        root.addWidget(hero_card)

        toolbar_card = QFrame()
        toolbar_card.setObjectName("toolbarCard")
        toolbar_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.toolbar_layout = QBoxLayout(QBoxLayout.LeftToRight, toolbar_card)
        self.toolbar_layout.setContentsMargins(16, 12, 16, 12)
        self.toolbar_layout.setSpacing(12)
        action_strip = QFrame()
        action_strip.setObjectName("actionStrip")
        action_strip.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.action_layout = QBoxLayout(QBoxLayout.LeftToRight, action_strip)
        self.action_layout.setContentsMargins(8, 8, 8, 8)
        self.action_layout.setSpacing(8)
        self.refresh_button = QPushButton("刷新列表")
        self.upload_button = QPushButton("上传文件")
        self.download_button = QPushButton("下载选中")
        self.clear_finished_button = QPushButton("清理已完成")
        self.refresh_button.setProperty("variant", "secondary")
        self.upload_button.setProperty("variant", "primary")
        self.download_button.setProperty("variant", "accent")
        self.clear_finished_button.setProperty("variant", "ghost")
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 16)
        self.thread_spin.setValue(int(settings.get("thread_count", 4)))
        self.thread_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.thread_spin.setAlignment(Qt.AlignCenter)
        self.thread_spin.setMinimumWidth(72)
        self.action_dividers = []
        self.action_layout.addWidget(self.refresh_button)
        divider = self._build_divider("vertical", "actionDivider")
        self.action_dividers.append(divider)
        self.action_layout.addWidget(divider)
        self.action_layout.addWidget(self.upload_button)
        divider = self._build_divider("vertical", "actionDivider")
        self.action_dividers.append(divider)
        self.action_layout.addWidget(divider)
        self.action_layout.addWidget(self.download_button)
        divider = self._build_divider("vertical", "actionDivider")
        self.action_dividers.append(divider)
        self.action_layout.addWidget(divider)
        self.action_layout.addWidget(self.clear_finished_button)
        self.toolbar_layout.addWidget(action_strip, 1)
        self.toolbar_main_divider = self._build_divider("vertical", "toolbarDivider")
        self.toolbar_layout.addWidget(self.toolbar_main_divider)
        tool_strip = QFrame()
        tool_strip.setObjectName("toolStrip")
        tool_strip.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.tool_layout = QBoxLayout(QBoxLayout.LeftToRight, tool_strip)
        self.tool_layout.setContentsMargins(10, 6, 10, 6)
        self.tool_layout.setSpacing(10)
        self.toolbar_hint = QLabel("任务列表会自动保留，关闭客户端后下次可继续恢复。")
        self.toolbar_hint.setObjectName("toolbarHint")
        self.toolbar_hint.setWordWrap(True)
        thread_card = QFrame()
        thread_card.setObjectName("threadCard")
        thread_card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)
        thread_layout = QVBoxLayout(thread_card)
        thread_layout.setContentsMargins(8, 6, 8, 6)
        thread_layout.setSpacing(2)
        thread_label = QLabel("并发线程")
        thread_label.setObjectName("threadCardLabel")
        thread_layout.addWidget(thread_label)
        thread_layout.addWidget(self.thread_spin)
        self.thread_spin.setFixedHeight(34)
        self.tool_dividers = []
        self.tool_layout.addWidget(self.toolbar_hint, 1)
        divider = self._build_divider("vertical", "toolbarDivider")
        self.tool_dividers.append(divider)
        self.tool_layout.addWidget(divider)
        self.tool_layout.addWidget(thread_card)
        self.toolbar_layout.addWidget(tool_strip)
        root.addWidget(toolbar_card)

        self.content_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.content_layout.setSpacing(16)

        left_card = QFrame()
        left_card.setObjectName("panelCard")
        left_panel = QVBoxLayout(left_card)
        left_panel.setContentsMargins(18, 18, 18, 18)
        left_panel.setSpacing(12)
        self.file_header_layout = QBoxLayout(QBoxLayout.LeftToRight)
        file_title_wrap = QVBoxLayout()
        file_title = QLabel("服务器文件")
        file_title.setObjectName("sectionTitle")
        file_subtitle = QLabel("双击或选中后下载，列表实时显示远端文件状态。")
        file_subtitle.setObjectName("sectionSubtitle")
        file_subtitle.setWordWrap(True)
        self.file_section_badge = QLabel("0 项")
        self.file_section_badge.setObjectName("sectionBadge")
        file_title_wrap.addWidget(file_title)
        file_title_wrap.addWidget(file_subtitle)
        self.file_header_layout.addLayout(file_title_wrap, 1)
        self.file_header_layout.addWidget(self.file_section_badge, alignment=Qt.AlignTop)
        self.file_path_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.file_path_layout.setSpacing(10)
        self.up_button = QPushButton("返回上一级")
        self.up_button.setProperty("variant", "secondary")
        self.remote_path_label = QLabel("当前位置：/")
        self.remote_path_label.setObjectName("pathBadge")
        self.remote_path_label.setWordWrap(True)
        self.file_path_layout.addWidget(self.up_button)
        self.file_path_layout.addWidget(self.remote_path_label, 1)
        self.file_table = RemoteFileTableWidget(0, 3)
        self.file_table.setHorizontalHeaderLabels(["文件名", "大小", "修改时间"])
        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_table.setMinimumHeight(240)
        self.file_empty_state = self._build_empty_state(
            "云端文件列表为空",
            "上传文件后，这里会显示远端文件清单。你也可以先刷新一次确认连接状态。",
            "立即上传",
            self.pick_upload,
            "teal",
        )
        left_panel.addLayout(self.file_header_layout)
        left_panel.addLayout(self.file_path_layout)
        left_panel.addWidget(self._build_divider("horizontal", "panelDivider"))
        left_panel.addWidget(self.file_table)
        left_panel.addWidget(self.file_empty_state)
        self.content_layout.addWidget(left_card, 3)

        right_card = QFrame()
        right_card.setObjectName("panelCard")
        right_panel = QVBoxLayout(right_card)
        right_panel.setContentsMargins(18, 18, 18, 18)
        right_panel.setSpacing(12)
        self.task_header_layout = QBoxLayout(QBoxLayout.LeftToRight)
        task_title_wrap = QVBoxLayout()
        task_title = QLabel("传输任务")
        task_title.setObjectName("sectionTitle")
        task_subtitle = QLabel("支持暂停、继续、失败后恢复，以及关闭客户端后保留任务。")
        task_subtitle.setObjectName("sectionSubtitle")
        task_subtitle.setWordWrap(True)
        self.task_section_badge = QLabel("待恢复 0")
        self.task_section_badge.setObjectName("sectionBadgeAlt")
        task_title_wrap.addWidget(task_title)
        task_title_wrap.addWidget(task_subtitle)
        self.task_header_layout.addLayout(task_title_wrap, 1)
        self.task_header_layout.addWidget(self.task_section_badge, alignment=Qt.AlignTop)
        self.transfer_list = QListWidget()
        self.transfer_list.setSpacing(10)
        self.transfer_list.setDragEnabled(True)
        self.transfer_list.setAcceptDrops(True)
        self.transfer_list.setDropIndicatorShown(True)
        self.transfer_list.setDefaultDropAction(Qt.MoveAction)
        self.transfer_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.transfer_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.transfer_list.setMinimumHeight(240)
        self.task_empty_state = self._build_empty_state(
            "当前没有传输任务",
            "新建上传或下载任务后，进度、速度与恢复状态都会显示在这里。",
            "上传文件",
            self.pick_upload,
            "warm",
        )
        right_panel.addLayout(self.task_header_layout)
        right_panel.addWidget(self._build_divider("horizontal", "panelDivider"))
        right_panel.addWidget(self.transfer_list)
        right_panel.addWidget(self.task_empty_state)
        self.content_layout.addWidget(right_card, 2)

        root.addLayout(self.content_layout, 1)
        self.setCentralWidget(central)

        self.setStyleSheet(
            """
            QWidget {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #fff4e7,
                    stop: 0.48 #edf7f4,
                    stop: 1 #e0edf7
                );
                color: #173042;
                font-size: 13px;
            }
            QLabel {
                background: transparent;
            }
            QFrame#heroCard {
                border: none;
                border-radius: 28px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #14324a,
                    stop: 0.4 #17586a,
                    stop: 0.72 #1f7a79,
                    stop: 1 #db7d34
                );
            }
            QFrame#heroTextPanel, QFrame#heroStatusPanel {
                border: none;
                border-radius: 20px;
                background: rgba(255, 255, 255, 0.10);
            }
            QLabel#heroEyebrow {
                color: rgba(255, 237, 201, 0.94);
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.4px;
            }
            QLabel#heroTitle {
                color: white;
                font-size: 31px;
                font-weight: 800;
            }
            QLabel#heroSubtitle {
                color: rgba(255, 255, 255, 0.88);
                font-size: 14px;
            }
            QLabel#heroMiniBadge, QLabel#heroMiniBadgeAlt,
            QLabel#connectionBadge, QLabel#summaryBadge, QLabel#summaryBadgeAlt, QLabel#summaryBadgeWarm {
                padding: 6px 11px;
                border-radius: 12px;
                font-weight: 700;
            }
            QLabel#heroMiniBadge {
                background: rgba(255, 244, 218, 0.92);
                color: #8b4a1f;
            }
            QLabel#heroMiniBadgeAlt {
                background: rgba(11, 35, 47, 0.22);
                color: #eef7f8;
            }
            QLabel#connectionBadge {
                background: rgba(255, 252, 244, 0.96);
                color: #1f5262;
            }
            QLabel#summaryBadgeWarm {
                background: rgba(255, 240, 209, 0.94);
                color: #8b4a1f;
            }
            QLabel#summaryBadge {
                background: rgba(255, 255, 255, 0.18);
                color: white;
            }
            QLabel#summaryBadgeAlt {
                background: rgba(12, 34, 46, 0.22);
                color: #e9f3f6;
            }
            QFrame#toolbarCard, QFrame#panelCard {
                background: rgba(255, 255, 255, 0.92);
                border: 1px solid rgba(23, 48, 66, 0.09);
                border-radius: 22px;
            }
            QFrame#actionStrip, QFrame#toolStrip {
                background: transparent;
                border: none;
                border-radius: 0;
            }
            QFrame#threadCard {
                background: transparent;
                border: none;
                border-radius: 14px;
            }
            QFrame#toolbarDivider, QFrame#actionDivider, QFrame#panelDivider {
                background: rgba(23, 48, 66, 0.10);
                border: none;
            }
            QFrame#toolbarDivider, QFrame#actionDivider {
                min-width: 1px;
                max-width: 1px;
            }
            QFrame#panelDivider {
                min-height: 1px;
                max-height: 1px;
                margin: 2px 0 4px 0;
            }
            QLabel#sectionTitle {
                font-size: 17px;
                font-weight: 700;
                color: #173042;
            }
            QLabel#sectionSubtitle, QLabel#mutedLabel, QLabel#toolbarHint {
                color: #627786;
            }
            QLabel#threadCardLabel {
                color: #315164;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#pathBadge {
                padding: 6px 10px;
                border-radius: 12px;
                background: rgba(20, 53, 77, 0.06);
                color: #315164;
                border: 1px solid rgba(20, 53, 77, 0.08);
            }
            QLabel#sectionBadge, QLabel#sectionBadgeAlt {
                padding: 6px 10px;
                border-radius: 12px;
                font-weight: 700;
            }
            QLabel#sectionBadge {
                background: transparent;
                color: #176f67;
                border: 1px solid rgba(28, 127, 120, 0.16);
            }
            QLabel#sectionBadgeAlt {
                background: transparent;
                color: #9b4f22;
                border: 1px solid rgba(216, 119, 51, 0.18);
            }
            QFrame#emptyStateCard {
                background: transparent;
                border: none;
                border-radius: 0;
            }
            QLabel#emptyStateBadge {
                padding: 8px 12px;
                border-radius: 13px;
                font-weight: 700;
                background: transparent;
                color: #176f67;
            }
            QLabel#emptyStateBadge[tone="warm"] {
                background: transparent;
                color: #9b4f22;
            }
            QLabel#emptyStateTitle {
                color: #173042;
                font-size: 18px;
                font-weight: 800;
            }
            QLabel#emptyStateBody {
                color: #627786;
            }
            QTableWidget, QListWidget, QSpinBox {
                border: 1px solid #d7e1e6;
                border-radius: 16px;
                background: rgba(251, 253, 254, 0.98);
                padding: 6px;
            }
            QHeaderView::section {
                background: #edf5f6;
                color: #315164;
                border: none;
                border-bottom: 1px solid #d7e1e6;
                padding: 11px 8px;
                font-weight: 700;
            }
            QTableWidget::item, QListWidget::item {
                padding: 6px;
            }
            QTableWidget::item:selected, QListWidget::item:selected {
                background: rgba(37, 144, 139, 0.15);
                color: #173042;
            }
            QTableWidget {
                alternate-background-color: rgba(240, 246, 247, 0.82);
                gridline-color: rgba(215, 225, 230, 0.68);
            }
            QPushButton {
                border: none;
                border-radius: 13px;
                padding: 9px 15px;
                font-weight: 600;
            }
            QPushButton[variant="primary"] {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #dd8034,
                    stop: 1 #c75728
                );
                color: white;
            }
            QPushButton[variant="primary"]:hover {
                background: #b94a22;
            }
            QPushButton[variant="accent"] {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #1c7f78,
                    stop: 1 #2f9d8f
                );
                color: white;
            }
            QPushButton[variant="accent"]:hover {
                background: #227c73;
            }
            QPushButton[variant="secondary"] {
                background: rgba(20, 53, 77, 0.10);
                color: #173042;
            }
            QPushButton[variant="secondary"]:hover {
                background: rgba(20, 53, 77, 0.16);
            }
            QPushButton[variant="ghost"] {
                background: rgba(191, 95, 73, 0.10);
                color: #8d3e2a;
            }
            QPushButton[variant="ghost"]:hover {
                background: rgba(191, 95, 73, 0.16);
            }
            QPushButton:disabled {
                background: #d2dbe0;
                color: #78909c;
            }
            QSpinBox:focus {
                border: 1px solid #1c7f78;
            }
            """
        )

        self.refresh_button.clicked.connect(self.refresh_files)
        self.upload_button.clicked.connect(self.pick_upload)
        self.download_button.clicked.connect(self.pick_download)
        self.clear_finished_button.clicked.connect(self.clear_finished_tasks)
        self.thread_spin.valueChanged.connect(self.persist_settings)
        self.file_table.doubleClicked.connect(lambda _: self.open_selected_entry())
        self.file_table.customContextMenuRequested.connect(self.open_file_context_menu)
        self.file_table.move_requested.connect(self.move_remote_entry_to_dir)
        self.up_button.clicked.connect(self.go_up_directory)
        self.transfer_list.model().rowsMoved.connect(self.on_task_rows_moved)
        self.update_empty_states()
        self._apply_responsive_layout()

    def _build_empty_state(self, title, body, action_text, action_handler, tone):
        card = QFrame()
        card.setObjectName("emptyStateCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(10)

        badge = QLabel("空状态")
        badge.setObjectName("emptyStateBadge")
        badge.setProperty("tone", tone)
        title_label = QLabel(title)
        title_label.setObjectName("emptyStateTitle")
        body_label = QLabel(body)
        body_label.setObjectName("emptyStateBody")
        body_label.setWordWrap(True)
        button = QPushButton(action_text)
        button.setProperty("variant", "secondary" if tone == "teal" else "primary")
        button.clicked.connect(action_handler)

        layout.addWidget(badge, alignment=Qt.AlignLeft)
        layout.addWidget(title_label)
        layout.addWidget(body_label)
        layout.addWidget(button, alignment=Qt.AlignLeft)
        layout.addStretch(1)
        return card

    def _build_divider(self, orientation, object_name):
        divider = QFrame()
        divider.setObjectName(object_name)
        if orientation == "vertical":
            divider.setFrameShape(QFrame.VLine)
        else:
            divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Plain)
        return divider

    @staticmethod
    def _set_box_direction(layout, direction):
        if layout.direction() != direction:
            layout.setDirection(direction)

    def _apply_responsive_layout(self, viewport_width=None):
        viewport_width = viewport_width or max(self.width(), self.minimumWidth(), 760)
        wide = viewport_width >= 980
        medium = viewport_width >= 900
        compact = viewport_width < 820

        self._set_box_direction(
            self.hero_layout,
            QBoxLayout.LeftToRight if medium else QBoxLayout.TopToBottom,
        )
        self._set_box_direction(
            self.hero_features_layout,
            QBoxLayout.LeftToRight if viewport_width >= 720 else QBoxLayout.TopToBottom,
        )
        self._set_box_direction(
            self.toolbar_layout,
            QBoxLayout.LeftToRight if viewport_width >= 920 else QBoxLayout.TopToBottom,
        )
        self._set_box_direction(
            self.action_layout,
            QBoxLayout.LeftToRight if viewport_width >= 860 else QBoxLayout.TopToBottom,
        )
        self._set_box_direction(
            self.tool_layout,
            QBoxLayout.LeftToRight if viewport_width >= 820 else QBoxLayout.TopToBottom,
        )
        self._set_box_direction(
            self.content_layout,
            QBoxLayout.LeftToRight if wide else QBoxLayout.TopToBottom,
        )
        self._set_box_direction(
            self.file_header_layout,
            QBoxLayout.LeftToRight if viewport_width >= 700 else QBoxLayout.TopToBottom,
        )
        self._set_box_direction(
            self.task_header_layout,
            QBoxLayout.LeftToRight if viewport_width >= 700 else QBoxLayout.TopToBottom,
        )
        self._set_box_direction(
            self.file_path_layout,
            QBoxLayout.LeftToRight if viewport_width >= 760 else QBoxLayout.TopToBottom,
        )

        horizontal_action = self.action_layout.direction() == QBoxLayout.LeftToRight
        horizontal_tool = self.tool_layout.direction() == QBoxLayout.LeftToRight
        toolbar_horizontal = self.toolbar_layout.direction() == QBoxLayout.LeftToRight
        self.toolbar_main_divider.setVisible(toolbar_horizontal)
        for divider in self.action_dividers:
            divider.setVisible(horizontal_action)
        for divider in self.tool_dividers:
            divider.setVisible(horizontal_tool)

        self.remote_path_label.setMinimumHeight(0)
        self.remote_path_label.setMaximumWidth(16777215 if medium else max(280, viewport_width - 140))
        self.toolbar_hint.setMaximumWidth(16777215 if viewport_width >= 820 else max(260, viewport_width - 120))
        self.file_table.setMinimumHeight(280 if compact else 320)
        self.transfer_list.setMinimumHeight(280 if compact else 320)

    def _refresh_task_item_sizes(self):
        for row in range(self.transfer_list.count()):
            item = self.transfer_list.item(row)
            widget = self.transfer_list.itemWidget(item)
            if item is not None and widget is not None:
                item.setSizeHint(widget.sizeHint())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout(event.size().width())
        self._refresh_task_item_sizes()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_responsive_layout(self.width())
        self._refresh_task_item_sizes()
        if not self._initial_size_fitted:
            screen = self.screen() or QApplication.primaryScreen()
            max_height = (screen.availableGeometry().height() - 80) if screen is not None else 900
            target_height = min(max(self.sizeHint().height(), self.minimumSizeHint().height()), max_height)
            if target_height > 0:
                self.setMinimumHeight(target_height)
                if self.height() != target_height:
                    super().resize(self.width(), target_height)
            self._initial_size_fitted = True
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

    def _file_icon(self, filename):
        suffix = Path(filename).suffix.lower()
        mapping = {
            ".png": QStyle.SP_FileIcon,
            ".jpg": QStyle.SP_FileIcon,
            ".jpeg": QStyle.SP_FileIcon,
            ".gif": QStyle.SP_FileIcon,
            ".bmp": QStyle.SP_FileIcon,
            ".pdf": QStyle.SP_FileIcon,
            ".zip": QStyle.SP_DriveFDIcon,
            ".7z": QStyle.SP_DriveFDIcon,
            ".rar": QStyle.SP_DriveFDIcon,
            ".txt": QStyle.SP_FileIcon,
            ".md": QStyle.SP_FileIcon,
            ".doc": QStyle.SP_FileIcon,
            ".docx": QStyle.SP_FileIcon,
            ".xls": QStyle.SP_FileIcon,
            ".xlsx": QStyle.SP_FileIcon,
            ".mp4": QStyle.SP_MediaPlay,
            ".mp3": QStyle.SP_MediaVolume,
        }
        if suffix in mapping:
            return self.style().standardIcon(mapping[suffix])
        return self._icon_provider.icon(QFileIconProvider.File)

    @staticmethod
    def _basename(remote_path):
        text = str(remote_path or "").replace("\\", "/").rstrip("/")
        if not text:
            return ""
        return text.split("/")[-1]

    @staticmethod
    def _join_remote_path(base_dir, name):
        base = str(base_dir or "").strip().strip("/")
        leaf = str(name or "").strip().strip("/")
        if not base:
            return leaf
        if not leaf:
            return base
        return f"{base}/{leaf}"

    def update_empty_states(self):
        has_files = self.file_table.rowCount() > 0
        self.file_table.setVisible(has_files)
        self.file_empty_state.setVisible(not has_files)

        has_tasks = bool(self.task_entries)
        self.transfer_list.setVisible(has_tasks)
        self.task_empty_state.setVisible(not has_tasks)

    def on_task_rows_moved(self, *_args):
        self.sync_task_entry_order()
        self.persist_tasks(force=True)

    def sync_task_entry_order(self):
        entry_by_item = {id(entry["item"]): entry for entry in self.task_entries}
        ordered_entries = []
        for row in range(self.transfer_list.count()):
            item = self.transfer_list.item(row)
            entry = entry_by_item.get(id(item))
            if entry is not None:
                ordered_entries.append(entry)
        if len(ordered_entries) == len(self.task_entries):
            self.task_entries = ordered_entries

    def persist_settings(self):
        self.state_store.save_settings(
            last_server=self.client.server_text,
            thread_count=self.thread_spin.value(),
        )

    def refresh_files(self):
        try:
            files, current_dir = self.client.list_files(self.current_remote_dir)
        except Exception as exc:
            show_warning(self, "刷新失败", str(exc))
            return
        self.current_remote_dir = current_dir
        self.remote_entries = list(files)
        self.remote_path_label.setText(f"当前位置：/{current_dir}" if current_dir else "当前位置：/")
        self.up_button.setEnabled(bool(current_dir))
        self.server_summary_label.setText(f"服务器文件 {len(files)} 项")
        self.file_section_badge.setText(f"{len(files)} 项")
        self.file_table.setRowCount(len(files))
        for row, file_info in enumerate(files):
            modified = datetime.fromtimestamp(file_info["modified"]).strftime("%Y-%m-%d %H:%M:%S")
            name_item = QTableWidgetItem(file_info["name"])
            name_item.setData(Qt.UserRole, dict(file_info))
            if file_info.get("is_dir"):
                name_item.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
            else:
                name_item.setIcon(self._file_icon(file_info["name"]))
            self.file_table.setItem(row, 0, name_item)
            self.file_table.setItem(
                row,
                1,
                QTableWidgetItem("-" if file_info.get("is_dir") else format_size(file_info["size"])),
            )
            self.file_table.setItem(row, 2, QTableWidgetItem(modified))
        self.update_empty_states()

    def selected_remote_entry(self):
        row = self.file_table.currentRow()
        if row < 0 or row >= len(self.remote_entries):
            return None
        return dict(self.remote_entries[row])

    def selected_remote_name(self):
        entry = self.selected_remote_entry()
        return entry["path"] if entry else ""

    def pick_upload(self):
        file_path = choose_open_file(self, "选择要上传的文件")
        if not file_path:
            return
        self.start_upload(file_path)

    def pick_download(self):
        entry = self.selected_remote_entry()
        if not entry:
            show_info(self, "请选择文件", "请先在服务器文件列表中选择一个文件，再执行下载。")
            return
        if entry.get("is_dir"):
            show_info(self, "不能下载文件夹", "当前版本支持进入文件夹浏览，但下载操作仅支持单个文件。")
            return
        save_path = choose_save_file(self, "保存文件", self._basename(entry["path"]))
        if not save_path:
            return
        self.start_download(entry["path"], save_path)

    def open_selected_entry(self):
        entry = self.selected_remote_entry()
        if not entry:
            return
        if entry.get("is_dir"):
            self.current_remote_dir = entry["path"]
            self.refresh_files()
            return
        self.pick_download()

    def go_up_directory(self):
        if not self.current_remote_dir:
            return
        parts = self.current_remote_dir.split("/")
        self.current_remote_dir = "/".join(parts[:-1])
        self.refresh_files()

    def open_file_context_menu(self, position):
        index = self.file_table.indexAt(position)
        if index.isValid():
            self.file_table.selectRow(index.row())
        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background: rgba(255, 255, 255, 0.98);
                border: 1px solid rgba(23, 48, 66, 0.10);
                border-radius: 12px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 18px;
                border-radius: 8px;
                color: #173042;
            }
            QMenu::item:selected {
                background: rgba(28, 127, 120, 0.12);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(23, 48, 66, 0.10);
                margin: 6px 8px;
            }
            """
        )

        entry = self.selected_remote_entry()
        open_action = None
        rename_action = None
        move_action = None
        delete_action = None
        if entry:
            open_action = menu.addAction("打开" if entry.get("is_dir") else "下载")
            menu.addSeparator()
            rename_action = menu.addAction("重命名")
            move_action = menu.addAction("移动")
            delete_action = menu.addAction("删除")
            menu.addSeparator()
        new_folder_action = menu.addAction("新建文件夹")

        action = menu.exec_(self.file_table.viewport().mapToGlobal(position))
        if action is None:
            return
        if action == open_action:
            self.open_selected_entry()
        elif action == rename_action:
            self.rename_remote_entry()
        elif action == move_action:
            self.move_remote_entry()
        elif action == delete_action:
            self.delete_remote_entry()
        elif action == new_folder_action:
            self.create_remote_folder()

    def create_remote_folder(self):
        folder_name, ok = prompt_text(self, "新建文件夹", "请输入新文件夹名称：")
        if not ok or not folder_name:
            return
        try:
            self.client.create_folder(self.current_remote_dir, folder_name)
        except Exception as exc:
            show_warning(self, "新建失败", str(exc))
            return
        self.refresh_files()

    def rename_remote_entry(self):
        entry = self.selected_remote_entry()
        if not entry:
            show_info(self, "请选择项目", "请先选择一个文件或文件夹，再执行重命名。")
            return
        new_name, ok = prompt_text(self, "重命名", "请输入新的名称：", entry["name"])
        if not ok or not new_name or new_name == entry["name"]:
            return
        try:
            self.client.rename_entry(entry["path"], new_name)
        except Exception as exc:
            show_warning(self, "重命名失败", str(exc))
            return
        self.refresh_files()

    def move_remote_entry(self):
        entry = self.selected_remote_entry()
        if not entry:
            show_info(self, "请选择项目", "请先选择一个文件或文件夹，再执行移动。")
            return
        target_dir, ok = prompt_text(
            self,
            "移动项目",
            "请输入目标目录，相对根目录；留空表示移动到根目录：",
            self.current_remote_dir,
        )
        if not ok:
            return
        try:
            self.client.move_entry(entry["path"], target_dir)
        except Exception as exc:
            show_warning(self, "移动失败", str(exc))
            return
        self.refresh_files()

    def move_remote_entry_to_dir(self, source_path, target_dir):
        if not source_path or not target_dir:
            return
        if source_path == target_dir or source_path.startswith(target_dir + "/"):
            return
        try:
            self.client.move_entry(source_path, target_dir)
        except Exception as exc:
            show_warning(self, "移动失败", str(exc))
            return
        self.refresh_files()

    def delete_remote_entry(self):
        entry = self.selected_remote_entry()
        if not entry:
            show_info(self, "请选择项目", "请先选择一个文件或文件夹，再执行删除。")
            return
        noun = "文件夹" if entry.get("is_dir") else "文件"
        if not ask_confirm(
            self,
            f"删除{noun}",
            f"确认删除 {entry['name']} 吗？此操作不可恢复。",
        ):
            return
        try:
            self.client.delete_entry(entry["path"])
        except Exception as exc:
            show_warning(self, "删除失败", str(exc))
            return
        self.refresh_files()

    def start_upload(self, file_path):
        path = Path(file_path)
        remote_path = self._join_remote_path(self.current_remote_dir, path.name)
        meta = {
            "task_id": uuid.uuid4().hex,
            "mode": "upload",
            "local_path": str(path),
            "remote_name": remote_path,
            "save_path": "",
            "title": f"上传 {path.name}",
            "thread_count": self.thread_spin.value(),
            "chunk_size": 1024 * 1024,
            "progress": 0,
            "speed": "0 B/s",
            "status": "等待中",
        }
        entry = self.add_task_entry(meta)
        self.start_task(entry, resumed=False)

    def start_download(self, remote_name, save_path):
        meta = {
            "task_id": uuid.uuid4().hex,
            "mode": "download",
            "local_path": "",
            "remote_name": remote_name,
            "save_path": str(Path(save_path)),
            "title": f"下载 {self._basename(remote_name)}",
            "thread_count": self.thread_spin.value(),
            "chunk_size": 1024 * 1024,
            "progress": 0,
            "speed": "0 B/s",
            "status": "等待中",
        }
        entry = self.add_task_entry(meta)
        self.start_task(entry, resumed=False)

    def restore_saved_tasks(self):
        restored = self.state_store.load_tasks(self.client.server_text, self.client.username)
        for meta in restored:
            try:
                if not isinstance(meta, dict) or meta.get("mode") not in {"upload", "download"}:
                    continue
                meta.setdefault("title", self.default_title(meta))
                meta.setdefault("status", "已暂停")
                meta.setdefault("progress", 0)
                meta.setdefault("speed", "等待恢复")
                meta.setdefault("local_path", "")
                meta.setdefault("remote_name", "")
                meta.setdefault("save_path", "")
                meta.setdefault("thread_count", self.thread_spin.value())
                meta.setdefault("chunk_size", 1024 * 1024)
                entry = self.add_task_entry(meta)
                self.prepare_restored_entry(entry)
            except Exception:
                continue
        if restored:
            self.persist_settings()

    def add_task_entry(self, meta):
        item = QListWidgetItem()
        widget = TransferItem(meta["title"])
        item.setSizeHint(widget.sizeHint())
        self.transfer_list.insertItem(0, item)
        self.transfer_list.setItemWidget(item, widget)

        entry = {
            "meta": dict(meta),
            "item": item,
            "widget": widget,
            "task": None,
        }
        self.task_entries.insert(0, entry)

        widget.pause_clicked.connect(lambda current_entry=entry: self.toggle_task_pause(current_entry))
        widget.remove_clicked.connect(lambda current_entry=entry: self.remove_task_entry(current_entry))
        self.apply_entry_visuals(entry)
        self.update_task_summary()
        self.update_empty_states()
        self.persist_tasks(force=True)
        return entry

    def default_title(self, meta):
        if meta.get("mode") == "upload":
            filename = Path(meta.get("local_path", "")).name or self._basename(meta.get("remote_name", "未知文件"))
            return f"上传 {filename}"
        return f"下载 {self._basename(meta.get('remote_name', '未知文件'))}"

    def prepare_restored_entry(self, entry):
        meta = entry["meta"]
        if meta["mode"] == "upload" and not Path(meta["local_path"]).exists():
            meta["status"] = "本地文件不存在"
            meta["speed"] = "-"
            entry["widget"].set_pause_enabled(False)
        else:
            meta["status"] = "已暂停"
            entry["widget"].set_paused(True)
            entry["widget"].set_pause_enabled(True)
        entry["widget"].set_remove_enabled(True)
        self.apply_entry_visuals(entry)

    def apply_entry_visuals(self, entry):
        meta = entry["meta"]
        widget = entry["widget"]
        widget.set_status(meta.get("status", "等待中"))
        widget.set_progress(int(meta.get("progress", 0)))
        widget.set_speed(meta.get("speed", "0 B/s"))
        paused = meta.get("status") in RESTORABLE_STATUSES or meta.get("status") == "已暂停"
        widget.set_paused(paused)
        widget.set_pause_enabled(meta.get("status") != "本地文件不存在")
        widget.set_remove_enabled(entry["task"] is None or not entry["task"].isRunning())
        if meta.get("status") == "已完成":
            widget.set_finished()
        self.update_task_summary()

    def build_task(self, meta):
        return TransferTask(
            self.client,
            mode=meta["mode"],
            local_path=meta.get("local_path") or None,
            remote_name=meta.get("remote_name") or None,
            save_path=meta.get("save_path") or None,
            thread_count=int(meta.get("thread_count", self.thread_spin.value())),
            chunk_size=int(meta.get("chunk_size", 1024 * 1024)),
        )

    def start_task(self, entry, resumed):
        meta = entry["meta"]
        if meta["mode"] == "upload" and not Path(meta["local_path"]).exists():
            meta["status"] = "本地文件不存在"
            meta["speed"] = "-"
            self.apply_entry_visuals(entry)
            self.persist_tasks(force=True)
            show_warning(self, "无法继续", f"本地文件不存在：\n{meta['local_path']}")
            return

        task = self.build_task(meta)
        entry["task"] = task
        entry["widget"].set_pause_enabled(True)
        entry["widget"].set_remove_enabled(False)
        entry["widget"].set_paused(False)
        meta["status"] = "准备上传" if meta["mode"] == "upload" else "准备下载"
        if resumed:
            meta["speed"] = "恢复中"
        self.apply_entry_visuals(entry)

        task.progress_changed.connect(lambda value, current_entry=entry: self.on_task_progress(current_entry, value))
        task.speed_changed.connect(lambda value, current_entry=entry: self.on_task_speed(current_entry, value))
        task.status_changed.connect(lambda value, current_entry=entry: self.on_task_status(current_entry, value))
        task.completed.connect(
            lambda success, message, current_entry=entry: self.finish_task(current_entry, success, message)
        )
        task.start()
        self.persist_tasks(force=True)

    def on_task_progress(self, entry, value):
        entry["meta"]["progress"] = value
        entry["widget"].set_progress(value)
        self.persist_tasks()

    def on_task_speed(self, entry, value):
        entry["meta"]["speed"] = value
        entry["widget"].set_speed(value)
        self.persist_tasks()

    def on_task_status(self, entry, value):
        entry["meta"]["status"] = value
        entry["widget"].set_status(value)
        if value == "已暂停":
            entry["widget"].set_paused(True)
            entry["widget"].set_remove_enabled(True)
            self.persist_tasks(force=True)
        elif value in ACTIVE_STATUSES:
            entry["widget"].set_paused(False)
            entry["widget"].set_remove_enabled(False)
        elif value == "失败":
            entry["widget"].set_remove_enabled(True)
            self.persist_tasks(force=True)
        self.update_task_summary()

    def finish_task(self, entry, success, message):
        entry["task"] = None
        if not success and message == "__paused__":
            entry["meta"]["status"] = "已暂停"
            entry["widget"].set_status("已暂停")
            entry["widget"].set_pause_enabled(True)
            entry["widget"].set_paused(True)
            entry["widget"].set_remove_enabled(True)
            self.persist_tasks(force=True)
            return
        if not success and message == "__stopped__":
            self.persist_tasks(force=True)
            return
        if success:
            entry["meta"]["status"] = "已完成"
            entry["meta"]["progress"] = 100
            self.refresh_files()
            entry["widget"].set_finished()
        else:
            entry["meta"]["status"] = "失败"
            entry["widget"].set_pause_enabled(True)
            entry["widget"].set_paused(True)
            show_warning(self, "传输失败", message)
        entry["widget"].set_status(entry["meta"]["status"])
        entry["widget"].set_progress(int(entry["meta"]["progress"]))
        entry["widget"].set_remove_enabled(True)
        self.update_task_summary()
        self.update_empty_states()
        self.persist_tasks(force=True)

    def toggle_task_pause(self, entry):
        task = entry["task"]
        if task and task.isRunning():
            task.pause()
            entry["meta"]["status"] = "已暂停"
            entry["widget"].set_paused(True)
            entry["widget"].set_remove_enabled(False)
            self.persist_tasks(force=True)
            return

        if task and not task.isRunning():
            entry["task"] = None

        self.start_task(entry, resumed=True)

    def remove_task_entry(self, entry):
        task = entry["task"]
        if task and task.isRunning():
            show_info(self, "请先暂停任务", "正在传输的任务不能直接移除，请先暂停后再移除。")
            return
        self.cleanup_local_artifacts(entry["meta"])
        row = self.transfer_list.row(entry["item"])
        if row >= 0:
            self.transfer_list.takeItem(row)
        self.task_entries = [item for item in self.task_entries if item is not entry]
        self.update_task_summary()
        self.update_empty_states()
        self.persist_tasks(force=True)

    def cleanup_local_artifacts(self, meta):
        if meta.get("mode") != "download":
            return
        raw_save_path = meta.get("save_path") or ""
        if not raw_save_path:
            return
        save_path = Path(raw_save_path)
        cache_dir = save_path.parent / f".{save_path.name}.parts"
        temp_file = save_path.with_suffix(save_path.suffix + ".downloading")
        if cache_dir.exists():
            import shutil

            shutil.rmtree(cache_dir, ignore_errors=True)
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)

    def clear_finished_tasks(self):
        removable = [
            entry
            for entry in list(self.task_entries)
            if entry["meta"].get("status") in {"已完成", "失败", "本地文件不存在"}
        ]
        for entry in removable:
            self.remove_task_entry(entry)

    def persist_tasks(self, force=False, for_shutdown=False):
        now = time.monotonic()
        if not force and now - self._last_persist_time < 1.0:
            return
        tasks = []
        for entry in self.task_entries:
            meta = dict(entry["meta"])
            task = entry["task"]
            if task and task.isRunning() and for_shutdown:
                meta["status"] = "已暂停"
            if meta.get("status") == "已完成":
                continue
            tasks.append(meta)
        self.state_store.save_tasks(self.client.server_text, self.client.username, tasks)
        self.state_store.save_settings(
            last_server=self.client.server_text,
            thread_count=self.thread_spin.value(),
        )
        self._last_persist_time = now

    def update_task_summary(self):
        total = len(self.task_entries)
        active = sum(1 for entry in self.task_entries if entry["meta"].get("status") in ACTIVE_STATUSES)
        paused = sum(
            1
            for entry in self.task_entries
            if entry["meta"].get("status") in RESTORABLE_STATUSES or entry["meta"].get("status") == "已暂停"
        )
        self.task_summary_label.setText(f"传输任务 {total} 项 | 活动 {active} | 待恢复 {paused}")
        self.task_section_badge.setText(f"活动 {active} / 恢复 {paused}")
        self.update_empty_states()

    def closeEvent(self, event: QCloseEvent):
        if self._tray_mode_enabled and not self._allow_tray_exit:
            event.ignore()
            self.hide()
            return
        for entry in self.task_entries:
            task = entry["task"]
            if task and task.isRunning():
                task.pause()
                task.wait(2000)
                entry["meta"]["status"] = "已暂停"
                entry["task"] = None
                entry["widget"].set_paused(True)
                entry["widget"].set_remove_enabled(True)
        self.persist_tasks(force=True, for_shutdown=True)
        self._allow_tray_exit = False
        super().closeEvent(event)
