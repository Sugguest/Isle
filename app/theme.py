"""Тема в стиле Discord: цвета и QSS."""
import ctypes
import sys

BRAND = "#5865F2"
BRAND_H = "#4752C4"
BG1 = "#313338"      # основной фон
BG2 = "#2b2d31"      # сайдбар, карточки
BG3 = "#1e1f22"      # рейл, поля
BG4 = "#111214"      # плавающие элементы
TEXT = "#dbdee1"
HEAD = "#f2f3f5"
MUTED = "#949ba4"
GREEN = "#23a55a"
FONT = "Segoe UI"

_RAW = """
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 14px; color: @TEXT@; outline: 0; }
QMainWindow { background: @BG1@; }
QWidget#Content, QWidget#Page, QScrollArea { background: @BG1@; border: none; }
QWidget#Rail { background: @BG3@; }
QWidget#Sidebar { background: @BG2@; }
QWidget#SidebarHeader { background: @BG2@; border-bottom: 1px solid #1f2023; }
QWidget#PageHeader { background: @BG1@; border-bottom: 1px solid #26272b; }
QWidget#UserPanel { background: #232428; }
QLabel { background: transparent; }
QLabel#Title { font-size: 16px; font-weight: 600; color: @HEAD@; }
QLabel#Topic { font-size: 13px; color: @MUTED@; }
QLabel#Section { font-size: 12px; font-weight: 700; color: @MUTED@; }
QLabel#RowTitle { font-weight: 500; color: @HEAD@; }
QLabel#RowDesc { font-size: 13px; color: @MUTED@; }
QLabel#Status { font-size: 13px; color: @MUTED@; }
QLabel#Ok { font-size: 13px; color: @GREEN@; }
QFrame#Card { background: @BG2@; border-radius: 8px; }
QFrame#Divider { background: #3a3c41; }
QFrame#Preview { border-radius: 8px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3b4296, stop:0.55 #2a2d5c, stop:1 #1b1c2b); }
QPushButton#NavItem { text-align: left; padding: 7px 10px; border: none; border-radius: 4px; background: transparent; color: @MUTED@; font-weight: 500; }
QPushButton#NavItem:hover { background: #35373c; color: @TEXT@; }
QPushButton#NavItem:checked { background: #404249; color: #ffffff; }
QPushButton#Btn, QPushButton#Primary { border: none; border-radius: 3px; padding: 8px 16px; color: #ffffff; font-weight: 500; }
QPushButton#Btn { background: #4e5058; }
QPushButton#Btn:hover { background: #6d6f78; }
QPushButton#Primary { background: @BRAND@; }
QPushButton#Primary:hover { background: @BRAND_H@; }
QPushButton#Btn:disabled, QPushButton#Primary:disabled { background: #3a3c41; color: #80848e; }
QWidget#SegBox { background: @BG3@; border-radius: 6px; }
QPushButton#Seg { border: none; border-radius: 4px; padding: 6px 14px; background: transparent; color: @MUTED@; font-weight: 500; }
QPushButton#Seg:hover { color: @TEXT@; }
QPushButton#Seg:checked { background: #404249; color: #ffffff; }
QProgressBar { background: @BG3@; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; color: transparent; }
QProgressBar::chunk { background: @BRAND@; border-radius: 4px; }
QSlider::groove:horizontal { height: 8px; background: #4e5058; border-radius: 4px; }
QSlider::sub-page:horizontal { background: @BRAND@; border-radius: 4px; }
QSlider::handle:horizontal { width: 10px; margin: -8px 0; background: #ffffff; border-radius: 3px; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #1a1b1e; border-radius: 4px; min-height: 40px; margin: 2px 2px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; height: 0; }
QToolTip { background: @BG4@; color: @HEAD@; border: 1px solid @BG3@; padding: 6px 10px; border-radius: 4px; }
QMenu { background: @BG4@; border: 1px solid @BG3@; padding: 6px; }
QMenu::item { padding: 7px 28px 7px 12px; border-radius: 3px; }
QMenu::item:selected { background: @BRAND@; color: #ffffff; }
QMenu::separator { height: 1px; background: #2b2d31; margin: 4px 6px; }
"""


def _build() -> str:
    s = _RAW
    for k, v in {"BRAND_H": BRAND_H, "BRAND": BRAND, "BG1": BG1, "BG2": BG2, "BG3": BG3,
                 "BG4": BG4, "TEXT": TEXT, "HEAD": HEAD, "MUTED": MUTED, "GREEN": GREEN}.items():
        s = s.replace(f"@{k}@", v)
    return s


QSS = _build()


def apply_dark_titlebar(widget) -> None:
    """Тёмная системная шапка окна (Windows 10 20H1+/11)."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)          # dark mode
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(0x221F1E)), 4)   # caption #1e1f22
        dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(ctypes.c_int(0xF2F3F5)), 4)   # caption text
    except Exception:
        pass
