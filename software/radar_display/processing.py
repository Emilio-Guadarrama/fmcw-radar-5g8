"""One frame of chirps -> range profile, noise level, threshold and detections.

The FFT, window and range scaling come from sim/fmcw.py (range_fft).

Method (all of it assumes targets hold still during a frame):

1. Integration: average the chirps sample by sample, then range_fft. Echoes
   add in step while noise partly cancels (10 log10(M) dB for M chirps,
   calculated). A moving target would partly or fully cancel.
2. Noise: subtract that average from every chirp. A still target disappears,
   leaving noise. For range cell k, with M chirps and R_m the spectrum of
   leftover m:  Pn(k) = sum |R_m(k)|^2 / (M (M - 1))
   which estimates the noise power left in the averaged spectrum.
3. Threshold: for complex Gaussian noise that is independent from chirp to
   chirp, |average(k)|^2 / Pn(k) follows an F(2, 2M - 2) distribution when
   there is no target, so a false-alarm probability Pfa per cell needs
       threshold(k) = a Pn(k),   a = (M - 1) (Pfa^(-1/(M-1)) - 1)
   This holds away from 0 Hz and fs/2.
4. Detection: a range cell above threshold that is also a local peak, and is
   not explained by the window leakage of a stronger detection.

Limits: anything that holds still is "a target" here, including leakage and
clutter on real hardware. Motion or chirp-to-chirp jitter would raise Pn.
"""

from dataclasses import dataclass

import numpy as np
from fmcw import RadarConfig, make_window, range_fft

PAD_FACTOR = 16
# Assumption: a weaker peak must be 6 dB above the worst-case window leakage of
# the stronger ones to count as a separate target.
LEAKAGE_MARGIN = 2.0
_ENVELOPE_OVERSAMPLING = 64


@dataclass(frozen=True)
class DetectionSettings:
    pfa: float = 1e-4  # per range cell per frame, decision 002 target
    min_range_m: float = 3.0  # decision 002 target
    max_range_m: float = 30.0  # decision 002: evaluated to 30 m


@dataclass(frozen=True)
class Detection:
    range_m: float
    snr_db: float  # estimated, after window and integration
    amplitude_v: float
    beat_hz: float
    cell: int


@dataclass(frozen=True)
class FrameResult:
    range_m: np.ndarray  # zero-padded axis, for drawing and peak position
    amplitude_v: np.ndarray
    cell_range_m: np.ndarray  # one entry per range cell, c/(2B) apart
    cell_amplitude_v: np.ndarray
    noise_power_v2: np.ndarray  # per cell, in the integrated spectrum
    threshold_v: np.ndarray  # per cell, same units as amplitude_v
    gate: np.ndarray  # indices of the cells that are tested
    detections: tuple[Detection, ...]  # strongest first

    @property
    def noise_floor_v(self) -> float:
        """Typical noise amplitude over the tested cells."""
        return float(np.sqrt(np.median(self.noise_power_v2[self.gate])))


def threshold_factor(n_chirps: int, pfa: float) -> float:
    """a in threshold power = a * Pn (see module notes)."""
    if n_chirps < 2:
        raise ValueError("at least 2 chirps are needed to estimate noise")
    if not 0 < pfa < 1:
        raise ValueError("pfa must be between 0 and 1")
    dof = n_chirps - 1
    return dof * (pfa ** (-1 / dof) - 1)


def quantization_noise_power_v2(cfg: RadarConfig, window: str, n_chirps: int) -> float:
    """Noise power per cell from ADC rounding alone (white, LSB^2/12).

    Used as a floor so identical chirps cannot give a zero threshold.
    """
    lsb = 2 * cfg.adc_full_scale_v / 2**cfg.adc_bits
    w = make_window(window, cfg.n_samples)
    return float(4 * (lsb**2 / 12) * np.sum(w**2) / np.sum(w) ** 2 / n_chirps)


def noise_power(cfg: RadarConfig, chirps_v: np.ndarray, window: str) -> np.ndarray:
    """Pn(k): noise power per range cell in the integrated spectrum."""
    m = chirps_v.shape[0]
    if m < 2:
        raise ValueError("at least 2 chirps are needed to estimate noise")
    leftovers = chirps_v - chirps_v.mean(axis=0)
    total = sum(range_fft(cfg, x, window)[1] ** 2 for x in leftovers)
    return np.maximum(
        total / (m * (m - 1)), quantization_noise_power_v2(cfg, window, m)
    )


def tested_cells(cell_range_m: np.ndarray, settings: DetectionSettings) -> np.ndarray:
    """Cells within half a cell of the range span, away from 0 Hz and fs/2."""
    half = (cell_range_m[1] - cell_range_m[0]) / 2
    inside = (cell_range_m >= settings.min_range_m - half) & (
        cell_range_m <= settings.max_range_m + half
    )
    inside[:2] = False
    inside[-2:] = False
    return np.flatnonzero(inside)


