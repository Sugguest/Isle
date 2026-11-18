"""Иконка приложения, нарисованная кодом (без внешних файлов)."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QLinearGradient, QPainter, QPixmap


def make_icon_image(size: int = 256) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    qp = QPainter(img)
    qp.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor("#6d79ff"))
    g.setColorAt(1, QColor("#3c45a5"))
    qp.setPen(Qt.NoPen)
    qp.setBrush(g)
    qp.drawRoundedRect(QRectF(0, 0, size, size), size * 0.26, size * 0.26)
    heights = [0.26, 0.48, 0.68, 0.42, 0.24]
    bw, gap = size * 0.088, size * 0.062
    total = len(heights) * bw + (len(heights) - 1) * gap
    x = (size - total) / 2
    qp.setBrush(QColor("white"))
    for h in heights:
        hh = size * h
        qp.drawRoundedRect(QRectF(x, (size - hh) / 2, bw, hh), bw / 2, bw / 2)
        x += bw + gap
    qp.end()
    return img


def make_pixmap(size: int) -> QPixmap:
    return QPixmap.fromImage(make_icon_image(max(size, 64)).scaled(
        size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))


def make_app_icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(make_pixmap(s))
    return ic
