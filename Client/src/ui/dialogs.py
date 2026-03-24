from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from common.app_meta import format_window_title


TONE_MAP = {
    "info": {
        "chip_bg": "rgba(28, 127, 120, 0.14)",
        "chip_fg": "#176f67",
        "title_fg": "#173042",
    },
    "warning": {
        "chip_bg": "rgba(216, 119, 51, 0.16)",
        "chip_fg": "#9b4f22",
        "title_fg": "#173042",
    },
    "error": {
        "chip_bg": "rgba(182, 63, 42, 0.14)",
        "chip_fg": "#9d3526",
        "title_fg": "#173042",
    },
}


class StyledMessageDialog(QDialog):
    def __init__(self, parent, title, message, tone="info"):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(format_window_title(title))
        self.setMinimumWidth(420)
        palette = TONE_MAP.get(tone, TONE_MAP["info"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(12)

        badge = QLabel(title[:2] if len(title) >= 2 else "提示")
        badge.setObjectName("toneBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setMinimumSize(48, 48)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        body_label = QLabel(message)
        body_label.setObjectName("bodyLabel")
        body_label.setWordWrap(True)
        text_wrap.addWidget(title_label)
        text_wrap.addWidget(body_label)

        hero_layout.addWidget(badge)
        hero_layout.addLayout(text_wrap, 1)
        layout.addWidget(hero)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setText("知道了")
        ok_button.setProperty("variant", "primary")
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.setStyleSheet(
            f"""
            QDialog {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #fff4e7,
                    stop: 0.5 #edf7f4,
                    stop: 1 #e0edf7
                );
                color: #173042;
                font-size: 13px;
            }}
            QFrame#heroCard {{
                background: rgba(255, 255, 255, 0.95);
                border: 1px solid rgba(23, 48, 66, 0.10);
                border-radius: 18px;
            }}
            QLabel#toneBadge {{
                background: {palette["chip_bg"]};
                color: {palette["chip_fg"]};
                border-radius: 14px;
                font-size: 15px;
                font-weight: 800;
                padding: 6px;
            }}
            QLabel#titleLabel {{
                color: {palette["title_fg"]};
                font-size: 18px;
                font-weight: 800;
            }}
            QLabel#bodyLabel {{
                color: #587082;
                line-height: 1.45;
            }}
            QPushButton {{
                border: none;
                border-radius: 12px;
                padding: 10px 18px;
                font-weight: 600;
                min-width: 96px;
            }}
            QPushButton[variant="primary"] {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #dd8034,
                    stop: 1 #c75728
                );
                color: white;
            }}
            QPushButton[variant="primary"]:hover {{
                background: #b94a22;
            }}
            """
        )


def show_info(parent, title, message):
    return StyledMessageDialog(parent, title, message, tone="info").exec_()


def show_warning(parent, title, message):
    return StyledMessageDialog(parent, title, message, tone="warning").exec_()


def show_error(parent, title, message):
    return StyledMessageDialog(parent, title, message, tone="error").exec_()


class StyledConfirmDialog(QDialog):
    def __init__(self, parent, title, message, tone="warning"):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(format_window_title(title))
        self.setMinimumWidth(440)
        palette = TONE_MAP.get(tone, TONE_MAP["warning"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(12)

        badge = QLabel("确认")
        badge.setObjectName("toneBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setMinimumSize(56, 48)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        body_label = QLabel(message)
        body_label.setObjectName("bodyLabel")
        body_label.setWordWrap(True)
        text_wrap.addWidget(title_label)
        text_wrap.addWidget(body_label)

        hero_layout.addWidget(badge)
        hero_layout.addLayout(text_wrap, 1)
        layout.addWidget(hero)

        buttons = QDialogButtonBox()
        cancel_button = QPushButton("取消")
        confirm_button = QPushButton("确认")
        cancel_button.setProperty("variant", "secondary")
        confirm_button.setProperty("variant", "primary")
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)
        buttons.addButton(confirm_button, QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setStyleSheet(
            f"""
            QDialog {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #fff4e7,
                    stop: 0.5 #edf7f4,
                    stop: 1 #e0edf7
                );
                color: #173042;
                font-size: 13px;
            }}
            QFrame#heroCard {{
                background: rgba(255, 255, 255, 0.95);
                border: 1px solid rgba(23, 48, 66, 0.10);
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
            }}
            QLabel#toneBadge {{
                background: {palette["chip_bg"]};
                color: {palette["chip_fg"]};
                border-radius: 14px;
                font-size: 15px;
                font-weight: 800;
                padding: 6px;
            }}
            QLabel#titleLabel {{
                color: {palette["title_fg"]};
                font-size: 18px;
                font-weight: 800;
            }}
            QLabel#bodyLabel {{
                color: #587082;
            }}
            QPushButton {{
                border: none;
                border-radius: 12px;
                padding: 10px 18px;
                font-weight: 600;
                min-width: 96px;
            }}
            QPushButton[variant="primary"] {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #dd8034,
                    stop: 1 #c75728
                );
                color: white;
            }}
            QPushButton[variant="secondary"] {{
                background: rgba(20, 53, 77, 0.10);
                color: #173042;
            }}
            """
        )


def ask_confirm(parent, title, message, tone="warning"):
    return StyledConfirmDialog(parent, title, message, tone=tone).exec_() == QDialog.Accepted


FILE_DIALOG_STYLE = """
QFileDialog, QWidget {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #fff4e7,
        stop: 0.5 #edf7f4,
        stop: 1 #e0edf7
    );
    color: #173042;
    font-size: 13px;
}
QLabel {
    background: transparent;
    color: #315164;
    font-weight: 600;
}
QLineEdit, QComboBox, QListView, QTreeView {
    background: rgba(255, 255, 255, 0.96);
    color: #173042;
    border: 1px solid #d7e1e6;
    border-radius: 12px;
    padding: 8px 10px;
}
QPushButton {
    border: none;
    border-radius: 12px;
    padding: 9px 16px;
    font-weight: 600;
    background: rgba(20, 53, 77, 0.10);
    color: #173042;
}
QPushButton:hover {
    background: rgba(20, 53, 77, 0.16);
}
QHeaderView::section {
    background: #edf5f6;
    color: #315164;
    border: none;
    border-bottom: 1px solid #d7e1e6;
    padding: 10px 8px;
    font-weight: 700;
}
"""


def choose_open_file(parent, title, directory=""):
    dialog = QFileDialog(parent, format_window_title(title), directory)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setFileMode(QFileDialog.ExistingFile)
    dialog.setNameFilter("所有文件 (*)")
    dialog.setStyleSheet(FILE_DIALOG_STYLE)
    if dialog.exec_() != QDialog.Accepted:
        return ""
    files = dialog.selectedFiles()
    return files[0] if files else ""


def choose_save_file(parent, title, default_name=""):
    dialog = QFileDialog(parent, format_window_title(title))
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setAcceptMode(QFileDialog.AcceptSave)
    dialog.setNameFilter("所有文件 (*)")
    dialog.selectFile(default_name)
    dialog.setStyleSheet(FILE_DIALOG_STYLE)
    if dialog.exec_() != QDialog.Accepted:
        return ""
    files = dialog.selectedFiles()
    return files[0] if files else ""


def prompt_text(parent, title, label, text=""):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(format_window_title(title))
    dialog.setLabelText(label)
    dialog.setTextValue(text)
    dialog.setStyleSheet(FILE_DIALOG_STYLE)
    if dialog.exec_() != QDialog.Accepted:
        return ("", False)
    return (dialog.textValue().strip(), True)
