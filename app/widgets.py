"""Виджеты в стиле Discord: переключатель, сегменты, карточки, кнопки рейла."""
from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QPointF, QPropertyAnimation, QRectF,
                            Qt, QVariantAnimation, Property, Signal)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from . import theme as T


def mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(round(a.red() + (b.red() - a.red()) * t),
                  round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


class Toggle(QAbstractButton):
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(40, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._k = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._k)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def getKnob(self): return self._k
    def setKnob(self, v): self._k = v; self.update()
    knob = Property(float, getKnob, setKnob)

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        track = mix(QColor("#80848e"), QColor(T.GREEN), self._k)
        qp.setPen(Qt.NoPen)
        qp.setBrush(track)
        qp.drawRoundedRect(QRectF(0, 0, 40, 24), 12, 12)
        cx = 12 + 16 * self._k
        qp.setBrush(QColor("white"))
        qp.drawEllipse(QPointF(cx, 12), 9, 9)
        qp.setPen(QPen(track, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if self._k > 0.5:
            qp.drawPolyline([QPointF(cx - 3.2, 12.2), QPointF(cx - 0.8, 14.4), QPointF(cx + 3.4, 9.6)])
        else:
            qp.drawLine(QPointF(cx - 2.8, 9.2), QPointF(cx + 2.8, 14.8))
            qp.drawLine(QPointF(cx - 2.8, 14.8), QPointF(cx + 2.8, 9.2))


class Segmented(QWidget):
    changed = Signal(str)

    def __init__(self, options, value, parent=None):
        super().__init__(parent)
        self.setObjectName("SegBox")
        self.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(self)
        h.setContentsMargins(3, 3, 3, 3)
        h.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for val, label in options:
            b = QPushButton(label)
            b.setObjectName("Seg")
            b.setCheckable(True)
            b.setChecked(val == value)
            b.setCursor(Qt.PointingHandCursor)
            self._group.addButton(b)
            b.clicked.connect(lambda _=False, v=val: self.changed.emit(v))
            h.addWidget(b)


def Button(text, primary=False) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("Primary" if primary else "Btn")
    b.setCursor(Qt.PointingHandCursor)
    return b


class Card(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Card")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        self._n = 0

    def add_row(self, title, desc, control):
        if self._n:
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(16, 0, 16, 0)
            line = QFrame()
            line.setObjectName("Divider")
            line.setFixedHeight(1)
            wl.addWidget(line)
            self._lay.addWidget(wrap)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("RowTitle")
        left.addWidget(t)
        if desc:
            d = QLabel(desc)
            d.setObjectName("RowDesc")
            d.setWordWrap(True)
            left.addWidget(d)
        h.addLayout(left, 1)
        if control is not None:
            h.addWidget(control, 0, Qt.AlignVCenter)
        self._lay.addWidget(row)
        self._n += 1


class RailButton(QAbstractButton):
    """Круглая иконка слева, как «серверы» в Discord: при наведении становится квадратом."""

    def __init__(self, kind, tooltip, accent=T.BRAND, selectable=True):
        super().__init__()
        self.kind, self.accent = kind, QColor(accent)
        self.setCheckable(selectable)
        self.setFixedSize(72, 52)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = 0.0
        self._sel = 1.0 if self.isChecked() else 0.0
        self._anims = {}
        self.toggled.connect(lambda on: self._go("_sel", 1.0 if on else 0.0))

    def _go(self, name, target):
        old = self._anims.get(name)
        if old:
            old.stop()
        a = QVariantAnimation(self)
        a.setDuration(170)
        a.setStartValue(getattr(self, name))
        a.setEndValue(target)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.valueChanged.connect(lambda v, n=name: (setattr(self, n, float(v)), self.update()))
        self._anims[name] = a
        a.start()

    def enterEvent(self, e): self._go("_hover", 1.0)
    def leaveEvent(self, e): self._go("_hover", 0.0)

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        t = max(self._hover, self._sel)
        cy = self.height() / 2
        qp.setPen(Qt.NoPen)
        qp.setBrush(QColor("white"))
        ih = 20 * self._hover + 20 * self._sel
        if ih > 1:
            qp.drawRoundedRect(QRectF(-4, cy - ih / 2, 8, ih), 4, 4)
        rad = 24 - 8 * t
        qp.setBrush(mix(QColor(T.BG1), self.accent, t))
        qp.drawRoundedRect(QRectF(12, cy - 24, 48, 48), rad, rad)
        icol = mix(self.accent if self.kind == "plus" else QColor(T.TEXT), QColor("white"), t)
        c = QPointF(36, cy)
        qp.setBrush(Qt.NoBrush)
        if self.kind == "logo":
            qp.setPen(Qt.NoPen)
            qp.setBrush(icol)
            for i, h in enumerate([10, 20, 28, 16, 8]):
                qp.drawRoundedRect(QRectF(c.x() - 17 + i * 7.2, cy - h / 2, 4, h), 2, 2)
        elif self.kind == "plus":
            qp.setPen(QPen(icol, 2.6, Qt.SolidLine, Qt.RoundCap))
            qp.drawLine(QPointF(c.x() - 8, cy), QPointF(c.x() + 8, cy))
            qp.drawLine(QPointF(c.x(), cy - 8), QPointF(c.x(), cy + 8))
        elif self.kind == "gear":
            qp.setPen(QPen(icol, 2.4, Qt.SolidLine, Qt.RoundCap))
            qp.drawEllipse(c, 6.5, 6.5)
            qp.setPen(QPen(icol, 3.2, Qt.SolidLine, Qt.RoundCap))
            qp.translate(c)
            for _i in range(8):
                qp.drawLine(QPointF(0, -9.5), QPointF(0, -11.5))
                qp.rotate(45)
