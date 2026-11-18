"""Новогоднее оформление: падающий снег (отлетает от курсора) и сугробы на кнопках, карточках и островке."""
import math
import random
import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QRegion
from PySide6.QtWidgets import QWidget

from .widgets import RailButton

SNOW = QColor(247, 250, 255)
SHADE = QColor(160, 184, 224, 210)


def snow_cap_path(x0, x1, y, hmax, seed, taper=10.0, drop=1.5) -> QPainterPath:
    """Сугроб вдоль верхней кромки: от x0 до x1 по линии y, высота до hmax, к краям сходит на нет."""
    taper = max(2.0, min(taper, (x1 - x0) / 2))
    n = max(3, int((x1 - x0) / 5))
    pts = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        edge = math.sin(min(1.0, (x - x0) / taper, (x1 - x) / taper) * math.pi / 2)
        noise = 0.55 + 0.45 * (0.6 * math.sin(x * 0.075 + seed) + 0.4 * math.sin(x * 0.21 + seed * 2.3))
        pts.append(QPointF(x, y - hmax * max(0.2, noise) * edge))
    path = QPainterPath()
    path.moveTo(x0, y + drop)
    path.lineTo(pts[0])
    for i in range(1, len(pts) - 1):
        path.quadTo(pts[i], QPointF((pts[i].x() + pts[i + 1].x()) / 2, (pts[i].y() + pts[i + 1].y()) / 2))
    path.lineTo(pts[-1])
    path.lineTo(x1, y + drop)
    path.closeSubpath()
    return path


def draw_cap(qp: QPainter, path: QPainterPath):
    qp.save()
    qp.setPen(Qt.NoPen)
    qp.translate(0, 1.3)
    qp.setBrush(SHADE)
    qp.drawPath(path)
    qp.translate(0, -1.3)
    qp.setBrush(SNOW)
    qp.drawPath(path)
    qp.restore()


class _Flake:
    __slots__ = ("x", "y", "r", "vy", "vx", "ph", "sw")


