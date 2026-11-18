"""Островок: плавающая «таблетка» с обложкой, названием, управлением и живой волной."""
import ctypes
import logging
import math
import time

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient, QRegion, QTransform,
                           QLinearGradient)
from PySide6.QtWidgets import QMenu, QWidget

from . import theme as T
from .audio import BANDS
from .constants import IS_WINDOWS
from .media import MediaState

CW, CH = 232.0, 44.0      # свёрнутый размер
EW, EH = 372.0, 152.0     # раскрытый размер
PAD = 4.0
log = logging.getLogger("isle.island")


def lerp(a, b, t): return a + (b - a) * t
def clamp(x, lo=0.0, hi=1.0): return max(lo, min(hi, x))
def fmt_time(s): s = int(max(0, s)); return f"{s // 60}:{s % 60:02d}"
def _mid(a, b): return QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)


def lerp_rect(a, b, t):
    return QRectF(lerp(a.x(), b.x(), t), lerp(a.y(), b.y(), t),
                  lerp(a.width(), b.width(), t), lerp(a.height(), b.height(), t))


_WINAPI = None


def _winapi():
    """Лениво готовим вызовы WinAPI (один раз)."""
    global _WINAPI
    if _WINAPI is None:
        from ctypes import wintypes

        class APPBARDATA(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                        ("uCallbackMessage", wintypes.UINT), ("uEdge", wintypes.UINT),
                        ("rc", wintypes.RECT), ("lParam", wintypes.LPARAM)]

        sh, u = ctypes.windll.shell32, ctypes.windll.user32
        sh.SHAppBarMessage.argtypes = [wintypes.DWORD, ctypes.POINTER(APPBARDATA)]
        sh.SHAppBarMessage.restype = ctypes.c_size_t
        u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        u.FindWindowW.restype = wintypes.HWND
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        _WINAPI = (APPBARDATA, wintypes, sh, u)
    return _WINAPI


def _taskbar_info(scr):
    """Панель задач основного экрана через WinAPI: (kind, полоса QRect, автоскрытие, видимость 0..1) или None.
    Работает и с обычной панелью, и с автоскрываемой. Слева/справа не поддерживается."""
    if not IS_WINDOWS or scr != QGuiApplication.primaryScreen():
        return None
    try:
        APPBARDATA, wintypes, sh, u = _winapi()
        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(APPBARDATA)
        autohide = bool(sh.SHAppBarMessage(4, ctypes.byref(abd)) & 1)       # ABM_GETSTATE
        if not sh.SHAppBarMessage(5, ctypes.byref(abd)):                    # ABM_GETTASKBARPOS
            return None
        edge, rc = abd.uEdge, abd.rc                                        # 0 слева, 1 сверху, 2 справа, 3 снизу
        win = wintypes.RECT()
        hwnd = u.FindWindowW("Shell_TrayWnd", None)
        have_win = bool(hwnd) and bool(u.GetWindowRect(hwnd, ctypes.byref(win)))
    except Exception:
        log.exception("не удалось опросить панель задач")
        return None
    if edge not in (1, 3):
        return None
    g, d = scr.geometry(), scr.devicePixelRatio()
    thick_px = rc.bottom - rc.top
    if not 20 <= thick_px <= 240 and have_win:
        thick_px = win.bottom - win.top
    if not 20 <= thick_px <= 240:
        thick_px = 48
    thick = thick_px / d
    frac = 1.0
    if edge == 3:
        band = QRect(g.left(), int(g.bottom() + 1 - thick), g.width(), int(thick))
        if autohide and have_win:
            frac = (g.bottom() + 1 - (g.top() + (win.top - g.top()) / d)) / thick
    else:
        band = QRect(g.left(), g.top(), g.width(), int(thick))
        if autohide and have_win:
            frac = ((g.top() + (win.bottom - g.top()) / d) - g.top()) / thick
    return ("bottom" if edge == 3 else "top"), band, autohide, max(0.0, min(1.0, frac))


