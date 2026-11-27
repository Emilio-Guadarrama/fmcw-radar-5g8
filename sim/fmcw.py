"""Baseband model of an FMCW radar: chirp, dechirp, noise, ADC and range FFT.

Simulation only. Nothing here is a measurement.

Model assumptions:
- Ideal linear sawtooth chirp: no PLL settling, nonlinearity or phase noise.
- Static point targets, one real (not I/Q) mixer output.
- Target amplitudes and noise level are inputs in volts at the ADC.
  They do not come from a link budget.
- No TX-to-RX leakage, cable delay, analog filters or anti-alias filter.
- Ideal ADC: uniform quantizer with clipping.
"""

from dataclasses import dataclass

import numpy as np

C = 299_792_458.0  # speed of light in vacuum, m/s (exact, SI definition)


@dataclass(frozen=True)
class RadarConfig:
    # Default sweep: radiated design case, 5.730-5.845 GHz (assumption, see
    # docs/decisions/001-sweep.md). It does not clear the radar to transmit.
    f_start_hz: float = 5.730e9
    bandwidth_hz: float = 115e6
    chirp_s: float = 1e-3  # assumption (charter)
    sample_rate_hz: float = 100e3  # assumption (charter)
    adc_bits: int = 12  # assumption, ADC not selected until Gate 2
    adc_full_scale_v: float = 1.0  # assumption, input range is +/- this value

    @property
    def slope_hz_per_s(self) -> float:
        return self.bandwidth_hz / self.chirp_s

    @property
    def n_samples(self) -> int:
        return round(self.sample_rate_hz * self.chirp_s)

    @property
    def range_resolution_m(self) -> float:
        """c / (2B)."""
        return C / (2 * self.bandwidth_hz)

    @property
    def max_range_m(self) -> float:
        """Range whose beat frequency equals fs/2 (real sampling)."""
        return self.range_from_beat(self.sample_rate_hz / 2)

    def beat_frequency_hz(self, range_m):
        """f_b = 2 R S / c."""
        return 2 * range_m * self.slope_hz_per_s / C

    def range_from_beat(self, f_b_hz):
        return f_b_hz * C / (2 * self.slope_hz_per_s)

    def sample_times(self) -> np.ndarray:
        return np.arange(self.n_samples) / self.sample_rate_hz


# 5.725-5.875 GHz. Cables and dummy load only: it extends above the 5.850 GHz
# edge of the listed free-use band.
CONDUCTED_150MHZ = RadarConfig(f_start_hz=5.725e9, bandwidth_hz=150e6)


def chirp_frequency_hz(cfg: RadarConfig, t):
    """Instantaneous transmit frequency during one ramp."""
    return cfg.f_start_hz + cfg.slope_hz_per_s * t


def chirp_phase_rad(cfg: RadarConfig, t, f_ref_hz: float = 0.0):
    """Transmit phase. f_ref_hz shifts the carrier down for numeric checks."""
    f0 = cfg.f_start_hz - f_ref_hz
    return 2 * np.pi * (f0 * t + 0.5 * cfg.slope_hz_per_s * t**2)


def beat_phase_rad(cfg: RadarConfig, t, range_m: float):
    """phase_tx(t) - phase_tx(t - tau), expanded to avoid cancellation error.

    Valid for t >= tau. The model also applies it to the first sample (t = 0),
    which ignores the tau-long start of each ramp (0.2 us at 30 m).
    """
    tau = 2 * range_m / C
    s = cfg.slope_hz_per_s
    return 2 * np.pi * (cfg.f_start_hz * tau + s * tau * t - 0.5 * s * tau**2)


def beat_signal(cfg: RadarConfig, targets, noise_rms_v: float = 0.0, rng=None):
    """Mixer output in volts for targets given as (range_m, amplitude_v)."""
    t = cfg.sample_times()
    x = np.zeros_like(t)
    for range_m, amplitude_v in targets:
        x += amplitude_v * np.cos(beat_phase_rad(cfg, t, range_m))
    if noise_rms_v > 0:
        if rng is None:
            raise ValueError("pass a numpy Generator so noisy runs are reproducible")
        x += rng.normal(0.0, noise_rms_v, t.size)
    return x


