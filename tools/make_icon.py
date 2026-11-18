"""Генерирует assets/icon.ico из кода иконки (нужны PySide6 и Pillow)."""
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice
from app.icon import make_icon_image

buf = QBuffer(); buf.open(QIODevice.WriteOnly)
make_icon_image(256).save(buf, "PNG")
img = Image.open(io.BytesIO(bytes(buf.data())))
out = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
img.save(out, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
print("saved", out)