def dominant_color(img: QImage) -> QColor:
    small = img.scaled(24, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB32)
    r = g = b = w = 0.0
    for y in range(24):
        for x in range(24):
            c = QColor(small.pixel(x, y))
            _, s, v, _ = c.getHsv()
            k = (s / 255.0) ** 2 * (v / 255.0) + 0.001
            r += c.red() * k; g += c.green() * k; b += c.blue() * k; w += k
    avg = QColor(int(r / w), int(g / w), int(b / w))
    h, s, v, _ = avg.getHsv()
    if h < 0 or s < 35:
        return QColor("#dbdee1")
    return QColor.fromHsv(h, max(s, 150), max(v, 215))


def draw_wave(qp, rect, vals, style, color, alpha):
    n = len(vals)
    cy, maxh = rect.center().y(), rect.height()
    if style == "wave":
        dx = rect.width() / (n - 1)
        top = [QPointF(rect.left() + i * dx, cy - max(1.2, v * maxh / 2)) for i, v in enumerate(vals)]
        bot = [QPointF(p.x(), 2 * cy - p.y()) for p in top]
        path = QPainterPath(top[0])
        for i in range(1, n - 1):
            path.quadTo(top[i], _mid(top[i], top[i + 1]))
        path.lineTo(top[-1])
        path.lineTo(bot[-1])
        for i in range(n - 2, 0, -1):
            path.quadTo(bot[i], _mid(bot[i], bot[i - 1]))
        path.lineTo(bot[0])
        path.closeSubpath()
        g = QLinearGradient(0, rect.top(), 0, rect.bottom())
        c1, c2 = QColor(color), QColor(color)
        c1.setAlphaF(alpha); c2.setAlphaF(alpha * 0.55)
        g.setColorAt(0, c1); g.setColorAt(0.5, c2); g.setColorAt(1, c1)
        qp.setPen(Qt.NoPen)
        qp.setBrush(g)
        qp.drawPath(path)
    else:
        pitch = rect.width() / n
        bw = max(2.0, pitch * 0.58)
        c = QColor(color)
        c.setAlphaF(alpha)
        qp.setPen(Qt.NoPen)
        qp.setBrush(c)
        for i, v in enumerate(vals):
            h = max(bw, v * maxh)
            qp.drawRoundedRect(QRectF(rect.left() + i * pitch + (pitch - bw) / 2, cy - h / 2, bw, h), bw / 2, bw / 2)


