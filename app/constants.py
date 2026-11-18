"""Общие константы приложения."""
import logging
import os
import sys
from pathlib import Path

APP_NAME = "Isle"
# Репозиторий GitHub вида "owner/repo", откуда берутся обновления (Releases).
# Можно переопределить в config.json ключом "update_repo".
GITHUB_REPO = "Sugguest/isle"
SINGLE_INSTANCE_KEY = "isle-single-instance-5c1e"
IS_WINDOWS = sys.platform == "win32"


def data_dir() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        filename=str(data_dir() / "isle.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )
    return logging.getLogger("isle")
