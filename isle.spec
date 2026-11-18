# PyInstaller: onedir-сборка без консоли -> dist/Isle/Isle.exe
from PyInstaller.utils.hooks import collect_all

datas, binaries, hidden = [], [], []
for pkg in ("winsdk", "pyaudiowpatch"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h

a = Analysis(
    ["main.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtMultimedia", "PySide6.QtPdf"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Isle", console=False,
          icon="assets/icon.ico", upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Isle", upx=False)
