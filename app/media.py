"""Источник данных о музыке: Windows Media Session (SMTC) + демо-режим."""
import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QBuffer, QIODevice, QObject, QPointF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter

log = logging.getLogger("isle.media")


@dataclass
class MediaState:
    has_session: bool = False
    key: str = ""
    title: str = ""
    artist: str = ""
    playing: bool = False
    position: float = 0.0
    duration: float = 0.0
    cover: Optional[bytes] = None      # приходит один раз, когда обложка получена


class MediaProvider(QObject):
    """Читает системную медиа-сессию (Spotify, Яндекс Музыка, браузер, плееры...)."""
    state_changed = Signal(object)

    def __init__(self):
        super().__init__()
        self._loop = None
        self._manager = None
        self._stop = False
        self._key = None
        self._cover_ok = False
        self._cover_tries = 0
        self._PS = None

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="media").start()

    def stop(self):
        self._stop = True

    def _run(self):
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._poll())
        except Exception:
            log.exception("медиа-поток остановился")
            self.state_changed.emit(MediaState())

    async def _poll(self):
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as SessionManager,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
        )
        self._PS = PlaybackStatus
        self._manager = await SessionManager.request_async()
        while not self._stop:
            try:
                st = await self._read()
            except Exception:
                log.exception("не удалось прочитать медиа-сессию")
                st = MediaState()
            self.state_changed.emit(st)
            await asyncio.sleep(0.5)

    async def _read(self) -> MediaState:
        from datetime import datetime, timezone
        s = self._manager.get_current_session()
        if s is None:
            self._key = None
            return MediaState()
        props = await s.try_get_media_properties_async()
        title = props.title or ""
        artist = props.artist or props.album_artist or ""
        if not title and not artist:
            return MediaState()
        key = f"{s.source_app_user_model_id}|{title}|{artist}"
        if key != self._key:
            self._key, self._cover_ok, self._cover_tries = key, False, 0
        cover = None
        if not self._cover_ok and self._cover_tries < 8:
            self._cover_tries += 1
            cover = await self._thumb(props)
            self._cover_ok = bool(cover)
        info = s.get_playback_info()
        tl = s.get_timeline_properties()
        playing = info.playback_status == self._PS.PLAYING
        pos = tl.position.total_seconds()
        dur = (tl.end_time - tl.start_time).total_seconds()
        if playing:
            try:
                pos += (datetime.now(timezone.utc) - tl.last_updated_time).total_seconds()
            except Exception:
                pass
        pos = max(0.0, min(pos, dur)) if dur > 0 else 0.0
        return MediaState(True, key, title, artist, playing, pos, max(dur, 0.0), cover)

    async def _thumb(self, props) -> Optional[bytes]:
        try:
            from winsdk.windows.storage.streams import Buffer, DataReader, InputStreamOptions
            ref = props.thumbnail
            if ref is None:
                return None
            stream = await ref.open_read_async()
            size = stream.size
            if not size:
                return None
            buf = Buffer(size)
            await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
            data = bytearray(buf.length)
            DataReader.from_buffer(buf).read_bytes(data)
            return bytes(data)
        except Exception:
            log.exception("не удалось получить обложку")
            return None

    # --- управление -------------------------------------------------------
    async def _call(self, name, *args):
        s = self._manager.get_current_session() if self._manager else None
        if s is None:
            return
        try:
            await getattr(s, name)(*args)
        except Exception:
            log.exception("команда %s не выполнена", name)
        await asyncio.sleep(0.12)
        self.state_changed.emit(await self._read())

    def _submit(self, name, *args):
        if self._loop and self._manager:
            asyncio.run_coroutine_threadsafe(self._call(name, *args), self._loop)

    def toggle(self): self._submit("try_toggle_play_pause_async")
    def next(self): self._submit("try_skip_next_async")
    def prev(self): self._submit("try_skip_previous_async")
    def seek(self, seconds: float): self._submit("try_change_playback_position_async", int(seconds * 10_000_000))


class DemoProvider(QObject):
    """Фейковый плеер — для предпросмотра интерфейса без Windows (--demo)."""
    state_changed = Signal(object)
    TRACKS = [
        ("Midnight City", "Neon Harbor", "#ff5d8f", "#3c45a5"),
        ("Glass Hours", "Low Tide", "#23a55a", "#0b3d2e"),
        ("Paper Moons", "Aurora Static", "#f0b232", "#7a2e0e"),
    ]
    DURATION = 214.0

    def __init__(self):
        super().__init__()
        self._i, self._pos, self._playing = 0, 41.0, True
        self._new_track = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._timer.start(250)
        self._emit()

    def stop(self):
        self._timer.stop()

    def _cover(self) -> bytes:
        _, _, c1, c2 = self.TRACKS[self._i]
        img = QImage(300, 300, QImage.Format_RGB32)
        qp = QPainter(img)
        qp.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, 300, 300)
        g.setColorAt(0, QColor(c1))
        g.setColorAt(1, QColor(c2))
        qp.fillRect(img.rect(), g)
        qp.setPen(Qt.NoPen)
        qp.setBrush(QColor(255, 255, 255, 40))
        qp.drawEllipse(QPointF(210, 90), 110, 110)
        qp.setBrush(QColor(0, 0, 0, 50))
        qp.drawEllipse(QPointF(80, 230), 90, 90)
        qp.end()
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        return bytes(buf.data())

    def _emit(self):
        title, artist, _, _ = self.TRACKS[self._i]
        cover = None
        if self._new_track:
            cover, self._new_track = self._cover(), False
        self.state_changed.emit(MediaState(True, f"demo{self._i}", title, artist,
                                           self._playing, self._pos, self.DURATION, cover))

    def _tick(self):
        if self._playing:
            self._pos += 0.25
            if self._pos >= self.DURATION:
                self.next()
                return
        self._emit()

    def toggle(self): self._playing = not self._playing; self._emit()
    def next(self): self._i = (self._i + 1) % len(self.TRACKS); self._pos, self._new_track = 0.0, True; self._emit()
    def prev(self): self._i = (self._i - 1) % len(self.TRACKS); self._pos, self._new_track = 0.0, True; self._emit()
    def seek(self, seconds): self._pos = seconds; self._emit()
