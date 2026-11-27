"""Checks of the baseband model against closed-form results.

Expected values are written from c, B, T and textbook formulas, not read back
from the functions under test.
"""

from dataclasses import replace

import fmcw
import numpy as np
import pytest

# Closed-form checks use the 150 MHz case; the radiated default is tested below.
CFG = fmcw.CONDUCTED_150MHZ
RADIATED = fmcw.RadarConfig()
C = 299_792_458.0


def db(ratio):
    return 20 * np.log10(ratio)


def test_closed_form_values():
    assert CFG.slope_hz_per_s == pytest.approx(1.5e11)
    assert CFG.n_samples == 100
    assert CFG.beat_frequency_hz(30.0) == pytest.approx(2 * 30 * 1.5e11 / C)
    assert CFG.beat_frequency_hz(30.0) == pytest.approx(30_020.77, abs=0.01)
    assert CFG.range_resolution_m == pytest.approx(C / (2 * 150e6))
    assert CFG.range_resolution_m == pytest.approx(0.999308, abs=1e-6)
    assert CFG.max_range_m == pytest.approx(50e3 * C / (2 * 1.5e11))


def test_chirp_covers_the_sweep():
    assert fmcw.chirp_frequency_hz(CFG, 0.0) == pytest.approx(5.725e9)
    assert fmcw.chirp_frequency_hz(CFG, CFG.chirp_s) == pytest.approx(5.875e9)


def test_default_sweep_stays_inside_listed_band_with_guards():
    low = fmcw.chirp_frequency_hz(RADIATED, 0.0)
    high = fmcw.chirp_frequency_hz(RADIATED, RADIATED.chirp_s)
    assert low - 5.725e9 >= 5e6
    assert 5.850e9 - high >= 5e6


def test_radiated_default_closed_form_and_30_m_target():
    assert RADIATED.range_resolution_m == pytest.approx(C / (2 * 115e6))
    f_b = 2 * 30 * (115e6 / 1e-3) / C
    assert RADIATED.beat_frequency_hz(30.0) == pytest.approx(f_b)
    x = fmcw.capture(RADIATED, [(30.0, 0.8)])
    assert fmcw.estimate_range_m(RADIATED, x) == pytest.approx(30.0, abs=0.05)


def test_chirp_phase_derivative_is_chirp_frequency():
    t = np.linspace(0, CFG.chirp_s, 200_001)
    f_ref = CFG.f_start_hz
    phase = fmcw.chirp_phase_rad(CFG, t, f_ref)
    freq = np.gradient(phase, t) / (2 * np.pi)
    expected = fmcw.chirp_frequency_hz(CFG, t) - f_ref
    np.testing.assert_allclose(freq[1:-1], expected[1:-1], rtol=1e-6)


@pytest.mark.parametrize("range_m", [3.0, 10.0, 30.0, 45.0])
def test_mixing_delayed_chirp_gives_2rs_over_c(range_m):
    """Subtract the phases of the chirp and its delayed copy, then fit a line."""
    tau = 2 * range_m / C
    t = np.linspace(tau, CFG.chirp_s, 20_000)
    tx = np.exp(1j * fmcw.chirp_phase_rad(CFG, t, CFG.f_start_hz))
    rx = np.exp(1j * fmcw.chirp_phase_rad(CFG, t - tau, CFG.f_start_hz))
    # rx lacks the delayed carrier phase after the frequency shift; add it back
    rx *= np.exp(-2j * np.pi * CFG.f_start_hz * tau)
    phase = np.unwrap(np.angle(tx * np.conj(rx)))
    slope, _ = np.polyfit(t, phase, 1)
    assert slope / (2 * np.pi) == pytest.approx(2 * range_m * 1.5e11 / C, rel=1e-7)
    model = fmcw.beat_phase_rad(CFG, t, range_m)
    error = np.angle(np.exp(1j * (phase - model)))
    assert np.max(np.abs(error)) < 1e-6


def test_fft_bin_spacing_equals_range_resolution():
    r, _ = fmcw.range_fft(CFG, np.zeros(CFG.n_samples), "rect")
    assert np.diff(r) == pytest.approx(np.full(r.size - 1, C / (2 * 150e6)))


def test_rect_mainlobe_matches_sinc():
    """Rectangular window: first null at c/2B, -3 dB width 0.886 c/2B."""
    t = CFG.sample_times()
    k0 = 25  # tone exactly on a bin, far from DC and fs/2
    x = np.cos(2 * np.pi * k0 * 1e3 * t)
    pad = 256
    r, a = fmcw.range_fft(CFG, x, "rect", pad * t.size)
    peak = k0 * pad
    assert a[peak] == pytest.approx(1.0, rel=1e-3)
    assert a[peak + pad] < 1e-3
    assert a[peak - pad] < 1e-3
    above = np.flatnonzero(a[peak - pad : peak + pad] >= 2**-0.5)
    width = (above[-1] - above[0]) * (r[1] - r[0])
    assert width == pytest.approx(0.886 * C / (2 * 150e6), rel=0.02)


