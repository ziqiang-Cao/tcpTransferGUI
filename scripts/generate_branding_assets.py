from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

from project_root import resolve_project_root


PROJECT_ROOT = resolve_project_root(__file__)
ASSET_DIR = PROJECT_ROOT / "assets" / "branding"
APP = None


def ensure_app():
    global APP
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    APP = app
    return APP


def background_gradient(rect):
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#12354d"))
    gradient.setColorAt(0.55, QColor("#1b6a73"))
    gradient.setColorAt(1.0, QColor("#dd7740"))
    return gradient


def draw_icon(size):
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)

    rect = QRectF(0, 0, size, size)
    painter.setPen(Qt.NoPen)
    painter.setBrush(background_gradient(rect))
    painter.drawRoundedRect(rect.adjusted(8, 8, -8, -8), size * 0.2, size * 0.2)

    card = QRectF(size * 0.16, size * 0.18, size * 0.68, size * 0.62)
    painter.setBrush(QColor(255, 255, 255, 245))
    painter.drawRoundedRect(card, size * 0.1, size * 0.1)

    tab = QRectF(size * 0.24, size * 0.12, size * 0.28, size * 0.14)
    painter.setBrush(QColor(255, 226, 192, 240))
    painter.drawRoundedRect(tab, size * 0.05, size * 0.05)

    path = QPainterPath()
    path.moveTo(size * 0.34, size * 0.48)
    path.lineTo(size * 0.50, size * 0.34)
    path.lineTo(size * 0.66, size * 0.48)
    path.lineTo(size * 0.58, size * 0.48)
    path.lineTo(size * 0.58, size * 0.66)
    path.lineTo(size * 0.42, size * 0.66)
    path.lineTo(size * 0.42, size * 0.48)
    path.closeSubpath()
    painter.setBrush(QColor("#1f8a7e"))
    painter.drawPath(path)

    painter.setPen(QPen(QColor("#ef9352"), max(6, size // 42), Qt.SolidLine, Qt.RoundCap))
    painter.drawArc(
        int(size * 0.28),
        int(size * 0.44),
        int(size * 0.44),
        int(size * 0.30),
        25 * 16,
        130 * 16,
    )

    painter.end()
    return image


def draw_banner(width, height):
    image = QImage(width, height, QImage.Format_RGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)

    rect = QRectF(0, 0, width, height)
    painter.fillRect(rect, background_gradient(rect))

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 255, 255, 28))
    painter.drawEllipse(QPointF(width * 0.18, height * 0.18), width * 0.38, width * 0.38)
    painter.drawEllipse(QPointF(width * 0.84, height * 0.82), width * 0.42, width * 0.42)

    icon = draw_icon(min(width - 36, 120))
    painter.drawImage(int((width - icon.width()) / 2), 22, icon)

    painter.setPen(QColor("#ffffff"))
    title_font = QFont("DejaVu Sans", 18)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.drawText(QRectF(18, 160, width - 36, 60), Qt.TextWordWrap | Qt.AlignHCenter, "TCPTransGUI")

    subtitle_font = QFont("DejaVu Sans", 9)
    painter.setFont(subtitle_font)
    painter.setPen(QColor(245, 250, 252, 220))
    painter.drawText(
        QRectF(18, 214, width - 36, 74),
        Qt.TextWordWrap | Qt.AlignHCenter,
        "Secure transfer\nResumable tasks\nServer & client",
    )

    painter.end()
    return image


def draw_header(width, height):
    image = QImage(width, height, QImage.Format_RGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = QRectF(0, 0, width, height)
    painter.fillRect(rect, background_gradient(rect))
    icon = draw_icon(min(width, height) - 10)
    painter.drawImage(int((width - icon.width()) / 2), int((height - icon.height()) / 2), icon)
    painter.end()
    return image


def main():
    ensure_app()
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    icon = draw_icon(512)
    if not icon.save(str(ASSET_DIR / "app_icon.png"), "PNG"):
        raise SystemExit("failed to write app_icon.png")
    if not icon.save(str(ASSET_DIR / "app_icon.ico"), "ICO"):
        raise SystemExit("failed to write app_icon.ico")

    banner = draw_banner(164, 314)
    if not banner.save(str(ASSET_DIR / "installer_banner.bmp"), "BMP"):
        raise SystemExit("failed to write installer_banner.bmp")

    header = draw_header(55, 55)
    if not header.save(str(ASSET_DIR / "installer_header.bmp"), "BMP"):
        raise SystemExit("failed to write installer_header.bmp")


if __name__ == "__main__":
    main()
