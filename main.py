"""Isle — точка входа."""
import sys

from PySide6.QtGui import QFont
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from app import theme as T
from app.audio import AudioAnalyzer
from app.config import Config
from app.constants import APP_NAME, IS_WINDOWS, SINGLE_INSTANCE_KEY, setup_logging
from app.icon import make_app_icon
from app.island import IslandWidget
from app.main_window import MainWindow
from app.media import DemoProvider, MediaProvider
from app.tray import Tray
from app.updater import Updater


def main() -> int:
    log = setup_logging()
    demo = "--demo" in sys.argv or not IS_WINDOWS
    minimized = "--minimized" in sys.argv

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    # одна копия приложения: повторный запуск просто показывает окно первой
    sock = QLocalSocket()
    sock.connectToServer(SINGLE_INSTANCE_KEY)
    if sock.waitForConnected(200):
        sock.write(b"show"); sock.flush(); sock.waitForBytesWritten(500)
        return 0
    QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
    server = QLocalServer()
    server.listen(SINGLE_INSTANCE_KEY)

    app.setFont(QFont(T.FONT, 10))
    app.setStyleSheet(T.QSS)
    app.setWindowIcon(make_app_icon())

    cfg = Config()
    media = DemoProvider() if demo else MediaProvider()
    audio = AudioAnalyzer()
    updater = Updater()
    window = MainWindow(cfg, media, audio, updater)
    island = IslandWidget(cfg, media, audio)
    island.open_requested.connect(window.show_window)
    window._island_ref = island
    window.island = island
    server.newConnection.connect(lambda: (server.nextPendingConnection(), window.show_window()))
    tray = Tray(window, cfg)

    media.start()
    if not demo:
        audio.start()
    if cfg.get("check_updates") and not demo:
        window.check_updates(silent=True)
    if not minimized:
        window.show()

    def cleanup():
        media.stop(); audio.stop(); cfg.save()
    app.aboutToQuit.connect(cleanup)
    log.info("Isle запущен (demo=%s)", demo)
    code = app.exec()
    del tray
    return code


if __name__ == "__main__":
    sys.exit(main())