@pytest.mark.parametrize("range_m", [3.0, 7.3, 15.5, 22.2, 30.0, 41.7])
def test_estimated_range_noiseless(range_m):
    x = fmcw.capture(CFG, [(range_m, 0.8)])
    assert fmcw.estimate_range_m(CFG, x) == pytest.approx(range_m, abs=0.05)


def test_peak_at_30_m_is_at_the_expected_beat_frequency():
    x = fmcw.capture(CFG, [(30.0, 0.8)])
    r = fmcw.estimate_range_m(CFG, x)
    assert 2 * r * 1.5e11 / C == pytest.approx(30_020.77, abs=50)


def test_target_beyond_nyquist_aliases():
    f_true = 2 * 60.0 * 1.5e11 / C  # about 60 kHz, above fs/2 = 50 kHz
    expected = (100e3 - f_true) * C / (2 * 1.5e11)
    x = fmcw.beat_signal(CFG, [(60.0, 0.5)])
    assert fmcw.estimate_range_m(CFG, x) == pytest.approx(expected, abs=0.05)


@pytest.mark.parametrize("window", ["rect", "hann"])
def test_two_target_limits(window):
    phases = np.linspace(0, 2 * np.pi, 24, endpoint=False)

    def fraction(sep):
        return np.mean(
            [fmcw.two_targets_resolved(CFG, 20.0, sep, window, p) for p in phases]
        )

    assert fraction(0.5) == 0.0
    assert fraction(3.0) == 1.0


def test_less_bandwidth_gives_coarser_resolution():
    narrow = replace(CFG, bandwidth_hz=125e6)
    assert narrow.range_resolution_m == pytest.approx(C / 250e6)
    assert narrow.range_resolution_m > 1.19


@pytest.mark.parametrize("bits", [8, 10, 12, 16])
def test_quantization_sqnr(bits):
    """Full-scale sine: SQNR = 6.02 N + 1.76 dB."""
    n = 200_000
    x = (1 - 2.0**-bits * 2) * np.sin(2 * np.pi * np.sqrt(2) / 20 * np.arange(n))
    error = fmcw.quantize(x, bits, 1.0) - x
    sqnr = db(np.std(x) / np.std(error))
    assert sqnr == pytest.approx(6.02 * bits + 1.76, abs=0.3)


def test_quantizer_error_bound_and_clipping():
    lsb = 2 / 2**8
    x = np.linspace(-0.99, 0.99, 10_001)
    assert np.max(np.abs(fmcw.quantize(x, 8, 1.0) - x)) <= lsb / 2 + 1e-12
    clipped = fmcw.quantize(np.array([-5.0, 5.0]), 8, 1.0)
    np.testing.assert_allclose(clipped, [-1.0, 1.0 - lsb])


def test_noise_rms_and_reproducibility():
    cfg = replace(CFG, chirp_s=1.0)  # 100 000 samples
    a = fmcw.beat_signal(cfg, [], 0.1, np.random.default_rng(1))
    b = fmcw.beat_signal(cfg, [], 0.1, np.random.default_rng(1))
    np.testing.assert_array_equal(a, b)
    assert np.std(a) == pytest.approx(0.1, rel=0.01)
    with pytest.raises(ValueError):
        fmcw.beat_signal(CFG, [], 0.1)


@pytest.mark.parametrize("window, enbw_bins", [("rect", 1.0), ("hann", 1.5)])
def test_fft_processing_gain(window, enbw_bins):
    """Real tone in white noise: bin SNR gain = 10 log10(N / (2 ENBW))."""
    n, k0, amp, sigma = CFG.n_samples, 25, 0.1, 0.1
    t = CFG.sample_times()
    rng = np.random.default_rng(2)
    tone = amp * np.cos(2 * np.pi * k0 * 1e3 * t)
    _, signal = fmcw.range_fft(CFG, tone, window)
    noise_power = np.mean(
        [
            fmcw.range_fft(CFG, rng.normal(0, sigma, n), window)[1][5:45] ** 2
            for _ in range(2000)
        ]
    )
    snr_out = 10 * np.log10(signal[k0] ** 2 / noise_power)
    snr_in = 10 * np.log10(amp**2 / 2 / sigma**2)
    expected = 10 * np.log10(n / (2 * enbw_bins))
    assert snr_out - snr_in == pytest.approx(expected, abs=0.2)


def test_noisy_quantized_30_m_target_is_found():
    rng = np.random.default_rng(3)
    # per-sample SNR of 0 dB (assumption, not a link budget)
    estimates = [
        fmcw.estimate_range_m(
            CFG, fmcw.capture(CFG, [(30.0, 0.1)], 0.1 / np.sqrt(2), rng)
        )
        for _ in range(200)
    ]
    assert np.max(np.abs(np.array(estimates) - 30.0)) < 0.5
