"""Захват системного звука (WASAPI loopback) и разбор на частотные полосы."""
import logging
import threading
import time

import numpy as np

log = logging.getLogger("isle.audio")

BANDS = 32
FRAME = 2048


class AudioAnalyzer:
    """Фоновый поток: слушает то, что играет в выбранном по умолчанию выходе."""

    def __init__(self):
        self.levels = np.zeros(BANDS, dtype=np.float32)   # 0..1 по полосам
        self.db = np.full(BANDS, -120.0, dtype=np.float32)  # сырые dB по полосам
        self.stamp = 0.0                                  # time.monotonic() последнего кадра
        self.ok = False                                   # удалось ли открыть loopback
        self._stop = threading.Event()
        self._buf = np.zeros(FRAME, dtype=np.float32)
        self._win = np.hanning(FRAME).astype(np.float32)
        self.tilt = np.linspace(0.0, 0.18, BANDS).astype(np.float32)
        self._tilt = self.tilt
        self._pairs = []

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="audio").start()

    def stop(self):
        self._stop.set()

    # --- поток -----------------------------------------------------------
    def _run(self):
        try:
            import pyaudiowpatch as pa
        except Exception:
            log.exception("pyaudiowpatch недоступен — волна будет синтетической")
            return
        while not self._stop.is_set():
            try:
                self._capture(pa)
            except Exception:
                log.exception("ошибка захвата звука")
            self.ok = False
            self._stop.wait(2.0)

    @staticmethod
    def _default_loopback(pa):
        p = pa.PyAudio()
        try:
            wasapi = p.get_host_api_info_by_type(pa.paWASAPI)
            dev = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
            if not dev.get("isLoopbackDevice"):
                for lb in p.get_loopback_device_info_generator():
                    if dev["name"] in lb["name"]:
                        return dict(lb)
                raise RuntimeError("loopback-устройство не найдено")
            return dict(dev)
        finally:
            p.terminate()

    def _capture(self, pa):
        dev = self._default_loopback(pa)
        ch = max(1, int(dev["maxInputChannels"]))
        rate = int(dev["defaultSampleRate"])
        self._make_pairs(rate)

        def cb(data, frames, t, status):
            try:
                self._process(data, ch)
            except Exception:
                pass
            return (None, pa.paContinue)

        p = pa.PyAudio()
        try:
            stream = p.open(format=pa.paInt16, channels=ch, rate=rate, input=True,
                            input_device_index=dev["index"], frames_per_buffer=1024,
                            stream_callback=cb)
            self.ok = True
            log.info("loopback: %s, %s Hz, %s ch", dev["name"], rate, ch)
            while not self._stop.wait(3.0):
                try:
                    if self._default_loopback(pa)["name"] != dev["name"]:
                        log.info("сменилось устройство вывода — переподключаюсь")
                        break
                except Exception:
                    break
            stream.stop_stream()
            stream.close()
        finally:
            p.terminate()

    def _make_pairs(self, rate):
        nb = FRAME // 2 + 1
        freqs = np.geomspace(50.0, min(14000.0, rate / 2 * 0.95), BANDS + 1)
        bins = freqs / (rate / FRAME)
        edges = [max(1, int(round(bins[0])))]
        for b in bins[1:]:
            edges.append(min(nb - 1, max(int(round(b)), edges[-1] + 1)))
        self._pairs = [(edges[i], max(edges[i + 1], edges[i] + 1)) for i in range(BANDS)]

    def _process(self, data, ch):
        x = np.frombuffer(data, dtype=np.int16)
        if ch > 1:
            x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
        x = x.astype(np.float32) / 32768.0
        n = len(x)
        if n >= FRAME:
            self._buf = x[-FRAME:]
        else:
            self._buf = np.concatenate((self._buf[n:], x))
        mag = np.abs(np.fft.rfft(self._buf * self._win)) / (FRAME / 4)
        vals = np.fromiter((mag[a:b].max() for a, b in self._pairs), dtype=np.float32, count=BANDS)
        db = 20.0 * np.log10(vals + 1e-6)
        self.db = db.astype(np.float32)
        self.levels = np.clip((db + 72.0) / 56.0 + self._tilt, 0.0, 1.0).astype(np.float32)
        self.stamp = time.monotonic()