def leakage_envelope(window: str, n: int) -> np.ndarray:
    """Largest window response at an offset of d cells or more, relative to the
    peak. Entry i is for d = i / 64 cells."""
    nfft = n * _ENVELOPE_OVERSAMPLING
    response = np.abs(np.fft.rfft(make_window(window, n), nfft))
    response /= response[0]
    return np.maximum.accumulate(response[::-1])[::-1]


def _refine_peak(r: np.ndarray, a: np.ndarray, cell: int) -> tuple[float, float]:
    """(range, amplitude) of the padded-spectrum peak near a range cell.

    Same log-parabola refinement as fmcw.estimate_range_m, but for any peak
    rather than only the strongest one.
    """
    centre = cell * PAD_FACTOR
    half = 3 * PAD_FACTOR // 4
    low = max(centre - half, 1)
    high = min(centre + half + 1, a.size - 1)
    k = low + int(np.argmax(a[low:high]))
    left, mid, right = np.log(a[k - 1 : k + 2] + 1e-30)
    curvature = left - 2 * mid + right
    delta = 0.5 * (left - right) / curvature if curvature < 0 else 0.0
    delta = float(np.clip(delta, -0.5, 0.5))
    amplitude = float(np.exp(mid - 0.25 * (left - right) * delta))
    return float(r[k] + delta * (r[1] - r[0])), amplitude


def find_detections(
    cfg: RadarConfig,
    window: str,
    r: np.ndarray,
    a: np.ndarray,
    cell_amplitude_v: np.ndarray,
    noise_power_v2: np.ndarray,
    threshold_v: np.ndarray,
    gate: np.ndarray,
    settings: DetectionSettings,
) -> tuple[Detection, ...]:
    cells = cell_amplitude_v
    cell_size = cfg.range_resolution_m
    candidates = []
    for k in gate:
        if not (cells[k] > threshold_v[k]):
            continue
        if not (cells[k] >= cells[k - 1] and cells[k] > cells[k + 1]):
            continue
        range_m, amplitude = _refine_peak(r, a, int(k))
        if not (
            settings.min_range_m - cell_size / 2
            <= range_m
            <= settings.max_range_m + cell_size / 2
        ):
            continue
        candidates.append((amplitude, range_m, int(k)))

    envelope = leakage_envelope(window, cfg.n_samples)
    accepted: list[Detection] = []
    for amplitude, range_m, k in sorted(candidates, reverse=True):
        leakage = 0.0
        for stronger in accepted:
            offset_cells = abs(range_m - stronger.range_m) / cell_size
            # 0.25 cell of slack for error in the two peak positions
            i = int(max(offset_cells - 0.25, 0.0) * _ENVELOPE_OVERSAMPLING)
            leakage += stronger.amplitude_v * envelope[min(i, envelope.size - 1)]
        if amplitude <= LEAKAGE_MARGIN * leakage:
            continue
        local_noise = float(np.mean(noise_power_v2[max(k - 3, 1) : k + 4]))
        # The peak holds signal plus noise, so take one noise unit off.
        snr = max(amplitude**2 / local_noise - 1.0, 0.1)
        accepted.append(
            Detection(
                range_m=range_m,
                snr_db=float(10 * np.log10(snr)),
                amplitude_v=amplitude,
                beat_hz=float(cfg.beat_frequency_hz(range_m)),
                cell=k,
            )
        )
    return tuple(accepted)


def process_frame(
    cfg: RadarConfig,
    chirps_v: np.ndarray,
    window: str = "hann",
    settings: DetectionSettings | None = None,
) -> FrameResult:
    settings = settings or DetectionSettings()
    chirps_v = np.asarray(chirps_v, dtype=float)
    if chirps_v.ndim != 2 or chirps_v.shape[1] != cfg.n_samples:
        raise ValueError(f"expected (chirps, {cfg.n_samples}) samples")
    average = chirps_v.mean(axis=0)
    r, a = range_fft(cfg, average, window, PAD_FACTOR * average.size)
    cell_range, cell_amplitude = range_fft(cfg, average, window)
    pn = noise_power(cfg, chirps_v, window)
    threshold = np.sqrt(threshold_factor(chirps_v.shape[0], settings.pfa) * pn)
    gate = tested_cells(cell_range, settings)
    detections = find_detections(
        cfg, window, r, a, cell_amplitude, pn, threshold, gate, settings
    )
    return FrameResult(
        r, a, cell_range, cell_amplitude, pn, threshold, gate, detections
    )
