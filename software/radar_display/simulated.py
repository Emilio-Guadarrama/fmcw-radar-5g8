"""Simulated frame source built on sim/fmcw.py. No hardware is touched.

Everything about the scene is an assumption, not a link budget: echo voltage,
noise level, and the 1/range^2 amplitude law (point target of constant radar
cross-section in free space).
"""

import math
import threading
import time
from dataclasses import asdict, dataclass, replace

import fmcw
import numpy as np

from .source import Frame, FrameSource

CHIRPS_PER_FRAME = 16  # decision 002 target
# Assumption: a little above the 10 Hz target, so timer jitter does not hide it.
FRAME_RATE_HZ = 12.5
REFERENCE_RANGE_M = 3.0
REFERENCE_AMPLITUDE_V = 0.4  # assumption: echo peak voltage at 3 m
MAX_AMPLITUDE_V = 0.8
MOVING_SPEED_M_PER_S = 1.0
MOVING_SPAN_M = (4.0, 28.0)
THREE_TARGETS_M = (6.0, 14.0, 24.0)

SWEEPS = {
    "115": fmcw.RadarConfig(),
    "150": fmcw.CONDUCTED_150MHZ,
}

SCENES = ("single", "pair", "moving", "three", "empty")

# name: (lowest, highest) accepted value
LIMITS = {
    "distance_m": (3.0, 40.0),
    "separation_m": (0.5, 5.0),
    "noise_mv": (1.0, 100.0),
}


@dataclass(frozen=True)
class SimSettings:
    sweep: str = "115"
    scene: str = "single"
    distance_m: float = 12.0
    separation_m: float = 2.5
    noise_mv: float = 10.0  # assumption: RMS noise per ADC sample


def validated(settings: SimSettings, changes: dict) -> SimSettings:
    """Return settings with changes applied, or raise ValueError."""
    clean = {}
    for key, value in changes.items():
        if key == "sweep":
            if value not in tuple(SWEEPS):
                raise ValueError(f"unknown sweep: {value!r}")
        elif key == "scene":
            if value not in SCENES:
                raise ValueError(f"unknown scene: {value!r}")
        elif key in LIMITS:
            low, high = LIMITS[key]
            is_number = isinstance(value, int | float) and not isinstance(value, bool)
            if not is_number or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{key} must be a number from {low} to {high}")
            value = float(value)
        else:
            raise ValueError(f"unknown setting: {key!r}")
        clean[key] = value
    return replace(settings, **clean)


def echo_amplitude_v(range_m: float) -> float:
    """Assumed echo peak voltage: falls as 1/range^2 (power as 1/range^4)."""
    return min(
        REFERENCE_AMPLITUDE_V * (REFERENCE_RANGE_M / range_m) ** 2, MAX_AMPLITUDE_V
    )


def moving_range_m(time_s: float) -> float:
    """Back and forth across MOVING_SPAN_M at constant speed."""
    low, high = MOVING_SPAN_M
    span = high - low
    travelled = (MOVING_SPEED_M_PER_S * time_s) % (2 * span)
    return low + (travelled if travelled <= span else 2 * span - travelled)


def scene_targets(settings: SimSettings, time_s: float) -> tuple:
    """(range_m, amplitude_v) pairs. Targets hold still within one frame."""
    d = settings.distance_m
    if settings.scene == "single":
        ranges = [(d, echo_amplitude_v(d))]
    elif settings.scene == "pair":
        # Two equal echoes, as in the two-target requirement.
        amplitude = echo_amplitude_v(d)
        ranges = [(d, amplitude), (d + settings.separation_m, amplitude)]
    elif settings.scene == "moving":
        r = moving_range_m(time_s)
        ranges = [(r, echo_amplitude_v(r))]
    elif settings.scene == "three":
        ranges = [(r, echo_amplitude_v(r)) for r in THREE_TARGETS_M]
    else:
        ranges = []
    return tuple(ranges)


class SimulatedSource(FrameSource):
    """Produces frames on a fixed schedule, as a streaming device would.

    If the reader falls behind by a whole frame period or more, the missed
    frames are skipped and show up as a gap in seq.
    """

    is_simulated = True
    description = "Simulated data (sim/fmcw.py). No radar hardware is connected."
    chirps_per_frame = CHIRPS_PER_FRAME

    def __init__(
        self,
        settings: SimSettings | None = None,
        frame_rate_hz: float = FRAME_RATE_HZ,
        seed: int | None = None,
        clock=time.perf_counter,
        sleep=time.sleep,
    ):
        if not frame_rate_hz > 0:
            raise ValueError("frame_rate_hz must be positive")
        self.frame_rate_hz = frame_rate_hz
        self._period_s = 1.0 / frame_rate_hz
        self._settings = settings or SimSettings()
        self._rng = np.random.default_rng(seed)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_seq = 0
        self._deadline_s = None
        self._to_drop = 0

    @property
    def settings(self) -> SimSettings:
        with self._lock:
            return self._settings

    def settings_dict(self) -> dict:
        return asdict(self.settings)

    def update(self, changes: dict) -> None:
        with self._lock:
            self._settings = validated(self._settings, changes)

    def drop_frames(self, count: int) -> None:
        """Pretend the link lost the next `count` frames (to test the display)."""
        with self._lock:
            self._to_drop += count

    def read_frame(self, timeout_s: float) -> Frame | None:
        now = self._clock()
        if self._deadline_s is None:
            self._deadline_s = now + self._period_s
        with self._lock:
            lost, self._to_drop = self._to_drop, 0
            settings = self._settings
        self._skip(lost)
        late_s = now - self._deadline_s
        if late_s >= self._period_s:
            self._skip(int(late_s // self._period_s))
        if self._deadline_s - now > timeout_s:
            self._sleep(timeout_s)
            return None

        seq, deadline = self._next_seq, self._deadline_s
        config = SWEEPS[settings.sweep]
        targets = scene_targets(settings, seq * self._period_s)
        # Generated before waiting, so the cost of simulating is not counted
        # as processing latency.
        chirps = np.stack(
            [
                fmcw.capture(config, targets, settings.noise_mv / 1e3, self._rng)
                for _ in range(self.chirps_per_frame)
            ]
        )
        wait_s = deadline - self._clock()
        if wait_s > 0:
            self._sleep(wait_s)
        self._next_seq += 1
        self._deadline_s += self._period_s
        return Frame(seq, chirps, config, deadline, targets)

    def _skip(self, count: int) -> None:
        self._next_seq += count
        self._deadline_s += count * self._period_s
