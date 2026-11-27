"""Processing checks against closed-form values and Monte Carlo. Simulation only."""

import fmcw
import numpy as np
import pytest
from radar_display import processing as p

CFG = fmcw.RadarConfig()  # 115 MHz
CFG150 = fmcw.CONDUCTED_150MHZ
C = 299_792_458.0
M = 16


def frame(cfg, targets, noise_v, seed=0, chirps=M):
    rng = np.random.default_rng(seed)
    return np.stack([fmcw.capture(cfg, targets, noise_v, rng) for _ in range(chirps)])


def theoretical_noise_power(sigma_v, window, n=100, chirps=M):
    """E|noise cell|^2 of the averaged spectrum, scaled as range_fft scales it."""
    w = fmcw.make_window(window, n)
    return 4 * sigma_v**2 * np.sum(w**2) / np.sum(w) ** 2 / chirps


def test_threshold_factor_closed_form():
    expected = 15 * (1e4 ** (1 / 15) - 1)
    assert p.threshold_factor(16, 1e-4) == pytest.approx(expected)
    assert 10 * np.log10(expected) == pytest.approx(11.05, abs=0.01)
    # With very many chirps the noise is known, and a tends to ln(1/Pfa).
    assert p.threshold_factor(100_000, 1e-4) == pytest.approx(np.log(1e4), rel=1e-3)
    with pytest.raises(ValueError):
        p.threshold_factor(1, 1e-4)
    with pytest.raises(ValueError):
        p.threshold_factor(16, 0.0)


@pytest.mark.parametrize("window", ["hann", "rect"])
def test_noise_estimate_matches_theory_and_ignores_still_targets(window):
    sigma = 0.01
    estimates = [
        p.noise_power(CFG, frame(CFG, [(12.0, 0.2)], sigma, seed), window)[3:47]
        for seed in range(300)
    ]
    # ADC rounding adds a little noise on top of sigma.
    expected = theoretical_noise_power(sigma, window)
    assert np.mean(estimates) == pytest.approx(expected, rel=0.03)


@pytest.mark.parametrize("pfa", [1e-2, 1e-3])
def test_false_alarm_probability_per_cell(pfa):
    rng = np.random.default_rng(11)
    crossings = trials = 0
    for _ in range(4000):
        x = fmcw.quantize(rng.normal(0, 0.01, (M, CFG.n_samples)), 12, 1.0)
        result = p.process_frame(CFG, x, "hann", p.DetectionSettings(pfa=pfa))
        over = result.cell_amplitude_v[result.gate] > result.threshold_v[result.gate]
        crossings += int(over.sum())
        trials += result.gate.size
    # About 880 and 88 events expected: allow roughly 3 standard deviations.
    # Neighbouring cells are correlated by the window. A larger one-off run
    # (60 000 frames) measured 9.99e-3, 1.03e-3 and, at 1e-4, 9.7e-5.
    assert crossings / trials == pytest.approx(pfa, rel=0.32 if pfa == 1e-3 else 0.1)


def test_tested_cells_cover_3_to_30_m():
    result = p.process_frame(CFG, np.zeros((M, 100)))
    cell = C / (2 * 115e6)
    ranges = result.cell_range_m[result.gate]
    assert ranges[0] >= 3.0 - cell / 2 and ranges[0] - cell < 3.0 - cell / 2
    assert ranges[-1] <= 30.0 + cell / 2 and ranges[-1] + cell > 30.0 + cell / 2
    assert result.gate.size == 22  # decision 002 says "about 21"


def test_silent_input_gives_no_detections_and_a_finite_threshold():
    result = p.process_frame(CFG, np.zeros((M, 100)))
    assert result.detections == ()
    assert np.all(result.threshold_v > 0)


