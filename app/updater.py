"""Автообновление через GitHub Releases: проверка → скачивание Setup.exe → тихая установка."""
import hashlib
import json
import logging
import re
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from .constants import IS_WINDOWS
from .version import __version__

log = logging.getLogger("isle.updater")
_HEADERS = {"User-Agent": "Isle-Updater", "Accept": "application/vnd.github+json"}


@dataclass
class UpdateInfo:
    version: str
    url: str
    notes: str
    size: int
    sha256: Optional[str]


def _ver(s: str):
    nums = [int(x) for x in re.findall(r"\d+", s)][:3]
    return tuple(nums + [0] * (3 - len(nums)))


class Updater(QObject):
    check_done = Signal(object, str)   # (UpdateInfo | None, текст ошибки)
    progress = Signal(int)
    ready = Signal(str)                # путь к скачанному установщику
    failed = Signal(str)

    def check(self, repo: str):
        threading.Thread(target=self._check, args=(repo,), daemon=True).start()

    def download(self, info: UpdateInfo):
        threading.Thread(target=self._download, args=(info,), daemon=True).start()

    def _check(self, repo: str):
        if not repo or repo.startswith("OWNER/"):
            self.check_done.emit(None, "Источник обновлений не настроен")
            return
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/releases/latest", headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            self.check_done.emit(None, "Релизов пока нет" if e.code == 404 else f"Ошибка GitHub: {e.code}")
            return
        except Exception as e:
            log.warning("проверка обновлений: %s", e)
            self.check_done.emit(None, "Не удалось проверить обновления (нет соединения?)")
            return
        tag = data.get("tag_name", "")
        if _ver(tag) <= _ver(__version__):
            self.check_done.emit(None, "")
            return
        asset = next((a for a in data.get("assets", [])
                      if a["name"].lower().endswith(".exe") and "setup" in a["name"].lower()), None)
        if asset is None:
            self.check_done.emit(None, "В релизе нет установщика Setup.exe")
            return
        digest = (asset.get("digest") or "")
        sha = digest.split(":", 1)[1] if digest.startswith("sha256:") else None
        self.check_done.emit(UpdateInfo(tag.lstrip("vV"), asset["browser_download_url"],
                                        (data.get("body") or "").strip(), asset.get("size", 0), sha), "")

    def _download(self, info: UpdateInfo):
        path = Path(tempfile.gettempdir()) / f"Isle-Setup-{info.version}.exe"
        try:
            req = urllib.request.Request(info.url, headers={"User-Agent": "Isle-Updater"})
            h, done, last = hashlib.sha256(), 0, -1
            with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as f:
                total = int(r.headers.get("Content-Length") or info.size or 0)
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    if total and done * 100 // total != last:
                        last = done * 100 // total
                        self.progress.emit(last)
            if info.sha256 and h.hexdigest().lower() != info.sha256.lower():
                path.unlink(missing_ok=True)
                self.failed.emit("Контрольная сумма скачанного файла не совпала")
                return
            self.ready.emit(str(path))
        except Exception as e:
            log.exception("скачивание обновления")
            self.failed.emit(f"Не удалось скачать обновление: {e}")

    @staticmethod
    def install(path: str):
        """Запускает установщик отдельным процессом; приложение после этого нужно закрыть."""
        flags = 0x00000008 | 0x00000200 if IS_WINDOWS else 0   # DETACHED_PROCESS | NEW_PROCESS_GROUP
        subprocess.Popen([path, "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS"],
                         close_fds=True, creationflags=flags)
