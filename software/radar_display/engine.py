"""Background loop: read a frame, process it, publish the latest snapshot."""

import threading
import time
import traceback

from .metrics import StreamStats
from .processing import DetectionSettings, process_frame
from .snapshot import SWEEP_NOTES, TARGETS, build_snapshot
from .source import FrameSource

WINDOWS = ("hann", "rect")
READ_TIMEOUT_S = 0.2


class Engine:
    def __init__(self, source: FrameSource, detection: DetectionSettings | None = None):
        self.source = source
        self.detection = detection or DetectionSettings()
        self.stats = StreamStats()
        self.window = "hann"
        self._condition = threading.Condition()
        self._latest = None
        self._version = 0
        self._error = None
        self._stop = threading.Event()
        self._thread = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.source.close()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def set_window(self, window: str) -> None:
        if window not in WINDOWS:
            raise ValueError(f"unknown window: {window!r}")
        self.window = window

    def step(self) -> bool:
        """Handle at most one frame. True if a snapshot was published."""
        frame = self.source.read_frame(READ_TIMEOUT_S)
        if frame is None:
            return False
        window = self.window
        result = process_frame(frame.config, frame.chirps_v, window, self.detection)
        self.stats.add(frame.seq, frame.captured_s, time.perf_counter())
        snapshot = build_snapshot(frame, result, self.stats, window, self.detection)
        # Wall-clock time of capture, so a browser on this same PC can measure
        # capture-to-screen delay with its own clock.
        snapshot["captured_epoch_ms"] = (
            time.time() - (time.perf_counter() - frame.captured_s)
        ) * 1e3
        snapshot["source"] = {
            "is_simulated": self.source.is_simulated,
            "description": self.source.description,
        }
        simulation = getattr(self.source, "settings_dict", None)
        snapshot["simulation"] = simulation() if simulation else None
        snapshot["sweep_notes"] = SWEEP_NOTES
        snapshot["targets"] = TARGETS
        with self._condition:
            self._latest = snapshot
            self._error = None
            self._version += 1
            self._condition.notify_all()
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.step()
            except Exception as error:  # noqa: BLE001 - keep serving, and show it
                traceback.print_exc()
                with self._condition:
                    self._error = f"{type(error).__name__}: {error}"
                    self._version += 1
                    self._condition.notify_all()
                self._stop.wait(1.0)

    def wait_for_update(self, after_version: int, timeout_s: float):
        """(version, snapshot, error). Slow readers get only the newest frame."""
        with self._condition:
            self._condition.wait_for(lambda: self._version > after_version, timeout_s)
            return self._version, self._latest, self._error
