"""Иконка в системном трее."""
from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .constants import APP_NAME
from .icon import make_app_icon


class Tray(QObject):
    def __init__(self, window, cfg):
        super().__init__()
        self.window, self.cfg = window, cfg
        self.icon = QSystemTrayIcon(make_app_icon())
        self.icon.setToolTip(APP_NAME)
        self.menu = QMenu()
        self.menu.addAction("Открыть Isle", window.show_window)
        self.act_island = QAction("Показывать островок", self.menu, checkable=True)
        self.act_island.setChecked(bool(cfg.get("island_enabled")))
        self.act_island.toggled.connect(lambda v: cfg.set("island_enabled", v))
        self.menu.addAction(self.act_island)
        self.menu.addAction("Проверить обновления", lambda: window.check_updates())
        self.menu.addSeparator()
        self.menu.addAction("Выход", window.quit_app)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._activated)
        cfg.changed.connect(self._cfg)
        window.update_available.connect(
            lambda v: self.icon.showMessage(APP_NAME, f"Доступна версия {v}. Открой «Обновления», чтобы установить.",
                                            QSystemTrayIcon.Information, 6000))
        self.icon.show()

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.window.show_window()

    def _cfg(self, key):
        if key == "island_enabled":
            v = bool(self.cfg.get(key))
            if self.act_island.isChecked() != v:
                self.act_island.blockSignals(True); self.act_island.setChecked(v); self.act_island.blockSignals(False)