@pytest.mark.parametrize("cfg", [CFG, CFG150], ids=["115MHz", "150MHz"])
@pytest.mark.parametrize("window", ["hann", "rect"])
def test_one_strong_target_is_reported_once(cfg, window):
    """Window side bumps must not show up as extra targets."""
    for range_m in np.arange(3.0, 30.01, 0.37):
        result = p.process_frame(cfg, frame(cfg, [(range_m, 0.4)], 0.001), window)
        found = [round(d.range_m, 2) for d in result.detections]
        assert len(found) == 1, (range_m, found)
        # The rect window's bumps pull the peak a little more than Hann's.
        assert found[0] == pytest.approx(range_m, abs=0.1 if window == "hann" else 0.2)


def test_range_matches_the_simulation_estimator():
    chirps = frame(CFG, [(17.3, 0.2)], 0.002)
    result = p.process_frame(CFG, chirps)
    reference = fmcw.estimate_range_m(CFG, chirps.mean(axis=0), min_range_m=3.0)
    assert result.detections[0].range_m == pytest.approx(reference, abs=1e-6)
    assert result.detections[0].beat_hz == pytest.approx(
        2 * result.detections[0].range_m * (115e6 / 1e-3) / C
    )


def test_snr_matches_the_closed_form_value():
    amplitude, sigma = 0.02, 0.01
    values = [
        p.process_frame(CFG, frame(CFG, [(15.0, amplitude)], sigma, s))
        .detections[0]
        .snr_db
        for s in range(200)
    ]
    expected = 10 * np.log10(amplitude**2 / theoretical_noise_power(sigma, "hann"))
    # Same value from per-sample SNR plus 15.2 dB (Hann FFT) plus 12.0 dB
    # (16 chirps), the first figure being the one in docs/requirements.md.
    per_sample = 10 * np.log10(amplitude**2 / 2 / sigma**2)
    assert expected == pytest.approx(per_sample + 15.2 + 12.04, abs=0.05)
    assert np.median(values) == pytest.approx(expected, abs=0.5)


def test_weak_but_visible_target_is_usually_found():
    # 4 mV over 10 mV noise is about 16 dB after processing (calculated).
    found = [
        any(
            abs(d.range_m - 24.0) < 0.65
            for d in p.process_frame(
                CFG, frame(CFG, [(24.0, 0.004)], 0.01, s)
            ).detections
        )
        for s in range(200)
    ]
    assert np.mean(found) > 0.95


def test_three_targets_with_40_db_spread_are_found():
    targets = [(4.0, 0.2), (14.0, 0.02), (27.0, 0.004)]
    result = p.process_frame(CFG, frame(CFG, targets, 0.003))
    found = sorted(d.range_m for d in result.detections)
    assert found == pytest.approx([4.0, 14.0, 27.0], abs=0.25)
    assert result.detections[0].range_m == pytest.approx(4.0, abs=0.25)  # strongest


def test_two_well_separated_equal_targets_give_two_detections():
    targets = [(12.0, 0.05), (16.0, 0.05)]
    result = p.process_frame(CFG, frame(CFG, targets, 0.002))
    assert sorted(d.range_m for d in result.detections) == pytest.approx(
        [12.0, 16.0], abs=0.4
    )


@pytest.mark.parametrize("range_m", [1.0, 36.0, 42.0])
def test_targets_outside_the_searched_span_are_not_reported(range_m):
    result = p.process_frame(CFG, frame(CFG, [(range_m, 0.1)], 0.001))
    assert result.detections == ()


def test_leakage_envelope_matches_known_window_sidelobes():
    for window, peak_db, beyond_cells in (("hann", -31.5, 2.0), ("rect", -13.3, 1.0)):
        envelope = p.leakage_envelope(window, 100)
        assert envelope[0] == pytest.approx(1.0)
        assert np.all(np.diff(envelope) <= 0)
        highest = envelope[int(beyond_cells * 64) + 1]
        assert 20 * np.log10(highest) == pytest.approx(peak_db, abs=0.2)


def test_bad_input_is_rejected():
    with pytest.raises(ValueError):
        p.process_frame(CFG, np.zeros((M, 99)))
    with pytest.raises(ValueError):
        p.process_frame(CFG, np.zeros((1, 100)))
    with pytest.raises(ValueError):
        p.process_frame(CFG, np.zeros(100))
