"""Главное окно: рейл → сайдбар → страницы (в духе Discord)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QProgressBar, QPushButton, QScrollArea, QSlider, QStackedWidget,
                               QSystemTrayIcon, QToolTip, QVBoxLayout, QWidget)

from . import autostart, theme as T
from .constants import APP_NAME, GITHUB_REPO, data_dir
from .icon import make_pixmap
from .island import EH, IslandWidget
from .updater import Updater
from .version import __version__
from .widgets import Button, Card, RailButton, Segmented, Toggle


class Page(QWidget):
    def __init__(self, title, topic):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        head = QWidget()
        head.setObjectName("PageHeader")
        head.setAttribute(Qt.WA_StyledBackground, True)
        head.setFixedHeight(48)
        h = QHBoxLayout(head)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(12)
        t = QLabel(title); t.setObjectName("Title"); h.addWidget(t)
        sep = QFrame(); sep.setFixedSize(1, 24); sep.setStyleSheet("background:#3f4147"); h.addWidget(sep)
        tp = QLabel(topic); tp.setObjectName("Topic"); h.addWidget(tp); h.addStretch()
        v.addWidget(head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget(); body.setObjectName("Page"); body.setAttribute(Qt.WA_StyledBackground, True)
        outer = QHBoxLayout(body)
        outer.setContentsMargins(28, 16, 28, 28)
        col = QWidget(); col.setMaximumWidth(720)
        self.col = QVBoxLayout(col)
        self.col.setContentsMargins(0, 0, 0, 0)
        self.col.setSpacing(8)
        outer.addWidget(col, 1)
        outer.addStretch(0)
        scroll.setWidget(body)
        v.addWidget(scroll, 1)

    def section(self, text):
        lbl = QLabel(text.upper()); lbl.setObjectName("Section")
        lbl.setContentsMargins(2, 12, 0, 0)
        self.col.addWidget(lbl)

    def add(self, w): self.col.addWidget(w)
    def finish(self): self.col.addStretch(1)


class MainWindow(QMainWindow):
    update_available = Signal(str)

    def __init__(self, cfg, media, audio, updater: Updater):
        super().__init__()
        self.cfg, self.media, self.audio, self.updater = cfg, media, audio, updater
        self.quitting, self._info, self._silent, self._dark_done = False, None, False, False
        self._toggles, self._nav = {}, {}
        self.setWindowTitle(APP_NAME)
        self.resize(1020, 700)
        self.setMinimumSize(860, 560)
        self.preview = IslandWidget(cfg, media, audio, embedded=True)

        root = QWidget()
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_rail())
        lay.addWidget(self._build_sidebar())
        self.pages = QStackedWidget()
        self.pages.setObjectName("Content")
        self.pages.addWidget(self._music_page())
        self.pages.addWidget(self._general_page())
        self.pages.addWidget(self._updates_page())
        lay.addWidget(self.pages, 1)

        cfg.changed.connect(self._cfg_changed)
        updater.check_done.connect(self._on_checked)
        updater.progress.connect(self.bar.setValue)
        updater.ready.connect(self._on_ready)
        updater.failed.connect(self._on_failed)
        self._go(0)

    # --- каркас ---------------------------------------------------------------------
    def _build_rail(self):
        rail = QWidget(); rail.setObjectName("Rail"); rail.setAttribute(Qt.WA_StyledBackground, True)
        rail.setFixedWidth(72)
        v = QVBoxLayout(rail)
        v.setContentsMargins(0, 12, 0, 12)
        v.setSpacing(8)
        self.rb_home = RailButton("logo", "Компоненты")
        self.rb_home.setChecked(True)
        self.rb_set = RailButton("gear", "Настройки")
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        grp.addButton(self.rb_home); grp.addButton(self.rb_set)
        self.rb_home.clicked.connect(lambda: (self.side.setCurrentIndex(0), self._go(0)))
        self.rb_set.clicked.connect(lambda: (self.side.setCurrentIndex(1), self._go(1)))
        add = RailButton("plus", "Скоро: новые компоненты", accent=T.GREEN, selectable=False)
        add.clicked.connect(lambda: QToolTip.showText(QCursor.pos(), "Скоро: новые компоненты"))
        sep = QFrame(); sep.setFixedSize(32, 2); sep.setStyleSheet("background:#35363c;border-radius:1px")
        v.addWidget(self.rb_home)
        v.addWidget(sep, 0, Qt.AlignHCenter)
        v.addWidget(add)
        v.addStretch(1)
        v.addWidget(self.rb_set)
        return rail

    def _side_list(self, title, groups, hint=None):
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        head = QWidget(); head.setObjectName("SidebarHeader"); head.setAttribute(Qt.WA_StyledBackground, True)
        head.setFixedHeight(48)
        hl = QHBoxLayout(head); hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel(title); t.setObjectName("Title"); hl.addWidget(t)
        v.addWidget(head)
        body = QVBoxLayout(); body.setContentsMargins(8, 12, 8, 8); body.setSpacing(2)
        grp = QButtonGroup(w); grp.setExclusive(True)
        for gtitle, items in groups:
            s = QLabel(gtitle); s.setObjectName("Section"); s.setContentsMargins(8, 0, 0, 4)
            body.addWidget(s)
            for text, idx in items:
                b = QPushButton(text); b.setObjectName("NavItem"); b.setCheckable(True)
                b.setCursor(Qt.PointingHandCursor)
                grp.addButton(b); self._nav[idx] = b
                b.clicked.connect(lambda _=False, i=idx: self.pages.setCurrentIndex(i))
                body.addWidget(b)
        if hint:
            h = QLabel(hint); h.setObjectName("Status"); h.setWordWrap(True); h.setContentsMargins(8, 14, 8, 0)
            body.addWidget(h)
        body.addStretch(1)
        v.addLayout(body, 1)
        return w

    def _build_sidebar(self):
        side = QWidget(); side.setObjectName("Sidebar"); side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(240)
        v = QVBoxLayout(side); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.side = QStackedWidget()
        self.side.addWidget(self._side_list("Компоненты", [("МОДУЛИ", [("Музыкальный островок", 0)])],
                                            "Здесь будут появляться новые компоненты."))
        self.side.addWidget(self._side_list("Настройки", [("ПРИЛОЖЕНИЕ", [("Основные", 1), ("Обновления", 2)])]))
        v.addWidget(self.side, 1)
        panel = QWidget(); panel.setObjectName("UserPanel"); panel.setAttribute(Qt.WA_StyledBackground, True)
        panel.setFixedHeight(56)
        h = QHBoxLayout(panel); h.setContentsMargins(10, 0, 10, 0); h.setSpacing(10)
        av = QLabel(); av.setPixmap(make_pixmap(32)); av.setFixedSize(32, 32); h.addWidget(av)
        col = QVBoxLayout(); col.setSpacing(0)
        n = QLabel(APP_NAME); n.setObjectName("RowTitle"); col.addWidget(n)
        self.panel_status = QLabel(f"Версия {__version__}"); self.panel_status.setObjectName("Status")
        col.addWidget(self.panel_status)
        h.addLayout(col, 1)
        v.addWidget(panel)
        return side

    def _go(self, idx):
        self.pages.setCurrentIndex(idx)
        if idx in self._nav:
            self._nav[idx].setChecked(True)

    # --- страницы -----------------------------------------------------------------
    def _toggle(self, key):
        t = Toggle(self.cfg.get(key))
        t.toggled.connect(lambda v, k=key: self.cfg.set(k, v))
        self._toggles[key] = t
        return t

    def _cfg_changed(self, key):
        t = self._toggles.get(key)
        if t is not None and t.isChecked() != bool(self.cfg.get(key)):
            t.blockSignals(True); t.setChecked(bool(self.cfg.get(key))); t.blockSignals(False)
            t._on_toggled(t.isChecked())

    def _music_page(self):
        pg = Page("Музыкальный островок", "Текущий трек и живая волна поверх рабочего стола")
        pg.section("Предпросмотр")
        prev = QFrame(); prev.setObjectName("Preview"); prev.setFixedHeight(int(EH) + 52)
        pl = QHBoxLayout(prev); pl.addStretch(); pl.addWidget(self.preview); pl.addStretch()
        pg.add(prev)
        pg.section("Поведение")
        c = Card()
        c.add_row("Показывать островок", "Плавающая панель на рабочем столе", self._toggle("island_enabled"))
        c.add_row("Раскрывать при наведении", "Если выключено — раскрытие по клику", self._toggle("expand_on_hover"))
        c.add_row("Раскрывать при смене трека", "Островок на пару секунд раскроется, когда начнётся новый трек", self._toggle("expand_on_track"))
        c.add_row("Скрывать, когда ничего не играет", "Островок появится вместе с музыкой", self._toggle("hide_when_idle"))
        c.add_row("Прилипать к панели задач", "Перетащи островок на панель задач — он встанет в неё и будет раскрываться вверх", self._toggle("dock_to_taskbar"))
        c.add_row("Поверх всех окон", "Если выключить, островок будет на уровне обычных окон", self._toggle("always_on_top"))
        pg.add(c)
        pg.section("Внешний вид")
        c2 = Card()
        sty = Segmented([("bars", "Столбики"), ("wave", "Волна")], self.cfg.get("wave_style"))
        sty.changed.connect(lambda v: self.cfg.set("wave_style", v))
        c2.add_row("Стиль визуализатора", None, sty)
        col = Segmented([("cover", "Из обложки"), ("brand", "Фирменный")], self.cfg.get("wave_color"))
        col.changed.connect(lambda v: self.cfg.set("wave_color", v))
        c2.add_row("Цвет волны", "Подбирается под обложку текущего трека", col)
        sl = QSlider(Qt.Horizontal); sl.setRange(80, 140); sl.setPageStep(10); sl.setFixedWidth(150)
        sl.setValue(self.cfg.get("island_scale"))
        val = QLabel(f"{sl.value()}%"); val.setFixedWidth(44); val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sl.valueChanged.connect(lambda v: (val.setText(f"{v}%"), self.cfg.set("island_scale", v)))
        box = QWidget(); bl = QHBoxLayout(box); bl.setContentsMargins(0, 0, 0, 0); bl.addWidget(sl); bl.addWidget(val)
        c2.add_row("Размер", None, box)
        ss = QSlider(Qt.Horizontal); ss.setRange(50, 250); ss.setPageStep(10); ss.setFixedWidth(150)
        ss.setValue(self.cfg.get("wave_sensitivity"))
        sv = QLabel(f"{ss.value()}%"); sv.setFixedWidth(44); sv.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ss.valueChanged.connect(lambda v: (sv.setText(f"{v}%"), self.cfg.set("wave_sensitivity", v)))
        sbox = QWidget(); sl2 = QHBoxLayout(sbox); sl2.setContentsMargins(0, 0, 0, 0); sl2.addWidget(ss); sl2.addWidget(sv)
        c2.add_row("Чувствительность волны", "Выше — волна сильнее реагирует на звук, ниже — спокойнее", sbox)
        pg.add(c2)
        row = QHBoxLayout()
        b = Button("Сбросить позицию")
        b.clicked.connect(lambda: self.island.reset_position() if getattr(self, "island", None) else None)
        row.addWidget(b); row.addStretch(1)
        pg.col.addSpacing(6); pg.col.addLayout(row)
        pg.finish()
        return pg

    def _general_page(self):
        pg = Page("Основные", "Поведение самого приложения")
        pg.section("Запуск")
        c = Card()
        t = Toggle(autostart.is_enabled())
        t.toggled.connect(lambda v: (autostart.set_enabled(v), self.cfg.set("autostart", v)))
        c.add_row("Запускать вместе с Windows", "Isle стартует свёрнутым в трей", t)
        c.add_row("Закрытие окна сворачивает в трей", "Островок продолжит работать в фоне", self._toggle("close_to_tray"))
        pg.add(c)
        pg.section("Данные")
        c2 = Card()
        folder = Button("Открыть папку")
        folder.clicked.connect(self._open_data)
        c2.add_row("Папка с настройками и логом", str(data_dir()), folder)
        pg.add(c2)
        pg.finish()
        return pg

    def _updates_page(self):
        pg = Page("Обновления", "Isle обновляется через GitHub Releases")
        pg.section("Версия")
        c = Card()
        c.add_row("Установленная версия", None, QLabel(__version__))
        c.add_row("Проверять при запуске", "Тихо, без окон — только уведомление в трее", self._toggle("check_updates"))
        pg.add(c)
        pg.section("Статус")
        c2 = Card()
        box = QWidget(); v = QVBoxLayout(box); v.setContentsMargins(16, 14, 16, 14); v.setSpacing(10)
        self.lbl_status = QLabel("Ещё не проверялось"); self.lbl_status.setObjectName("RowTitle"); v.addWidget(self.lbl_status)
        self.lbl_notes = QLabel(""); self.lbl_notes.setObjectName("RowDesc"); self.lbl_notes.setWordWrap(True)
        self.lbl_notes.hide(); v.addWidget(self.lbl_notes)
        self.bar = QProgressBar(); self.bar.setRange(0, 100); self.bar.setTextVisible(False); self.bar.hide(); v.addWidget(self.bar)
        r = QHBoxLayout(); r.setSpacing(8)
        self.btn_check = Button("Проверить обновления"); self.btn_check.clicked.connect(lambda: self.check_updates())
        self.btn_install = Button("Скачать и установить", primary=True); self.btn_install.hide()
        self.btn_install.clicked.connect(self._install)
        r.addWidget(self.btn_check); r.addWidget(self.btn_install); r.addStretch(1)
        v.addLayout(r)
        c2.add_row_widget = None
        c2._lay.addWidget(box)
        pg.add(c2)
        pg.finish()
        return pg

    # --- обновления ------------------------------------------------------------------
    def check_updates(self, silent=False):
        self._silent = silent
        self.btn_check.setEnabled(False)
        self.lbl_status.setText("Проверяю…")
        self.updater.check(self.cfg.get("update_repo") or GITHUB_REPO)

    def _on_checked(self, info, err):
        self.btn_check.setEnabled(True)
        if err:
            self.lbl_status.setText(err)
            return
        if info is None:
            self.lbl_status.setText("У тебя последняя версия")
            self.btn_install.hide(); self.lbl_notes.hide()
            return
        self._info = info
        self.lbl_status.setText(f"Доступна версия {info.version}")
        self.panel_status.setObjectName("Ok"); self.panel_status.setStyleSheet("")
        self.panel_status.style().unpolish(self.panel_status); self.panel_status.style().polish(self.panel_status)
        self.panel_status.setText(f"Доступно обновление {info.version}")
        if info.notes:
            self.lbl_notes.setText(info.notes[:600]); self.lbl_notes.show()
        self.btn_install.show()
        if self._silent:
            self.update_available.emit(info.version)

    def _install(self):
        if not self._info:
            return
        self.btn_install.setEnabled(False); self.btn_check.setEnabled(False)
        self.bar.setValue(0); self.bar.show()
        self.lbl_status.setText("Скачиваю обновление…")
        self.updater.download(self._info)

    def _on_ready(self, path):
        self.lbl_status.setText("Устанавливаю и перезапускаюсь…")
        self.quitting = True
        Updater.install(path)
        QApplication.quit()

    def _on_failed(self, msg):
        self.lbl_status.setText(msg)
        self.bar.hide(); self.btn_install.setEnabled(True); self.btn_check.setEnabled(True)

    def _open_data(self):
        import os
        try:
            os.startfile(str(data_dir()))  # type: ignore[attr-defined]
        except Exception:
            pass

    # --- окно -------------------------------------------------------------------------
    def show_window(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    def quit_app(self):
        self.quitting = True
        QApplication.quit()

    def showEvent(self, e):
        if not self._dark_done:
            T.apply_dark_titlebar(self)
            self._dark_done = True
        super().showEvent(e)

    def closeEvent(self, e):
        if self.quitting or not self.cfg.get("close_to_tray") or not QSystemTrayIcon.isSystemTrayAvailable():
            self.quitting = True
            QApplication.quit()
            e.accept()
        else:
            e.ignore()
            self.hide()