def _skip(qp, c, color, forward):
    d = 1 if forward else -1
    p = QPainterPath()
    p.moveTo(c.x() - d * 6, c.y() - 7); p.lineTo(c.x() + d * 4, c.y()); p.lineTo(c.x() - d * 6, c.y() + 7); p.closeSubpath()
    qp.setPen(QPen(color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    qp.setBrush(color)
    qp.drawPath(p)
    qp.drawLine(QPointF(c.x() + d * 7.5, c.y() - 7), QPointF(c.x() + d * 7.5, c.y() + 7))


class IslandWidget(QWidget):
    open_requested = Signal()

    def __init__(self, cfg, media, audio, embedded=False, parent=None):
        super().__init__(parent)
        self.cfg, self.media, self.audio, self.embedded = cfg, media, audio, embedded
        self.state = MediaState()
        self._stamp = time.perf_counter()
        self.cover = None
        self._key = ""
        self.p = 1.0 if embedded else 0.0
        self.vis = 1.0 if embedded else 0.0
        self.lv = np.zeros(BANDS, np.float32)
        self._hover = self._pinned = self._dragging = False
        self._flash_until = 0.0
        self._hits, self._hit_key, self._press_key = {}, None, None
        self._press_pos = self._drag_off = None
        self._seek_frac = None
        self._col_cur, self._col_tgt = QColor(T.BRAND), QColor(T.BRAND)
        self._last = time.perf_counter()
        self._scale = 1.0 if embedded else cfg.get("island_scale") / 100.0
        self._dock = None            # None | "bottom" | "top" — пристыкован к панели задач
        self._anchor_bottom = False  # при доке снизу панель раскрывается вверх
        self._autohide, self._band, self._warned = False, None, False
        self.dock_vis, self._tb_t, self._tb_target = 1.0, 0.0, 1.0   # видимость вместе с панелью задач
        self._ch = CH                # высота свёрнутой таблетки (в доке подгоняется под панель задач)

        self._f_title = QFont(T.FONT); self._f_title.setPixelSize(14); self._f_title.setWeight(QFont.DemiBold)
        self._f_artist = QFont(T.FONT); self._f_artist.setPixelSize(12)
        self._f_time = QFont(T.FONT); self._f_time.setPixelSize(10)

        self._leave = QTimer(self)
        self._leave.setSingleShot(True)
        self._leave.setInterval(300)
        self._leave.timeout.connect(lambda: setattr(self, "_hover", False))
        self.setMouseTracking(True)
        if not embedded:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
                                | Qt.NoDropShadowWindowHint
                                | (Qt.WindowStaysOnTopHint if cfg.get("always_on_top") else Qt.Widget))
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._apply_size()

        media.state_changed.connect(self._on_state)
        cfg.changed.connect(self._on_cfg)
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self._top_timer = QTimer(self)
        self._top_timer.timeout.connect(self._keep_on_top)
        self._top_timer.start(500)

    # --- размеры и позиция ---------------------------------------------------
    def _apply_size(self):
        s = self._scale
        self.setFixedSize(round((EW + 2 * PAD) * s), round((EH + 2 * PAD) * s))
        self._update_mask()

    def _place_default(self):
        scr = QGuiApplication.primaryScreen().availableGeometry()
        self.move(scr.center().x() - self.width() // 2, scr.top() + 6 - round(PAD * self._scale))

    def _restore_pos(self):
        x, y = self.cfg.get("island_x"), self.cfg.get("island_y")
        if x is not None and y is not None:
            c = QPoint(int(x + self.width() / 2), int(y + self.height() / 2))
            scr = QGuiApplication.screenAt(c)
            if scr is not None:
                dock = self.cfg.get("island_dock")
                if dock and self.cfg.get("dock_to_taskbar"):
                    kind, band = self._taskbar_band(scr)
                    if kind == dock:
                        self._apply_dock(kind, band, int(x), scr)
                        return
                self._undock()
                self.move(int(x), int(y))
                return
        self._place_default()

    def reset_position(self):
        self._undock()
        self.cfg.set("island_x", None)
        self.cfg.set("island_y", None)
        self.cfg.set("island_dock", "")
        self._place_default()

    # --- док в панель задач ------------------------------------------------------------
    @staticmethod
    def _taskbar_band(scr):
        """Где панель задач на этом экране: (\"bottom\"|\"top\"|None, QRect). Слева/справа и автоскрытие не поддерживаются."""
        info = _taskbar_info(scr)
        if info:
            return info[0], info[1]
        g, a = scr.geometry(), scr.availableGeometry()
        if a.bottom() < g.bottom():
            return "bottom", QRect(g.left(), a.bottom() + 1, g.width(), g.bottom() - a.bottom())
        if a.top() > g.top():
            return "top", QRect(g.left(), g.top(), g.width(), a.top() - g.top())
        return None, None

    def _apply_dock(self, kind, band, x_left, scr):
        s = self._scale
        self._dock, self._anchor_bottom = kind, kind == "bottom"
        self._band = band
        info = _taskbar_info(scr)
        self._autohide = bool(info and info[2])
        self._ch = max(30.0, min(CH, (band.height() - 8) / s))
        cy = band.center().y()
        y = cy - (PAD + EH - self._ch / 2) * s if kind == "bottom" else cy - (PAD + self._ch / 2) * s
        g = scr.geometry()
        x = max(g.left(), min(x_left, g.right() - self.width()))
        self.move(round(x), round(y))
        self._update_mask()
        self.update()

    def _undock(self):
        self._dock, self._anchor_bottom, self._ch = None, False, CH
        self._autohide, self._band, self.dock_vis, self._tb_target = False, None, 1.0, 1.0
        self._update_mask()

    def _redock(self):
        scr = QGuiApplication.screenAt(self.geometry().center())
        if scr is None or not self._dock:
            return
        kind, band = self._taskbar_band(scr)
        if kind == self._dock:
            self._apply_dock(kind, band, self.x(), scr)
        else:
            self._undock()

    def _drag_to(self, gp):
        """Перетаскивание: рядом с панелью задач островок «прилипает» к ней."""
        if self.cfg.get("dock_to_taskbar"):
            scr = QGuiApplication.screenAt(gp)
            if scr is not None:
                kind, band = self._taskbar_band(scr)
                if kind:
                    dist = band.top() - gp.y() if kind == "bottom" else gp.y() - band.bottom()
                    if dist < (90 if self._dock == kind else 50):
                        self._apply_dock(kind, band, (gp - self._drag_off).x(), scr)
                        return
            if scr is not None and not self._warned:
                g = scr.geometry()
                if gp.y() > g.bottom() - 120 or gp.y() < g.top() + 120:
                    self._warned = True
                    log.warning("прилипание: панель задач не найдена (экран %s, рабочая область %s, info=%s)",
                                g, scr.availableGeometry(), _taskbar_info(scr))
        if self._dock:
            self._undock()
        self.move(gp - self._drag_off)

    def _update_dock_vis(self, now, dt):
        """При автоскрытии панели задач островок появляется и исчезает вместе с ней."""
        if not (self._dock and self._autohide):
            self.dock_vis = 1.0
            return
        if now - self._tb_t > 0.05:
            self._tb_t = now
            scr = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
            res = _taskbar_info(scr)
            keep = self._hover or self._dragging or self.p > 0.02 or res is None
            self._tb_target = 1.0 if keep else clamp(res[3] * 1.25)
        self.dock_vis += (self._tb_target - self.dock_vis) * (1 - math.exp(-dt * 18))
        if abs(self._tb_target - self.dock_vis) < 0.01:
            self.dock_vis = self._tb_target

    def _keep_on_top(self):
        """Панель задач сама «топмост» — периодически возвращаем островок выше неё."""
        if IS_WINDOWS and self._dock and self.isVisible() and self.cfg.get("always_on_top"):
            try:
                ctypes.windll.user32.SetWindowPos(ctypes.c_void_p(int(self.winId())), ctypes.c_void_p(-1),
                                                  0, 0, 0, 0, 0x0013)   # NOMOVE | NOSIZE | NOACTIVATE
            except Exception:
                pass

    def _pill_rect(self):
        w, h = lerp(CW, EW, self.p), lerp(self._ch, EH, self.p)
        return QRectF((EW - w) / 2, (EH - h) if self._anchor_bottom else 0, w, h)

    def _radius(self): return lerp(self._ch / 2, 28.0, self.p)

    def _update_mask(self):
        if self.embedded:
            return
        r = self._pill_rect().adjusted(-1.5, -1.5, 1.5, 1.5).translated(PAD, PAD)
        path = QPainterPath()
        path.addRoundedRect(r, self._radius() + 1.5, self._radius() + 1.5)
        s = self._scale
        poly = QTransform.fromScale(s, s).map(path).toFillPolygon().toPolygon()
        self.setMask(QRegion(poly))

    # --- события извне -----------------------------------------------------------
    def _on_state(self, st: MediaState):
        if st.key != self._key:
            self._key = st.key
            self.cover = None
            self._col_tgt = QColor(T.BRAND)
            if st.title and self.cfg.get("expand_on_track") and not self.embedded:
                self._flash_until = time.perf_counter() + 3.2
        if st.cover:
            img = QImage.fromData(st.cover)
            if not img.isNull():
                side = min(img.width(), img.height())
                sq = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
                self.cover = QPixmap.fromImage(sq)
                self._col_tgt = dominant_color(sq)
        self.state, self._stamp = st, time.perf_counter()
        self.update()

    def _on_cfg(self, key):
        if self.embedded:
            self.update()
            return
        if key == "island_scale":
            cx = self.x() + self.width() / 2
            self._scale = self.cfg.get("island_scale") / 100.0
            self._apply_size()
            self.move(round(cx - self.width() / 2), self.y())
            if self._dock:
                self._redock()
        elif key == "dock_to_taskbar":
            if not self.cfg.get(key) and self._dock:
                self._undock()
                self._place_default()
        elif key == "always_on_top":
            vis, pos = self.isVisible(), self.pos()
            self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(self.cfg.get("always_on_top")))
            if vis:
                self.show()
            self.move(pos)
        self.update()

    def _should_show(self):
        if self.embedded:
            return True
        if not self.cfg.get("island_enabled"):
            return False
        return self.state.has_session or not self.cfg.get("hide_when_idle")

    # --- анимация ------------------------------------------------------------------
    def _synthetic(self, t):
        i = np.arange(BANDS)
        v = (0.5 + 0.5 * np.sin(t * 5.0 + i * 0.9)) * (0.5 + 0.5 * np.sin(t * 2.3 - i * 0.37))
        v = v * (0.9 * np.exp(-i / 22.0) + 0.1)
        v[:6] += 0.45 * max(0.0, math.sin(t * 12.5)) ** 6
        return np.clip(v, 0, 1).astype(np.float32)

    def _tick(self):
        now = time.perf_counter()
        dt = min(now - self._last, 0.05)
        self._last = now
        dirty = False
        if not self.embedded:
            self._update_dock_vis(now, dt)
            tv = 1.0 if self._should_show() else 0.0
            if self.vis != tv:
                self.vis += (tv - self.vis) * (1 - math.exp(-dt * 14))
                if abs(tv - self.vis) < 0.01:
                    self.vis = tv
            op = self.vis * self.dock_vis
            if op > 0.01 and not self.isVisible():
                self._restore_pos()
                self.show()
            if not self.isVisible():
                return
            if op <= 0.01:
                self.hide()
                return
            if abs(self.windowOpacity() - op) > 0.004:
                self.setWindowOpacity(op)
        # раскрытие
        want = (self.embedded or self._pinned or now < self._flash_until
                or (self._hover and self.cfg.get("expand_on_hover")))
        tgt = 1.0 if want else 0.0
        if self.p != tgt:
            self.p += (tgt - self.p) * (1 - math.exp(-dt * 16))
            if abs(tgt - self.p) < 0.002:
                self.p = tgt
            self._update_mask()
            dirty = True
        # волна
        st = self.state
        if not st.playing:
            target = np.zeros(BANDS, np.float32)
        elif self.audio.ok:
            fresh = time.monotonic() - self.audio.stamp < 0.3
            if fresh:
                gain = (self.cfg.get("wave_sensitivity") - 100) * 0.2   # дБ: 130% = +6 дБ
                target = np.clip((self.audio.db + 72.0 + gain) / 56.0 + self.audio.tilt, 0.0, 1.0)
            else:
                target = np.zeros(BANDS, np.float32)
        else:
            target = self._synthetic(now)
        up, down = 1 - math.exp(-dt * 28), 1 - math.exp(-dt * 9)
        self.lv += (target - self.lv) * np.where(target > self.lv, up, down)
        if st.playing or self.lv.max() > 0.004:
            dirty = True
        # цвет
        k = 1 - math.exp(-dt * 6)
        a, b = self._col_cur, self._col_tgt
        if abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) > 2:
            self._col_cur = QColor(round(a.red() + (b.red() - a.red()) * k),
                                   round(a.green() + (b.green() - a.green()) * k),
                                   round(a.blue() + (b.blue() - a.blue()) * k))
            dirty = True
        if dirty:
            self.update()

    # --- рисование -------------------------------------------------------------------
    def _bars(self, n):
        half = (n + 1) // 2
        v = np.interp(np.linspace(0, BANDS * 0.78, half), np.arange(BANDS), self.lv)
        full = np.concatenate([v[::-1], v[1:]]) if n % 2 else np.concatenate([v[::-1], v])
        return np.clip(full ** 0.9, 0, 1)

    def _position(self):
        st = self.state
        pos = st.position + ((time.perf_counter() - self._stamp) if st.playing else 0.0)
        return min(pos, st.duration) if st.duration > 0 else pos

    def paintEvent(self, _e):
        s, p, st = self._scale, self.p, self.state
        qp = QPainter(self)
        qp.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        qp.scale(s, s)
        qp.translate(PAD, PAD)
        r, rad = self._pill_rect(), self._radius()
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        qp.setPen(QPen(QColor(255, 255, 255, 24), 1))
        qp.setBrush(QColor(17, 18, 20, 248))
        qp.drawPath(path)
        accent = QColor(self._col_cur) if self.cfg.get("wave_color") == "cover" else QColor(T.BRAND)

        c0 = QRectF(r.left() + 8, r.top() + (self._ch - 28) / 2, 28, 28)
        c1 = QRectF(r.left() + 16, r.top() + 16, 56, 56)
        cr = lerp_rect(c0, c1, p)
        # свечение от обложки
        qp.save()
        qp.setClipPath(path)
        g = QRadialGradient(cr.center(), 170)
        gc = QColor(accent); gc.setAlpha(52); g.setColorAt(0, gc); gc.setAlpha(0); g.setColorAt(1, gc)
        qp.fillRect(r, g)
        qp.restore()
        # обложка
        cp = QPainterPath()
        crad = lerp(8, 12, p)
        cp.addRoundedRect(cr, crad, crad)
        qp.save()
        qp.setClipPath(cp)
        if self.cover is not None:
            qp.drawPixmap(cr, self.cover, QRectF(self.cover.rect()))
        else:
            qp.fillPath(cp, QColor("#2b2d31"))
            qp.setPen(QColor(T.MUTED))
            f = QFont(T.FONT); f.setPixelSize(int(cr.height() * 0.5)); qp.setFont(f)
            qp.drawText(cr, Qt.AlignCenter, "♪")
        qp.restore()
        # волна
        w0 = QRectF(r.left() + 48, r.top() + (self._ch - 24) / 2, max(10.0, r.width() - 62), 24)
        w1 = QRectF(r.right() - 16 - 72, r.top() + 22, 72, 44)
        wr = lerp_rect(w0, w1, p)
        n = max(8, int(round(lerp(26, 12, p))))
        vals = self._bars(n) if self.cfg.get("wave_style") == "bars" else self._bars(n)
        draw_wave(qp, wr, vals, self.cfg.get("wave_style"), accent, 1.0 if st.playing else 0.45)

        a = clamp((p - 0.5) / 0.5)
        self._hits = {}
        if a > 0.01:
            qp.save()
            qp.setOpacity(a)
            tx = r.left() + 16 + 56 + 14
            tw = (r.right() - 16 - 72) - 12 - tx
            title = st.title if st.has_session else "Ничего не играет"
            artist = st.artist if st.has_session else "Запусти музыку в любом плеере"
            qp.setFont(self._f_title); qp.setPen(QColor(T.HEAD))
            qp.drawText(QPointF(tx, r.top() + 40), QFontMetrics(self._f_title).elidedText(title, Qt.ElideRight, int(tw)))
            qp.setFont(self._f_artist); qp.setPen(QColor(T.MUTED))
            qp.drawText(QPointF(tx, r.top() + 59), QFontMetrics(self._f_artist).elidedText(artist, Qt.ElideRight, int(tw)))
            # прогресс
            y = r.top() + 91
            x0, x1 = r.left() + 16 + 36, r.right() - 16 - 36
            pos = self._position()
            frac = self._seek_frac if self._seek_frac is not None else (pos / st.duration if st.duration > 0 else 0.0)
            frac = clamp(frac)
            qp.setFont(self._f_time); qp.setPen(QColor(T.MUTED))
            qp.drawText(QRectF(r.left() + 16, y - 8, 30, 16), Qt.AlignRight | Qt.AlignVCenter, fmt_time(frac * st.duration if self._seek_frac is not None else pos))
            qp.drawText(QRectF(x1 + 6, y - 8, 30, 16), Qt.AlignLeft | Qt.AlignVCenter, fmt_time(st.duration))
            hov = self._hit_key == "bar" or self._press_key == "bar"
            bh = 6 if hov else 4
            qp.setPen(Qt.NoPen)
            qp.setBrush(QColor("#4e5058"))
            qp.drawRoundedRect(QRectF(x0, y - bh / 2, x1 - x0, bh), bh / 2, bh / 2)
            qp.setBrush(QColor("#ffffff") if hov else accent)
            qp.drawRoundedRect(QRectF(x0, y - bh / 2, (x1 - x0) * frac, bh), bh / 2, bh / 2)
            if hov:
                qp.setBrush(QColor("white"))
                qp.drawEllipse(QPointF(x0 + (x1 - x0) * frac, y), 6, 6)
            # кнопки
            cy, cx = r.top() + 118, r.center().x()
            en = st.has_session
            qp.setOpacity(a * (1.0 if en else 0.35))
            white = QColor("white")
            for key, off, size in (("prev", -54, 34), ("play", 0, 40), ("next", 54, 34)):
                rc = QRectF(cx + off - size / 2, cy - size / 2, size, size)
                self._hits[key] = rc
                hot = self._hit_key == key and en
                if key == "play":
                    qp.setPen(Qt.NoPen)
                    qp.setBrush(white if hot else QColor("#e6e7ea"))
                    qp.drawEllipse(rc.adjusted(-1, -1, 1, 1) if hot else rc)
                    dark = QColor("#111214")
                    if st.playing:
                        qp.setBrush(dark)
                        qp.drawRoundedRect(QRectF(cx - 6.5, cy - 7, 4.4, 14), 1.6, 1.6)
                        qp.drawRoundedRect(QRectF(cx + 2.1, cy - 7, 4.4, 14), 1.6, 1.6)
                    else:
                        tri = QPainterPath()
                        tri.moveTo(cx - 4.5, cy - 8); tri.lineTo(cx + 8, cy); tri.lineTo(cx - 4.5, cy + 8); tri.closeSubpath()
                        qp.setPen(QPen(dark, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                        qp.setBrush(dark)
                        qp.drawPath(tri)
                else:
                    if hot:
                        qp.setPen(Qt.NoPen); qp.setBrush(QColor(255, 255, 255, 22)); qp.drawEllipse(rc)
                    _skip(qp, rc.center(), white if hot else QColor("#dbdee1"), key == "next")
            qp.restore()
            if a > 0.7:
                self._hits["bar"] = QRectF(x0, y - 10, x1 - x0, 20)
            else:
                self._hits = {}

    # --- мышь ------------------------------------------------------------------------
    def _logical(self, pos): return QPointF(pos.x() / self._scale - PAD, pos.y() / self._scale - PAD)

    def _hit_at(self, pt):
        for k in ("prev", "play", "next", "bar"):
            rc = self._hits.get(k)
            if rc is not None and rc.contains(pt):
                return k
        return None

    def _frac_at(self, x):
        r = self._pill_rect()
        x0, x1 = r.left() + 52, r.right() - 52
        return clamp((x - x0) / (x1 - x0))

    def enterEvent(self, e):
        self._leave.stop()
        self._hover = True

    def leaveEvent(self, e):
        self._hit_key = None
        self._leave.start()
        self.update()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        pt = self._logical(e.position())
        self._press_key = self._hit_at(pt)
        self._press_pos = e.globalPosition().toPoint()
        self._dragging = False
        if not self.embedded:
            self._drag_off = self._press_pos - self.frameGeometry().topLeft()
        if self._press_key == "bar":
            self._seek_frac = self._frac_at(pt.x())
        self.update()

    def mouseMoveEvent(self, e):
        pt = self._logical(e.position())
        if self._press_pos is not None:
            if self._press_key == "bar":
                self._seek_frac = self._frac_at(pt.x())
                self.update()
                return
            if self._press_key is None and not self.embedded:
                if (e.globalPosition().toPoint() - self._press_pos).manhattanLength() > 4:
                    self._dragging = True
                if self._dragging:
                    self._drag_to(e.globalPosition().toPoint())
                    return
        k = self._hit_at(pt)
        if k != self._hit_key:
            self._hit_key = k
            self.setCursor(Qt.PointingHandCursor if k else Qt.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._press_pos is None:
            return
        pt, k = self._logical(e.position()), self._press_key
        if self._dragging:
            self.cfg.set("island_x", self.x())
            self.cfg.set("island_y", self.y())
            self.cfg.set("island_dock", self._dock or "")
        elif k == "bar":
            if self.state.has_session and self.state.duration > 0 and self._seek_frac is not None:
                sec = self._seek_frac * self.state.duration
                self.state.position, self._stamp = sec, time.perf_counter()
                self.media.seek(sec)
        elif k in ("prev", "play", "next"):
            if self._hit_at(pt) == k and self.state.has_session:
                getattr(self.media, {"prev": "prev", "play": "toggle", "next": "next"}[k])()
        elif k is None and not self.embedded:
            self._pinned = not self._pinned
        self._press_key = self._press_pos = self._seek_frac = None
        self._dragging = False
        self.update()

    def contextMenuEvent(self, e):
        if self.embedded:
            return
        m = QMenu(self)
        m.addAction("Открыть Isle", self.open_requested.emit)
        m.addAction("Скрыть островок", lambda: self.cfg.set("island_enabled", False))
        m.exec(e.globalPos())