class SnowOverlay(QWidget):
    """Прозрачный слой поверх главного окна: снежинки + сугробы. Мышь сквозь него проходит."""
    WIND_R = 110.0

    def __init__(self, host, cfg, pages):
        super().__init__(host)
        self.cfg, self.pages = cfg, pages
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._flakes, self._targets, self._seeds = [], [], {}
        self._last = time.perf_counter()
        self._cur_prev = QPointF(-1000, -1000)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)
        self._rt = QTimer(self)
        self._rt.timeout.connect(self.refresh_targets)
        self._rt.start(1500)
        cfg.changed.connect(lambda k: self.update() if k.startswith("snow_") else None)
        self.refresh_targets()

    # --- сугробы ----------------------------------------------------------------
    def refresh_targets(self):
        out = []
        for w in self.parentWidget().findChildren(QWidget):
            n = w.objectName()
            if isinstance(w, RailButton):
                out.append((w, "rail", 5.0))
            elif n in ("Btn", "Primary"):
                out.append((w, "rect", 5.0))
            elif n in ("Card", "Preview"):
                out.append((w, "rect", 6.5))
            elif n == "UserPanel":
                out.append((w, "rect", 6.0))
        self._targets = out

    def _paint_caps(self, qp):
        host = self.parentWidget()
        pages_top = self.pages.mapTo(host, QPoint(0, 0)).y() + 48
        for w, kind, hmax in self._targets:
            if not w.isVisible():
                continue
            vr = w.visibleRegion().boundingRect()
            if vr.isEmpty() or vr.top() > 0:
                continue
            seed = self._seeds.setdefault(w, random.uniform(0, 100))
            hm = hmax * (0.85 + 0.3 * ((seed * 7) % 1))
            tl = w.mapTo(host, QPoint(0, 0))
            if kind == "rail":
                cy = tl.y() + w.height() / 2 - 24
                path = snow_cap_path(tl.x() + 24, tl.x() + 48, cy, hm, seed, 9, drop=3.0)
            else:
                if tl.y() - hm < (pages_top if self.pages.isAncestorOf(w) else 0):
                    continue
                path = snow_cap_path(tl.x() + 2, tl.x() + w.width() - 2, tl.y(), hm, seed, min(10, w.width() / 4))
            draw_cap(qp, path)

    # --- снегопад -----------------------------------------------------------------
    def _spawn(self, anywhere):
        f = _Flake()
        f.r = random.uniform(1.1, 3.4)
        f.x = random.uniform(0, max(1, self.width()))
        f.y = random.uniform(0, max(1, self.height())) if anywhere else -8.0
        f.vy = (28 + f.r * 14) * random.uniform(0.8, 1.2)
        f.vx, f.ph, f.sw = 0.0, random.uniform(0, 6.28), random.uniform(0.6, 1.6)
        return f

    @staticmethod
    def _rect(f):
        s = int(f.r + 3)
        return QRect(int(f.x) - s, int(f.y) - s, 2 * s, 2 * s)

    def _tick(self):
        now = time.perf_counter()
        dt = min(now - self._last, 0.1)
        self._last = now
        win = self.window()
        if not win.isVisible() or win.isMinimized():
            return
        if not self.cfg.get("snow_fall"):
            if self._flakes:
                self._flakes.clear()
                self.update()
            return
        w, h = self.width(), self.height()
        target = int(w * h / 6000 * self.cfg.get("snow_amount") / 50)
        while len(self._flakes) < target:
            self._flakes.append(self._spawn(anywhere=len(self._flakes) < target * 0.9 or True))
        if len(self._flakes) > target:
            del self._flakes[target:]
        cur = self.mapFromGlobal(QCursor.pos())
        curp = QPointF(cur)
        cvx = (curp.x() - self._cur_prev.x()) / max(dt, 1e-3)
        cvy = (curp.y() - self._cur_prev.y()) / max(dt, 1e-3)
        if abs(self._cur_prev.x()) > 900:
            cvx = cvy = 0.0
        self._cur_prev = curp
        cvx, cvy = max(-2500, min(2500, cvx)), max(-2500, min(2500, cvy))
        R = self.WIND_R
        dirty = QRegion()
        for f in self._flakes:
            old = self._rect(f)
            dx, dy = f.x - curp.x(), f.y - curp.y()
            d2 = dx * dx + dy * dy
            if d2 < R * R:
                d = math.sqrt(d2) + 0.001
                push = 1.0 - d / R
                f.vx += (dx / d * push * 520 + cvx * push * 1.6) * dt
                f.y += (dy / d * push * 260 + cvy * push * 0.9) * dt
            f.vx *= math.exp(-dt * 1.6)
            f.x += (f.vx + math.sin(now * f.sw + f.ph) * 14 * (f.r / 3)) * dt
            f.y += f.vy * dt
            if f.y > h + 8 or f.y < -60:
                f.y, f.x, f.vx = -8.0, random.uniform(0, w), 0.0
            if f.x < -12:
                f.x = w + 12
            elif f.x > w + 12:
                f.x = -12
            dirty += old.united(self._rect(f))
        self.update(dirty)

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        if self.cfg.get("snow_caps"):
            self._paint_caps(qp)
        clip = e.rect()
        qp.setPen(Qt.NoPen)
        for f in self._flakes:
            if not clip.intersects(self._rect(f)):
                continue
            a = 0.4 + 0.5 * (f.r - 1.1) / 2.3
            if f.r > 2.2:
                qp.setBrush(QColor(255, 255, 255, int(255 * a * 0.35)))
                qp.drawEllipse(QPointF(f.x, f.y), f.r * 1.7, f.r * 1.7)
            qp.setBrush(QColor(255, 255, 255, int(255 * a)))
            qp.drawEllipse(QPointF(f.x, f.y), f.r, f.r)
