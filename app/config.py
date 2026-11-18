"""Настройки приложения (JSON в %APPDATA%\\Isle\\config.json)."""
import json
import os

from PySide6.QtCore import QObject, QTimer, Signal

from .constants import data_dir

DEFAULTS = {
    "island_enabled": True,
    "island_x": None,
    "island_y": None,
    "island_scale": 100,
    "expand_on_hover": True,
    "expand_on_track": True,
    "hide_when_idle": True,
    "always_on_top": True,
    "dock_to_taskbar": True,
    "island_dock": "",
    "wave_style": "bars",      # bars | wave
    "wave_color": "cover",     # cover | brand
    "wave_sensitivity": 130,   # 50..250 %
    "autostart": False,
    "close_to_tray": True,
    "check_updates": True,
    "update_repo": "",
}


class Config(QObject):
    changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._path = data_dir() / "config.json"
        self._d = {}
        try:
            self._d = json.loads(self._path.read_text("utf-8"))
        except Exception:
            pass
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.save)

    def get(self, key):
        return self._d.get(key, DEFAULTS[key])

    def set(self, key, value):
        if key in self._d and self._d[key] == value:
            return
        self._d[key] = value
        self.changed.emit(key)
        self._timer.start()

    def save(self):
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._d, ensure_ascii=False, indent=2), "utf-8")
            os.replace(tmp, self._path)
        except Exception:
            pass
