"""The small interface between "where samples come from" and everything else.

A future ESP32-S3 USB source implements FrameSource. Its wire protocol is not
defined yet, and nothing here assumes one.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from fmcw import RadarConfig


@dataclass(frozen=True)
class Frame:
    """One group of chirps, which is processed into one screen update."""

    seq: int
    """Counts up by 1 per frame at the source. A gap means frames were lost."""

    chirps_v: np.ndarray
    """Shape (chirps_per_frame, samples_per_chirp), volts at the ADC input."""

    config: RadarConfig
    """The settings these samples were taken with."""

    captured_s: float
    """time.perf_counter() on this PC when the last sample of the frame existed.
    Latency is counted from here. A hardware source can only know when the data
    reached the PC unless it has a shared clock, so state which one it reports."""

    truth: tuple[tuple[float, float], ...] | None = None
    """(range_m, amplitude_v) of simulated targets. None for real data."""


class FrameSource(ABC):
    is_simulated: bool
    """Drives the on-screen banner. Only a real hardware source may say False."""

    description: str
    chirps_per_frame: int

    @abstractmethod
    def read_frame(self, timeout_s: float) -> Frame | None:
        """Wait up to timeout_s for the next frame; None if none is ready."""

    def close(self) -> None:
        """Release the device or file. Nothing to do by default."""