def quantize(x, bits: int, full_scale_v: float):
    """Uniform mid-tread quantizer over [-FS, +FS - LSB], output in volts."""
    lsb = 2 * full_scale_v / 2**bits
    codes = np.clip(np.round(x / lsb), -(2 ** (bits - 1)), 2 ** (bits - 1) - 1)
    return codes * lsb


def capture(cfg: RadarConfig, targets, noise_rms_v: float = 0.0, rng=None):
    """beat_signal followed by the configured ADC."""
    x = beat_signal(cfg, targets, noise_rms_v, rng)
    return quantize(x, cfg.adc_bits, cfg.adc_full_scale_v)


def make_window(name: str, n: int) -> np.ndarray:
    if name == "rect":
        return np.ones(n)
    if name == "hann":
        return 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)  # periodic Hann
    raise ValueError(f"unknown window: {name}")


def range_fft(cfg: RadarConfig, x, window: str = "hann", nfft: int | None = None):
    """Return (range_axis_m, amplitude_v).

    amplitude_v is scaled so a tone of peak A, well away from DC and fs/2,
    reads A at its peak.
    """
    nfft = nfft or x.size
    if nfft < x.size:
        raise ValueError("nfft shorter than the record would drop samples")
    w = make_window(window, x.size)
    spectrum = 2 * np.fft.rfft(x * w, nfft) / w.sum()
    freqs = np.fft.rfftfreq(nfft, 1 / cfg.sample_rate_hz)
    return cfg.range_from_beat(freqs), np.abs(spectrum)


def estimate_range_m(cfg, x, window="hann", pad_factor=16, min_range_m=1.0):
    """Range of the strongest peak, refined with a parabola on log magnitude."""
    r, a = range_fft(cfg, x, window, pad_factor * x.size)
    first = max(int(np.searchsorted(r, min_range_m)), 1)
    k = first + int(np.argmax(a[first:-1]))
    left, mid, right = np.log(a[k - 1 : k + 2] + 1e-30)
    curvature = left - 2 * mid + right
    delta = 0.5 * (left - right) / curvature if curvature < 0 else 0.0
    return r[k] + delta * (r[1] - r[0])


def two_targets_resolved(
    cfg, r1_m, separation_m, window="hann", phase_rad=None, dip_db=3.0
) -> bool:
    """True if two equal targets give two peaks with a dip between them.

    Criterion (assumption): the spectrum shows a local maximum within a quarter
    resolution cell of each target, and the minimum between them is at least
    dip_db below the weaker one. Noiseless and unquantized. The position limit
    matters: nearly opposite-phase echoes much closer than one cell still make
    two peaks, but in the wrong places (about 0.47 m off at 0.5 m spacing,
    rectangular window).

    phase_rad overrides the relative phase of the second echo. By default it
    follows from the geometry through the carrier term.
    """
    t = cfg.sample_times()
    r2_m = r1_m + separation_m
    p1 = beat_phase_rad(cfg, t, r1_m)
    p2 = beat_phase_rad(cfg, t, r2_m)
    if phase_rad is not None:
        p2 = p2 - p2[0] + p1[0] + phase_rad
    r, a = range_fft(cfg, 0.4 * (np.cos(p1) + np.cos(p2)), window, 64 * t.size)
    peaks = np.flatnonzero((a[1:-1] > a[:-2]) & (a[1:-1] >= a[2:])) + 1
    tolerance = cfg.range_resolution_m / 4
    found = []
    for target in (r1_m, r2_m):
        near = peaks[np.abs(r[peaks] - target) <= tolerance]
        if near.size == 0:
            return False
        found.append(near[np.argmax(a[near])])
    i, j = sorted(found)
    if i == j:
        return False
    return bool(a[i : j + 1].min() <= min(a[i], a[j]) * 10 ** (-dip_db / 20))
