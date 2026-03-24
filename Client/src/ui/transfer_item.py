from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget


class TransferItem(QWidget):
    pause_clicked = pyqtSignal()
    remove_clicked = pyqtSignal()

    def __init__(self, title):
        super().__init__()
        self.setObjectName("transferCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleLabel")
        self.title_label.setWordWrap(True)
        self.status_label = QLabel("等待中")
        self.status_label.setObjectName("detailLabel")
        self.status_chip = QLabel("等待中")
        self.status_chip.setAlignment(Qt.AlignCenter)
        self.status_chip.setObjectName("statusChip")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setTextVisible(True)
        self.pause_button = QPushButton("暂停")
        self.pause_button.setCursor(Qt.PointingHandCursor)
        self.pause_button.setProperty("variant", "secondary")
        self.pause_button.setMinimumHeight(32)
        self.pause_button.clicked.connect(self.pause_clicked.emit)
        self.remove_button = QPushButton("移除")
        self.remove_button.setCursor(Qt.PointingHandCursor)
        self.remove_button.setProperty("variant", "ghost")
        self.remove_button.setMinimumHeight(32)
        self.remove_button.clicked.connect(self.remove_clicked.emit)
        self.speed_label = QLabel("0 B/s")
        self.speed_label.setAlignment(Qt.AlignRight)
        self.speed_label.setObjectName("speedLabel")

        top_row = QHBoxLayout()
        top_row.addWidget(self.title_label, 1)
        top_row.addWidget(self.status_chip)

        footer = QHBoxLayout()
        footer.addWidget(self.pause_button)
        footer.addWidget(self.remove_button)
        footer.addStretch(1)
        footer.addWidget(self.speed_label)

        layout.addLayout(top_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addLayout(footer)

        self.setStyleSheet(
            """
            QWidget#transferCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgba(255, 255, 255, 0.99),
                    stop: 0.6 rgba(244, 249, 250, 0.99),
                    stop: 1 rgba(255, 244, 234, 0.95)
                );
                border: 1px solid rgba(19, 72, 89, 0.09);
                border-radius: 18px;
            }
            QLabel#titleLabel {
                font-size: 14px;
                font-weight: 700;
                color: #173042;
            }
            QLabel#detailLabel {
                color: #5a7283;
            }
            QLabel#statusChip {
                min-width: 72px;
                padding: 5px 10px;
                border-radius: 11px;
                font-size: 12px;
                font-weight: 700;
                background: rgba(23, 48, 66, 0.08);
                color: #315164;
            }
            QLabel#statusChip[tone="active"] {
                background: rgba(38, 135, 124, 0.14);
                color: #15675e;
            }
            QLabel#statusChip[tone="paused"] {
                background: rgba(214, 126, 53, 0.16);
                color: #9e5221;
            }
            QLabel#statusChip[tone="danger"] {
                background: rgba(182, 63, 42, 0.14);
                color: #9d3526;
            }
            QLabel#statusChip[tone="success"] {
                background: rgba(72, 156, 106, 0.16);
                color: #23724c;
            }
            QLabel#speedLabel {
                color: #1b5666;
                font-weight: 600;
            }
            QProgressBar {
                border: 1px solid rgba(23, 48, 66, 0.08);
                border-radius: 9px;
                background: #edf4f5;
                text-align: center;
                min-height: 19px;
                color: #173042;
                font-weight: 700;
            }
            QProgressBar::chunk {
                border-radius: 9px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #23908b,
                    stop: 1 #4ebc86
                );
            }
            QProgressBar[tone="paused"]::chunk {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #d9822b,
                    stop: 1 #f0aa47
                );
            }
            QProgressBar[tone="danger"]::chunk {
                background: #bf5f49;
            }
            QProgressBar[tone="success"]::chunk {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #2b8f64,
                    stop: 1 #61be82
                );
            }
            QPushButton {
                border: none;
                border-radius: 11px;
                padding: 7px 13px;
                font-weight: 600;
            }
            QPushButton[variant="secondary"] {
                background: rgba(23, 48, 66, 0.10);
                color: #173042;
            }
            QPushButton[variant="secondary"]:hover {
                background: rgba(23, 48, 66, 0.16);
            }
            QPushButton[variant="ghost"] {
                background: rgba(191, 95, 73, 0.10);
                color: #8d3e2a;
            }
            QPushButton[variant="ghost"]:hover {
                background: rgba(191, 95, 73, 0.18);
            }
            QPushButton:disabled {
                background: #ced7dd;
                color: #7c909d;
            }
            """
        )
        self._apply_tone("neutral")

    def set_status(self, text):
        self.status_label.setText(text)
        self.status_chip.setText(text)
        if text == "已完成":
            tone = "success"
        elif text in {"失败", "本地文件不存在"}:
            tone = "danger"
        elif text in {"已暂停", "等待恢复"}:
            tone = "paused"
        elif text in {"准备上传", "准备下载", "上传中", "下载中"}:
            tone = "active"
        else:
            tone = "neutral"
        self._apply_tone(tone)

    def set_progress(self, value):
        self.progress_bar.setValue(value)

    def set_speed(self, text):
        self.speed_label.setText(text)

    def set_paused(self, paused):
        self.pause_button.setText("继续" if paused else "暂停")

    def set_finished(self):
        self.pause_button.setEnabled(False)
        self._apply_tone("success")

    def set_pause_enabled(self, enabled):
        self.pause_button.setEnabled(enabled)

    def set_remove_enabled(self, enabled):
        self.remove_button.setEnabled(enabled)

    def _apply_tone(self, tone):
        self.status_chip.setProperty("tone", tone)
        self.progress_bar.setProperty("tone", tone)
        self.status_chip.style().unpolish(self.status_chip)
        self.status_chip.style().polish(self.status_chip)
        self.progress_bar.style().unpolish(self.progress_bar)
        self.progress_bar.style().polish(self.progress_bar)
